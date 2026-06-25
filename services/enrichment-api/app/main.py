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
    INCIDENT_TYPES,
    CategoriesResponse,
    CompareRequest,
    CompareResponse,
    DigestPreviewRequest,
    DigestPreviewResponse,
    EnrichedResult,
    GeminiResult,
    HealthResponse,
    IndexRequest,
    SearchHitResponse,
    SearchRequest,
    SearchResponse,
    SensitivityRequest,
    SensitivityResponse,
    Severity,
    SeverityRequest,
    SeverityResponse,
)
from .routing import ServiceCatalog
from .severity import score_severity
from .compare import call_gemini_pro_json, compare_extractions
from .digest import aggregate_digest, build_digest_html, filter_last_24h
from .search_store import get_vector_store

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
        incident_types=INCIDENT_TYPES,
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
    # BON-5: index enriched document for semantic search (in-memory or Supabase)
    try:
        text = " ".join(
            filter(
                None,
                [
                    payload.summary,
                    payload.incident_title,
                    payload.root_cause,
                    " ".join(payload.affected_services),
                ],
            )
        )
        if text.strip():
            store = get_vector_store()
            store.upsert(
                document_id=result.document_id,
                filename=str(getattr(payload, "source_filename", "") or ""),
                classification=payload.incident_type,
                department=result.department,
                sensitivity=result.sensitivity.value,
                routing_tag=result.routing_tag,
                summary=result.summary[:500],
                processed_at=result.processed_at,
                text=text,
            )
    except Exception:  # noqa: BLE001
        logger.warning("search index upsert skipped", exc_info=True)
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
        cvss_score=payload.cvss_score,
        cve_ids=payload.cve_ids,
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
        cvss_score=payload.cvss_score,
    )
    return SeverityResponse(
        reported_severity=payload.reported_severity,
        computed_severity=verdict.computed,
        severity_score=verdict.score,
        rationale=verdict.rationale,
        review_needed=verdict.review_needed,
    )


@app.post("/search", response_model=SearchResponse, tags=["bonus"])
def search_endpoint(payload: SearchRequest) -> SearchResponse:
    store = get_vector_store()
    hits = store.search(payload.query, top_k=payload.top_k, min_similarity=payload.min_similarity)
    return SearchResponse(
        query=payload.query,
        hits=[
            SearchHitResponse(
                document_id=h.document_id,
                filename=h.filename,
                classification=h.classification,
                summary=h.summary,
                routing_tag=h.routing_tag,
                sensitivity=h.sensitivity,
                similarity=h.similarity,
            )
            for h in hits
        ],
    )


@app.post("/index", tags=["bonus"])
def index_endpoint(payload: IndexRequest) -> dict:
    store = get_vector_store()
    store.upsert(
        document_id=payload.document_id,
        filename=payload.filename,
        classification=payload.classification,
        department=payload.department,
        sensitivity=payload.sensitivity,
        routing_tag=payload.routing_tag,
        summary=payload.summary,
        processed_at=payload.processed_at,
        text=payload.text,
    )
    _METRICS["hindsight_documents_indexed_total"] += 1
    return {"status": "indexed", "document_id": payload.document_id}


@app.post("/compare", response_model=CompareResponse, tags=["bonus"])
def compare_endpoint(payload: CompareRequest) -> CompareResponse:
    pro = payload.pro
    if pro is None and payload.prompt_text:
        pro = call_gemini_pro_json(payload.prompt_text)
    if pro is None:
        pro = {}
    report = compare_extractions(payload.flash, pro)
    return CompareResponse(**report)


@app.post("/digest/preview", response_model=DigestPreviewResponse, tags=["bonus"])
def digest_preview_endpoint(payload: DigestPreviewRequest) -> DigestPreviewResponse:
    recent = filter_last_24h(payload.rows, window_hours=payload.window_hours)
    agg = aggregate_digest(recent)
    html = build_digest_html(agg, window_hours=payload.window_hours)
    subject = f"HINDSIGHT daily digest — {agg.get('total', 0)} incidents (last {payload.window_hours}h)"
    return DigestPreviewResponse(aggregate=agg, html=html, subject=subject)


@app.get("/", include_in_schema=False)
def root() -> dict:
    return {"service": settings.app_name, "version": settings.version, "docs": "/docs"}
