"""Local HTTP gateway for ParaLab F1, F2, F4, and F5.

F1 uses only local model/data artifacts. F2 and F4 are deterministic modules.
F5 receives a browser-produced transcript and returns a draft that requires
explicit human confirmation; it never writes a journal checkpoint.
"""
from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from modules.f2_guardrail import screen_formula
from modules.f4_next_validation import recommend_next_validation
from scripts.f1_hybrid_retrieval import search
from scripts.f1_runtime import finalize_summary, prepare_summary_request, redact_f1_numbers

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROWS = Path(os.environ.get("PARALAB_F1_ROWS_PATH", ROOT / "data" / "evidence_rag_text.jsonl"))
DEFAULT_CORPUS = Path(os.environ.get("PARALAB_F1_CORPUS_PATH", ROOT / "data" / "evidence_corpus.jsonl"))
# Production mounts all ignored F1 weights under one read-only directory. The
# local-first defaults preserve the repository's existing development layout.
_MODELS_DIR = os.environ.get("PARALAB_F1_MODELS_DIR")
DEFAULT_EMBEDDINGS = Path(os.environ.get(
    "PARALAB_F1_EMBEDDINGS_PATH",
    Path(_MODELS_DIR) / "embeddings_paralab.npy" if _MODELS_DIR else ROOT / "sentence-transformer" / "embeddings_paralab.npy",
))
DEFAULT_EMBEDDING_MODEL = Path(os.environ.get(
    "PARALAB_F1_EMBEDDING_MODEL_PATH",
    Path(_MODELS_DIR) / "embedding_model" if _MODELS_DIR else ROOT / "models" / "embedding_model",
))
DEFAULT_QWEN_MODEL = Path(os.environ.get(
    "PARALAB_F1_QWEN_MODEL_PATH",
    Path(_MODELS_DIR) / "Qwen2.5-1.5B-Instruct" if _MODELS_DIR else ROOT / "models" / "Qwen2.5-1.5B-Instruct",
))
DEFAULT_QWEN_ADAPTER = Path(os.environ.get(
    "PARALAB_F1_QWEN_ADAPTER_PATH",
    Path(_MODELS_DIR) / "formulab-qwen-lora" if _MODELS_DIR else ROOT / "models" / "formulab-qwen-lora",
))


class F1Service(Protocol):
    def query(self, query: str, top_k: int = 5) -> dict[str, Any]: ...


