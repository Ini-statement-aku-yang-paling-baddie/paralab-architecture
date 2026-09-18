# F1/F2/F4/F5 gateway. Local model artifacts are mounted at runtime, never copied.
FROM python:3.11.16-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app
COPY requirements/model_gateway.txt requirements/f1_summarizer.txt requirements/
RUN pip install --no-cache-dir -r requirements/model_gateway.txt \
    && groupadd --system paralab \
    && useradd --system --gid paralab --home-dir /nonexistent --shell /usr/sbin/nologin paralab

COPY api/ api/
COPY modules/ modules/
COPY scripts/f1_hybrid_retrieval.py scripts/f1_runtime.py scripts/
COPY data/evidence_rag_text.jsonl data/evidence_corpus.jsonl data/ \
     data/ingredient_master.json data/formulation_rules.json data/
RUN chown -R paralab:paralab /app

USER paralab
EXPOSE 8100
CMD ["uvicorn", "api.model_gateway:app", "--host", "0.0.0.0", "--port", "8100", "--no-access-log"]
