"""HTTP adapter minimal untuk F3 Stability Sentinel ParaLab."""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Callable, Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from modules.f3_stability_sentinel.inference import LoadedArtifact, forecast, load_artifact
from modules.f4_next_validation import recommend_next_validation

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_DIR = ROOT / "modules" / "f3_stability_sentinel" / "outputs" / "1"


class FormulaItem(BaseModel):
    bahan: str = Field(min_length=1)
    pct: float = Field(ge=0, le=100)


class ProcessConditions(BaseModel):
    heating_temp_c: float
    homogenization_rpm: float = Field(ge=0)
    mixing_time_min: float = Field(ge=0)


class Observation(BaseModel):
    week: int = Field(ge=0)
    ph: float = Field(ge=0, le=14)
    viscosity_cp: float = Field(gt=0)
    appearance: str = "uniform"


class ForecastRequest(BaseModel):
    trial_id: str = Field(min_length=1)
    formula: list[FormulaItem] = Field(min_length=1)
    process: ProcessConditions
    storage_temperature_c: float
    landmark_week: int = Field(ge=1)
    observations: list[Observation] = Field(min_length=1)
    context: dict[str, str] | None = None


class F4RecommendationRequest(BaseModel):
    """Structured F3/F2 output plus optional confirmed checkpoint for F4."""
    f3_forecast: dict
    checkpoint: dict | None = None


@lru_cache(maxsize=1)
def default_artifact_loader() -> LoadedArtifact:
    artifact_dir = Path(os.environ.get("PARALAB_F3_ARTIFACT_DIR", DEFAULT_ARTIFACT_DIR))
    return load_artifact(artifact_dir)


def create_app(artifact_loader: Callable[[], LoadedArtifact] = default_artifact_loader) -> FastAPI:
    """Create the API with an injectable artifact loader for contract tests."""
    app = FastAPI(
        title="ParaLab F3 API",
        version="0.1.0",
        description=(
            "Synthetic-demo early-risk forecast. Bukan hasil uji stabilitas formal, "
            "bukan approval formula, dan CV hanya concept-only synthetic render pilot."
        ),
    )
    origins = [origin.strip() for origin in os.environ.get(
        "PARALAB_CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
    ).split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/health")
    def health() -> dict:
        try:
            artifact = artifact_loader()
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=f"F3 artifact unavailable: {exc}") from exc
        manifest = artifact.manifest
        return {
            "status": "ok",
            "model_version": manifest.get("model_version"),
            "data_origin": manifest.get("data_origin", "synthetic_demo"),
            "cv_status": manifest.get("cv_status", "concept_only_synthetic_render_pilot"),
        }

    @app.post("/v1/f3/forecasts")
    def create_forecast(request: ForecastRequest) -> dict:
        try:
            artifact = artifact_loader()
            return forecast(artifact, request.model_dump(exclude_none=True))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/v1/f4/next-validation")
    def create_f4_recommendation(request: F4RecommendationRequest) -> dict:
        return recommend_next_validation(
            request.f3_forecast,
            request.checkpoint,
        )

    return app


app = create_app()
