"""F1 runtime guardrails between hybrid retrieval and student summary."""
import re

SYNTHETIC_LIMITATION = "Evidence ini berasal dari data sintetis dan memerlukan validasi R&D manusia."
FORBIDDEN = (
    r"\d+(?:[.,]\d+)?\s*%",
    r"\bp\s*h\s*\d",
    r"\d+(?:[.,]\d+)?\s*(?:cp|rpm|°c)\b",
)
SAFE_FIELDS = (
    "source_id", "outcome", "failure_mode", "journal_title", "narrative_excerpt",
    "lesson_learned", "data_origin", "scientific_validation_status",
)


def redact_f1_numbers(value):
    """Remove sensitive numeric details while keeping evidence prose readable."""
    if not isinstance(value, str):
        return value
    text = re.sub(r"\bminggu\s+ke-\s*\d+\b", "fase pengamatan lanjutan", value, flags=re.I)
    text = re.sub(r"\bsetelah\s+\d+\s+minggu\b", "setelah beberapa minggu", text, flags=re.I)
    text = re.sub(r"\b\d+(?:[.,]\d+)?\s*%?\b", "", text)
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([,.;:])", r"\1", text).strip()


def prepare_summary_request(query, retrieval):
    if retrieval.get("evidence_status") != "sufficient" or not retrieval.get("related_cases"):
        return None
    cases = []
    for row in retrieval["related_cases"]:
        card = {key: row.get(key) for key in SAFE_FIELDS if key in row}
        for key in ("narrative_excerpt", "lesson_learned"):
            if key in card:
                card[key] = redact_f1_numbers(card[key])
        cases.append(card)
    return {"query": query, "related_cases": cases}


def finalize_summary(model_output):
    if not isinstance(model_output, dict) or not isinstance(model_output.get("summary"), str) or not model_output["summary"].strip():
        raise ValueError("summary must be non-empty")
    text = model_output["summary"]
    if any(re.search(pattern, text, re.I) for pattern in FORBIDDEN):
        raise ValueError("summary must not expose measurements or concentrations")
    return {"summary": text.strip(), "limitations": SYNTHETIC_LIMITATION}
