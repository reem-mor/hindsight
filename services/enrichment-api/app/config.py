"""Runtime configuration for the HINDSIGHT enrichment service.

Twelve-factor style: everything overridable by environment variable so the same
image runs in dev, CI and prod with no code changes.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

_DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "data" / "service_catalog.yaml"


def _env_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, default))
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("HINDSIGHT_APP_NAME", "HINDSIGHT Enrichment API")
    version: str = os.getenv("HINDSIGHT_VERSION", "1.0.0")
    log_level: str = os.getenv("HINDSIGHT_LOG_LEVEL", "INFO").upper()
    json_logs: bool = _env_bool("HINDSIGHT_JSON_LOGS", True)

    service_catalog_path: Path = field(
        default_factory=lambda: Path(os.getenv("HINDSIGHT_CATALOG_PATH", str(_DEFAULT_CATALOG)))
    )

    # Confidence below this flags a doc for human review.
    review_confidence_threshold: float = _env_float("HINDSIGHT_REVIEW_THRESHOLD", 0.7)
    # Error-budget burn above this fraction tags a budget breach.
    budget_breach_fraction: float = _env_float("HINDSIGHT_BUDGET_BREACH_FRACTION", 0.5)

    # CORS origins for the dashboard (comma-separated). "*" allowed in dev.
    cors_origins: str = os.getenv("HINDSIGHT_CORS_ORIGINS", "*")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