class LocalF1Service:
    """Lazy local F1 retrieval plus Qwen/LoRA evidence summarization."""

    def __init__(
        self,
        *,
        rows_path: Path = DEFAULT_ROWS,
        corpus_path: Path = DEFAULT_CORPUS,
        embeddings_path: Path = DEFAULT_EMBEDDINGS,
        embedding_model_path: Path = DEFAULT_EMBEDDING_MODEL,
        qwen_model_path: Path = DEFAULT_QWEN_MODEL,
        qwen_adapter_path: Path = DEFAULT_QWEN_ADAPTER,
    ) -> None:
        self.rows_path = rows_path
        self.corpus_path = corpus_path
        self.embeddings_path = embeddings_path
        self.embedding_model_path = embedding_model_path
        self.qwen_model_path = qwen_model_path
        self.qwen_adapter_path = qwen_adapter_path
        self.rows: list[dict[str, Any]] | None = None
        self.embeddings: np.ndarray | None = None
        self.embedder: Any = None
        self.tokenizer: Any = None
        self.generator: Any = None

    def _load_retrieval(self) -> None:
        if self.rows is not None:
            return
        for path in (self.rows_path, self.corpus_path, self.embeddings_path, self.embedding_model_path):
            if not path.exists():
                raise FileNotFoundError(f"F1 local artifact missing: {path}")
        try:
            from sentence_transformers import SentenceTransformer
        except ModuleNotFoundError as exc:
            raise RuntimeError("F1 runtime missing sentence-transformers.") from exc
        rows = [json.loads(line) for line in self.rows_path.read_text(encoding="utf-8").splitlines() if line]
        # evidence_rag_text.jsonl only carries {source_id, text}: enough for
        # lexical/dense ranking, but prepare_summary_request() needs the
        # structured evidence-card fields (outcome, failure_mode, ...) that
        # live in evidence_corpus.jsonl instead. Enrich by source_id while
        # keeping row ORDER from rows_path, since embeddings_paralab.npy is
        # aligned to that file positionally, not by id.
        corpus_by_id = {
            record["source_id"]: record
            for record in (
                json.loads(line) for line in self.corpus_path.read_text(encoding="utf-8").splitlines() if line
            )
        }
        for row in rows:
            extra = corpus_by_id.get(row["source_id"])
            if extra:
                for key in (
                    "outcome", "failure_mode", "journal_title", "narrative_excerpt",
                    "lesson_learned", "data_origin", "scientific_validation_status",
                ):
                    if key in extra:
                        row.setdefault(key, extra[key])
        self.rows = rows
        self.embeddings = np.asarray(np.load(self.embeddings_path), dtype=np.float32)
        if len(self.rows) != len(self.embeddings):
            raise ValueError("F1 evidence rows and embeddings are misaligned.")
        self.embedder = SentenceTransformer(str(self.embedding_model_path), local_files_only=True)

    def _load_generator(self) -> None:
        if self.generator is not None:
            return
        for path in (self.qwen_model_path, self.qwen_adapter_path):
            if not path.exists():
                raise FileNotFoundError(f"F1 local artifact missing: {path}")
        try:
            import torch
            from peft import PeftModel
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ModuleNotFoundError as exc:
            raise RuntimeError("F1 runtime missing transformers, torch, or peft.") from exc
        device = "cuda" if torch.cuda.is_available() else "cpu"
        dtype = torch.float16 if device == "cuda" else torch.float32
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.qwen_model_path), local_files_only=True)
        base = AutoModelForCausalLM.from_pretrained(
            str(self.qwen_model_path),
            local_files_only=True,
            torch_dtype=dtype,
            device_map="auto" if device == "cuda" else None,
        )
        self.generator = PeftModel.from_pretrained(base, str(self.qwen_adapter_path), local_files_only=True)
        if device == "cpu":
            self.generator.to(device)
        self.generator.eval()

    def _summarize(self, request: dict[str, Any]) -> dict[str, str]:
        self._load_generator()
        import torch

        evidence = json.dumps(request["related_cases"], ensure_ascii=False)
        prompt = (
            "Ringkas evidence berikut dalam Bahasa Indonesia untuk peneliti R&D. "
            "Jangan tulis angka, konsentrasi, pH, suhu, atau keputusan kelulusan. "
            "Nyatakan bahwa peneliti harus memvalidasi hasil.\n"
            f"Pertanyaan: {request['query']}\nEvidence: {evidence}\nRingkasan:"
        )
        messages = [{"role": "user", "content": prompt}]
        encoded = self.tokenizer.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
            return_dict=True,
        )
        encoded = encoded.to(self.generator.device)
        with torch.inference_mode():
            generated = self.generator.generate(
                input_ids=encoded["input_ids"],
                attention_mask=encoded.get("attention_mask"),
                max_new_tokens=160,
                do_sample=False,
            )
        text = self.tokenizer.decode(generated[0][encoded["input_ids"].shape[-1] :], skip_special_tokens=True).strip()
        return finalize_summary({"summary": text})

    def query(self, query: str, top_k: int = 5) -> dict[str, Any]:
        self._load_retrieval()
        vector = np.asarray(self.embedder.encode([query], normalize_embeddings=True)[0], dtype=np.float32)
        retrieval = search(self.rows or [], self.embeddings, vector, query, top_k=top_k)
        request = prepare_summary_request(query, retrieval)
        evidence = [
            {
                key: row[key]
                for key in ("source_id", "hybrid_score", "outcome", "failure_mode", "journal_title")
                if key in row
            }
            for row in retrieval["related_cases"]
        ]
        if request is None:
            return {
                "query": query,
                "evidence_status": "insufficient",
                "evidence": evidence,
                "answer": None,
                "requires_human_review": True,
                "limitations": retrieval["limitations"],
            }
        answer = self._summarize(request)
        return {
            "query": query,
            "evidence_status": retrieval["evidence_status"],
            "evidence": evidence,
            "answer": answer,
            "requires_human_review": True,
            "limitations": retrieval["limitations"],
        }


class FormulaItem(BaseModel):
    bahan: str = Field(min_length=1)
    pct: float = Field(ge=0, le=100)


class F2Request(BaseModel):
    formula: list[FormulaItem] = Field(min_length=1)
    context: dict[str, str] = Field(default_factory=dict)
    ph: float | None = Field(default=None, ge=0, le=14)


class F4Request(BaseModel):
    f3_forecast: dict[str, Any]
    checkpoint: dict[str, Any] | None = None


