# Local Qwen host handoff — ParaLab

**Audience:** engineer/agent configuring the Linux laptop that hosts ParaLab model inference.

## Scope

Run one HTTPS-reachable FastAPI gateway which loads Qwen once and serves both
F1 Evidence Copilot and F5 Voice Log. F3/F4 already exist independently in
`api/app.py`; this handoff specifies what must be added for F1/F5. It does not
authorize a browser to load model weights.

## Host baseline

| Item | Available | Deployment decision |
|---|---:|---|
| OS | Linux | Use Python 3.11 virtual environment |
| GPU | RTX 4050 Laptop | 6 GB VRAM; one process and one active generation |
| RAM | 32 GB | Sufficient for model files, audio decoding, and CPU fallback work |
| Qwen base | Qwen2.5-1.5B-Instruct | Load locally in BF16/FP16 |
| ParaLab LoRA | rank 16, alpha 32 | Attach once with PEFT |
| Whisper | supplied by STT teammate | Serve via `faster-whisper`; do not download during a user request |

The host is suitable for a hackathon demo. It is **not** a multi-user inference
cluster: run a single Uvicorn worker, serialize Qwen generations, cap input
and output lengths, and return 429/timeout rather than allowing OOM.

## Artifacts to copy (do not commit)

Copy whole directories into a private host location such as `/opt/paralab/models`:

```text
/opt/paralab/models/
├── Qwen2.5-1.5B-Instruct/                         # about 2.9 GB
│   ├── config.json
│   ├── tokenizer.json
│   ├── model.safetensors
│   └── all remaining files in the source folder
├── formulab_qwen_lora/
│   └── qwen25-15b-formulab-lora/                  # about 86 MB
│       ├── adapter_config.json
│       ├── adapter_model.safetensors
│       └── all remaining files in the source folder
└── embedding_model/                               # about 466 MB; needed by F1
    └── all files in the source folder
```

The LoRA is not standalone. Its recorded base is
`Qwen/Qwen2.5-1.5B-Instruct`; the host must load that exact base before the
adapter. It targets `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`,
`up_proj`, and `down_proj`.

Also retain the F1 source-controlled retrieval assets:

```text
data/f1_embeddings_v4.npy
data/f1_embeddings_v4.manifest.json
data/training/f1_evidence_catalog.jsonl
data/public_observed/f1_evidence_documents.jsonl
```

Before accepting requests, validate that document count, embedding row count,
embedding dimension, and manifest ordered source IDs align. A shape-compatible
but stale embedding matrix is an invalid deployment.

## Linux setup

```bash
sudo apt update
sudo apt install -y git curl ffmpeg build-essential python3.11 python3.11-venv

git clone https://github.com/Ini-statement-aku-yang-paling-baddie/paralab-architecture.git
cd paralab-architecture
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
```

First make the NVIDIA driver work:

```bash
nvidia-smi
```

Then install the CUDA-enabled PyTorch wheel matching the host driver from the
official PyTorch selector. Do **not** install the CPU wheel. Install remaining
packages only after that:

```bash
python -m pip install -r requirements/model-gateway.txt
python - <<'PY'
import torch
assert torch.cuda.is_available(), "CUDA PyTorch is required for the demo host"
print(torch.__version__)
print(torch.cuda.get_device_name(0))
PY
```

Copy `deploy/model-gateway.env.example` to a private `.env`, adjust the actual
paths and website origin, and keep that private file outside Git.

## Required runtime lifecycle

Implement the gateway so that app startup, not each request, does all of this:

1. Load Qwen base from `PARALAB_QWEN_BASE_DIR` with `local_files_only=True`.
2. Attach LoRA from `PARALAB_QWEN_LORA_DIR` with PEFT and call `eval()`.
3. Load SentenceTransformer from `PARALAB_F1_EMBEDDING_MODEL_DIR` with
   `local_files_only=True`.
4. Load and validate F1 corpus + embedding manifest.
5. Initialize the approved local Whisper model once.
6. Create one async semaphore of size `PARALAB_MODEL_CONCURRENCY` shared by
   F1 and F5 Qwen generation.
7. Surface readiness of Qwen, embeddings, corpus, and Whisper independently in
   `GET /health`; do not report ready if a required artifact is unavailable.

