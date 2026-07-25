"""FastAPI app exposing live NeoTex vitals as JSON with unix timestamps."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from neotex.api.store import STORE


class VitalsBody(BaseModel):
    hr_bpm: Optional[float] = None
    rr_bpm: Optional[float] = None
    spo2_pct: Optional[float] = None
    temp_f: Optional[float] = None


class MetricsEnvelope(BaseModel):
    unix_timestamp: float
    window_s: float = 5.0
    analysis_window_s: Optional[float] = None
    sampling_rate_hz: Optional[float] = None
    source: str = "file_playback"
    file: Optional[str] = None
    vitals: VitalsBody
    quality: dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="NeoTex Baby Belt API",
        version="0.1.0",
        description="Live vitals JSON publisher for the NeoTex baby-belt demo.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, **STORE.status()}

    @app.get("/vitals/latest")
    def vitals_latest() -> dict[str, Any]:
        latest = STORE.latest()
        if latest is None:
            return {
                "unix_timestamp": None,
                "vitals": {
                    "hr_bpm": None,
                    "rr_bpm": None,
                    "spo2_pct": None,
                    "temp_f": None,
                },
                "status": "waiting",
            }
        return latest

    @app.get("/vitals/history")
    def vitals_history(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        items = STORE.history(limit=limit)
        return {"count": len(items), "items": items}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return STORE.status()

    return app


app = create_app()