class F5Request(BaseModel):
    selected_trial_id: str = Field(min_length=1)
    transcript: str = Field(min_length=1, max_length=10_000)


_DIGITS = {
    "nol": "0", "satu": "1", "dua": "2", "tiga": "3", "empat": "4",
    "lima": "5", "enam": "6", "tujuh": "7", "delapan": "8", "sembilan": "9",
}


def _number(text: str) -> float:
    cleaned = text.lower().strip().replace(",", ".")
    numeric = re.search(r"\d+(?:\.\d+)?", cleaned)
    if numeric:
        return float(numeric.group(0))
    words = re.findall(r"[a-z]+", cleaned)
    if "koma" in words:
        divider = words.index("koma")
        left, right = words[:divider], words[divider + 1 :]
        if len(left) == 1 and left[0] in _DIGITS and right and all(word in _DIGITS for word in right):
            return float(_DIGITS[left[0]] + "." + "".join(_DIGITS[word] for word in right))
    if len(words) == 1 and words[0] in _DIGITS:
        return float(_DIGITS[words[0]])
    raise ValueError(f"unsupported spoken number: {text!r}")


def _extract_value(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, flags=re.IGNORECASE)
    if not match:
        return None
    try:
        return _number(match.group(1))
    except ValueError:
        return None


def f5_draft(selected_trial_id: str, transcript: str) -> dict[str, Any]:
    """Produce a conservative draft from a browser STT transcript."""
    measurements: dict[str, float] = {}
    ph = _extract_value(transcript, r"\bp\s*h\s*(?:nya|nya adalah|:)?\s*([^,;]+)")
    viscosity = _extract_value(transcript, r"(?:viskositas|kekentalan)\s*(?:nya|:)?\s*([^,;]+)")
    if ph is not None and 0 <= ph <= 14:
        measurements["ph"] = ph
    if viscosity is not None and viscosity > 0:
        measurements["viscosity_cp"] = viscosity

    normalized = transcript.lower()
    appearance = None
    if any(token in normalized for token in ("homogen", "seragam", "uniform")):
        appearance = "uniform"
    elif any(token in normalized for token in ("keruh", "menggumpal", "tidak homogen", "tidak seragam")):
        appearance = "heterogeneous"
    elif any(token in normalized for token in ("memisah", "pemisahan fase", "terpisah")):
        appearance = "phase_separation"

    return {
        "trial_id": selected_trial_id,
        "proposed_checkpoint_patch": {
            "measurements": measurements,
            "observations": {"appearance": appearance} if appearance else {},
        },
        "field_confidence": {
            **{field: 0.65 for field in measurements},
            **({"appearance": 0.60} if appearance else {}),
        },
        "requires_confirmation": True,
        "data_origin": "browser_stt_transcript",
        "limitations": [
            "F5 menghasilkan draft dari transkrip browser, bukan pengukuran laboratorium.",
            "Semua field wajib diperiksa dan dikonfirmasi manusia sebelum ditulis ke jurnal.",
        ],
    }


@lru_cache(maxsize=1)
def default_f1_service() -> LocalF1Service:
    return LocalF1Service()


def create_app(f1_service: F1Service | None = None) -> FastAPI:
    service = f1_service or default_f1_service()
    app = FastAPI(title="ParaLab Local Model Gateway", version="0.1.0")
    origins = [origin.strip() for origin in os.environ.get(
        "PARALAB_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "services": ["f1", "f2", "f4", "f5"], "mode": "local"}

    @app.post("/v1/f1/query")
    def f1_query(payload: dict[str, Any]) -> dict[str, Any]:
        query = payload.get("query")
        if not isinstance(query, str) or not query.strip():
            raise HTTPException(status_code=422, detail="query must be a non-empty string")
        try:
            return service.query(query.strip())
        except (FileNotFoundError, RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"F1 local service unavailable: {exc}") from exc

    @app.post("/v1/f2/health-check")
    def f2_health_check(request: F2Request) -> dict[str, Any]:
        return screen_formula(
            [item.model_dump() for item in request.formula],
            konteks=request.context,
            ph=request.ph,
        )

    @app.post("/v1/f4/next-validation")
    def f4_next_validation(request: F4Request) -> dict[str, Any]:
        return recommend_next_validation(request.f3_forecast, request.checkpoint)

    @app.post("/v1/f5/transcribe-draft")
    def f5_transcribe_draft(request: F5Request) -> dict[str, Any]:
        return f5_draft(request.selected_trial_id, request.transcript)

    return app


app = create_app()