Initial inference settings for the 6 GB GPU:

```text
workers:                 1
active Qwen generations: 1
max input tokens:        2048
max new tokens:          256
timeout:                 90 seconds
dtype:                   bfloat16, or float16 if BF16 fails
```

If CUDA OOM occurs, reduce input to 1536 then output to 160. Only after those
steps consider a tested 4-bit path; do not silently change output quality or
model behavior.

## Endpoint contracts to implement

### `POST /v1/f1/query`

Request:

```json
{"query":"Kenapa gel cream mengalami penurunan viskositas?","top_k":5}
```

Response must contain at least:

```json
{
  "summary":"Ringkasan grounded dalam Bahasa Indonesia.",
  "related_cases":[{"source_id":"J-2024-072-T03"}],
  "limitations":"Evidence ini berasal dari data sintetis dan memerlukan validasi R&D manusia.",
  "data_origin":"synthetic_demo"
}
```

Implementation rules:

- Run retrieval before generation using `scripts/f1_hybrid_retrieval.py`.
- Pass only `scripts/f1_runtime.py::prepare_summary_request()` output to Qwen.
- If retrieval is insufficient, do not call Qwen; return an insufficient-evidence
  response.
- Finalize output with `scripts/f1_runtime.py::finalize_summary()`.
- Do not disclose formula, ingredient, concentration, pH, RPM, temperature,
  raw prompt, or stack trace.

### `POST /v1/f5/transcribe-draft`

Accept `multipart/form-data`:

```text
audio: audio file
selected_trial_id: non-empty string
language: optional; default id
```

Response must contain at least:

```json
{
  "trial_id":"UI-owned trial ID",
  "transcript":"hasil STT",
  "proposed_checkpoint_patch":{"measurements":{},"observations":{}},
  "field_confidence":{},
  "requires_confirmation":true
}
```

Implementation rules:

- Reject invalid MIME type, oversized audio, and empty transcript.
- Store uploaded audio only in a request-scoped temporary file; delete it in a
  `finally` block.
- Run local Whisper, then Qwen extraction constrained to JSON schema.
- Send all model output to `scripts/f5_runtime.py::finalize_extraction()` with
  `selected_trial_id` from the request. This function must overwrite any
  hallucinated ID and force `requires_confirmation=true`.
- Never write a journal/checkpoint in this endpoint. The frontend must preview,
  permit edits, and get explicit human confirmation first.

## Launch and public access

Local smoke run:

```bash
source .venv/bin/activate
set -a; source /private/path/to/paralab.env; set +a
uvicorn api.app:app --host 127.0.0.1 --port 7860 --workers 1
```

Expose `127.0.0.1:7860` with a HTTPS tunnel (Cloudflare Tunnel or ngrok). Do
not point the browser at plain HTTP on a laptop, because an HTTPS website will
block mixed content.

Set the web host build variable:

```dotenv
VITE_MODEL_API_BASE=https://<public-gateway-url>
```

`VITE_*` is public browser configuration. Never put API keys, tunnel tokens, or
model paths there.

## Security and reliability minimum

- `PARALAB_CORS_ORIGINS` must name actual website origins; never use `*` for a
  public tunnel.
- Limit audio body size (default 20 MB), request timeout, and active model jobs.
- Avoid persistent logs of audio, transcripts, prompts, raw evidence, or model
  output.
- Return structured client-safe errors; do not return exception tracebacks.
- Keep model artifacts outside the Git repository and never expose a directory
  listing route.
- Tunnel credentials and any access-control credentials remain private on the
  host.

## Definition of done

```text
[ ] nvidia-smi works
[ ] torch.cuda.is_available() is true
[ ] Qwen base + LoRA loads from local paths without model download
[ ] embedding model and F1 corpus/manifest validate at startup
[ ] Whisper successfully transcribes a short Indonesian audio sample
[ ] GET /health reports F1 and F5 readiness truthfully
[ ] F1 gives a grounded Indonesian response with limitation/provenance
[ ] F5 uses selected_trial_id from request, not model output
[ ] F5 always returns requires_confirmation=true and performs no journal write
[ ] service runs with exactly one worker and one active Qwen generation
[ ] public HTTPS URL works from the deployed web origin without CORS/mixed-content errors
```
