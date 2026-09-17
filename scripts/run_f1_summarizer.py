#!/usr/bin/env python
"""Sanity check untuk F1 evidence summarizer (Qwen2.5-1.5B + LoRA formulab).

Memuat base model dan adapter dari models/, lalu menjalankan satu contoh
dari models/formulab_qwen_lora/sft_data/f1_sft_test.jsonl persis dengan
format prompt yang dipakai saat fine-tuning. Ini BUKAN evaluator resmi —
cuma pembuktian bahwa environment lokal bisa memuat dan menjalankan model,
dan keluarannya masih masuk akal dibanding target aslinya.

Jalankan:
    .venv-f1-llm/bin/python scripts/run_f1_summarizer.py
    .venv-f1-llm/bin/python scripts/run_f1_summarizer.py --index 5
    .venv-f1-llm/bin/python scripts/run_f1_summarizer.py --device cpu
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE_MODEL_DIR = ROOT / "models" / "Qwen2.5-1.5B-Instruct"
ADAPTER_DIR = ROOT / "models" / "formulab-qwen-lora"
SFT_TEST_PATH = ROOT / "models" / "formulab_qwen_lora" / "sft_data" / "f1_sft_test.jsonl"


def load_examples(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def pick_device(requested: str | None) -> str:
    import torch

    if requested:
        return requested
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=int, default=0, help="Baris ke berapa di f1_sft_test.jsonl")
    parser.add_argument("--device", default=None, help="cuda | cpu (default: auto-detect)")
    parser.add_argument("--max-new-tokens", type=int, default=200)
    args = parser.parse_args()

    for path in (BASE_MODEL_DIR, ADAPTER_DIR, SFT_TEST_PATH):
        if not path.exists():
            raise FileNotFoundError(
                f"{path} tidak ditemukan. Pastikan folder models/ sudah lengkap sebelum menjalankan skrip ini."
            )

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = pick_device(args.device)
    dtype = torch.bfloat16 if device == "cuda" else torch.float32
    print(f"[info] device={device} dtype={dtype}")

    examples = load_examples(SFT_TEST_PATH)
    example = examples[args.index]
    system_msg, user_msg = example["messages"][0], example["messages"][1]
    expected = example["messages"][2]["content"]

    print(f"[info] memuat base model dari {BASE_MODEL_DIR} ...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_DIR)
    base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_DIR, dtype=dtype)

    print(f"[info] menempelkan LoRA adapter dari {ADAPTER_DIR} ...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
    model.to(device)
    model.eval()

    prompt = tokenizer.apply_chat_template(
        [
            {"role": "system", "content": system_msg["content"]},
            {"role": "user", "content": user_msg["content"]},
        ],
        tokenize=False,
        add_generation_prompt=True,
    )
    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    print("[info] generating ...")
    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=args.max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    generated = tokenizer.decode(output[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True)

    print("\n=== Input (evidence card) ===")
    print(user_msg["content"])
    print("\n=== Keluaran model ===")
    print(generated.strip())
    print("\n=== Target SFT (referensi, bukan jawaban tunggal yang benar) ===")
    print(expected)
    print(
        "\n[batas] data_origin=synthetic_demo, requires_human_review=true — "
        "keluaran ini adalah ringkasan grounded synthetic-demo, bukan hasil tervalidasi."
    )


if __name__ == "__main__":
    main()
