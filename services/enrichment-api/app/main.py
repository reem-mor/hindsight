"""HINDSIGHT Enrichment API.

FastAPI service that enriches Gemini postmortem extractions with SRE/business
intelligence. Designed to be operated like any production service: structured
logs, correlation IDs, a /health probe and a Prometheus-style /metrics endpoint.
"""
from __future__ import annotations

import time
import uuid
from collections import Counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from .config import get_settings
from .enrichment import classify_sensitivity, enrich
from .logging_setup import configure_logging, correlation_id
from .models import (
    CategoriesResponse,
    EnrichedResult,
    GeminiResult,
    HealthResponse,
    IncidentMetrics,
    SensitivityRequest,
    SensitivityResponse,
    Severity,
    SeverityRequest,
    SeverityResponse,
)
from .routing import ServiceCatalog
from .severity import score_severity

settings = get_settings()
configure_logging(settings.log_level, settings.json_logs)

import logging  # noqa: E402  (after logging configured)

logger = logging.getLogger("hindsight.api")

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
    description=(
        "Enrichment microservice for **HINDSIGHT** — turns raw Gemini postmortem "
        "extractions into routed, scored, audit-ready incident records."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- shared state ---------------------------------------------------------- #
STARTED_AT = time.time()
CATALOG = ServiceCatalog(settings.service_catalog_path)

# Lightweight in-process metrics (Prometheus exposition format).
_METRICS: Counter[str] = Counter()


# ---- middleware ------------------------------------------------------------ #
@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    cid = request.headers.get("x-correlation-id") or str(uuid.uuid4())
    token = correlation_id.set(cid)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:  # noqa: BLE001
        _METRICS["hindsight_requests_errors_total"] += 1
        logger.exception("unhandled error", extra={"path": request.url.path})
        return JSONResponse(status_code=500, content={"detail": "internal error", "correlation_id": cid})
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        correlation_id.reset(token)
    _METRICS["hindsight_requests_total"] += 1
    response.headers["x-correlation-id"] = cid
    logger.info(
        "request",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status": response.status_code,
            "duration_ms": round(elapsed_ms, 2),
        },
    )
    return response


# ---- routes ---------------------------------------------------------------- #
@app.get("/health", response_model=HealthResponse, tags=["ops"])
def health() -> HealthResponse:
    return HealthResponse(
        version=settings.version,
        uptime_seconds=round(time.time() - STARTED_AT, 1),
        catalog_services=CATALOG.service_count,
    )


@app.get("/metrics", response_class=PlainTextResponse, tags=["ops"])
def metrics() -> str:
    """Prometheus exposition format — scrape me like any other service."""
    lines = [
        "# HELP hindsight_uptime_seconds Service uptime.",
        "# TYPE hindsight_uptime_seconds gauge",
        f"hindsight_uptime_seconds {round(time.time() - STARTED_AT, 1)}",
        "# HELP hindsight_catalog_services Number of catalogued services.",
        "# TYPE hindsight_catalog_services gauge",
        f"hindsight_catalog_services {CATALOG.service_count}",
    ]
    for key, value in sorted(_METRICS.items()):
        lines.append(f"# TYPE {key} counter")
        lines.append(f"{key} {value}")
    return "\n".join(lines) + "\n"


@app.get("/categories", response_model=CategoriesResponse, tags=["reference"])
def categories() -> CategoriesResponse:
    return CategoriesResponse(
        severities=[s.value for s in Severity],
        incident_types=[
            "outage", "degradation", "data-incident", "security",
            "deployment-failure", "capacity", "dependency-failure",
            "configuration", "other",
        ],
        sensitivities=["public", "internal", "confidential"],
        teams=CATALOG.teams,
    )


@app.get("/service-catalog", tags=["reference"])
def service_catalog() -> dict:
    return {
        "service_count": CATALOG.service_count,
        "teams": CATALOG.teams,
    }


@app.post("/enrich", response_model=EnrichedResult, tags=["enrichment"])
def enrich_endpoint(payload: GeminiResult) -> EnrichedResult:
    result = enrich(payload, settings, CATALOG)
    _METRICS["hindsight_documents_enriched_total"] += 1
    _METRICS[f'hindsight_documents_by_severity_total{{severity="{result.computed_severity.value}"}}'] += 1
    if "page-oncall" in result.routing_tags:
        _METRICS["hindsight_page_oncall_total"] += 1
    if "repeat-offender" in result.routing_tags:
        _METRICS["hindsight_repeat_offender_total"] += 1
    logger.info(
        "document enriched",
        extra={
            "document_id": result.document_id,
            "computed_severity": result.computed_severity.value,
            "department": result.department,
            "tags": result.routing_tags,
        },
    )
    return result


@app.post("/sensitivity", response_model=SensitivityResponse, tags=["enrichment"])
def sensitivity_endpoint(payload: SensitivityRequest) -> SensitivityResponse:
    blob = " ".join(
        payload.entities.people
        + payload.entities.teams
        + payload.entities.systems
        + payload.entities.error_codes
    )
    sens, rationale = classify_sensitivity(
        incident_type=payload.incident_type,
        affected_jurisdictions=payload.affected_jurisdictions,
        entities_blob=blob,
        summary=payload.summary,
    )
    return SensitivityResponse(sensitivity=sens, rationale=rationale)


@app.post("/score-severity", response_model=SeverityResponse, tags=["enrichment"])
def score_severity_endpoint(payload: SeverityRequest) -> SeverityResponse:
    resolved = CATALOG.resolve_many(payload.affected_services)
    verdict = score_severity(
        reported=payload.reported_severity,
        incident_type=payload.incident_type,
        resolved_services=resolved,
        affected_jurisdictions=payload.affected_jurisdictions,
        metrics=payload.metrics,
        summary=payload.summary,
        catalog=CATALOG,
    )
    return SeverityResponse(
        reported_severity=payload.reported_severity,
        computed_severity=verdict.computed,
        severity_score=verdict.score,
        rationale=verdict.rationale,
        review_needed=verdict.review_needed,
    )


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.app_name, "version": settings.version, "docs": "/docs"}
