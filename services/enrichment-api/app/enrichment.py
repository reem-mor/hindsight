"""Enrichment engine.

Takes a Gemini extraction and adds the business/SRE intelligence that an LLM
cannot reliably know on its own:

  * severity validated against a rubric (severity.py)
  * ownership routing via the service catalog (routing.py)
  * data-sensitivity classification
  * SLO / error-budget burn estimate
  * a stable recurrence fingerprint (so repeats can be grouped in the registry)
  * routing tags that drive downstream automation (paging, escalation, review)
  * a confidence score adjusted for extraction completeness
"""
from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter
from datetime import datetime, timezone

from .config import Settings
from .models import (
    SECURITY_SENSITIVE_TYPES,
    EnrichedResult,
    GeminiResult,
    Sensitivity,
    Severity,
    SloImpact,
)
from .routing import ServiceCatalog
from .severity import score_severity

# Words stripped from root cause before fingerprinting so phrasing differences
# don't defeat recurrence detection.
_STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "and", "or", "for", "was", "were",
    "is", "due", "caused", "by", "this", "that", "with", "from", "after", "led",
    "which", "resulted", "incident", "issue", "error", "failure",
}

# Process-local recurrence memory. The Sheets registry is the durable source of
# truth; this just lets a single worker surface "we've seen this before" within
# its lifetime. Documented as ephemeral on purpose — no false persistence claims.
_seen_fingerprints: Counter[str] = Counter()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_sensitivity(
    *,
    incident_type: str,
    affected_jurisdictions: list[str],
    entities_blob: str,
    summary: str,
    cvss_score: float | None = None,
    cve_ids: list[str] | None = None,
) -> tuple[Sensitivity, list[str]]:
    """public / internal / confidential."""
    rationale: list[str] = []
    text = f"{summary} {entities_blob}".lower()

    confidential_signals = [
        (f"security-class incident ({incident_type})", incident_type in SECURITY_SENSITIVE_TYPES),
        ("PII / customer-data reference", bool(re.search(r"\bpii|customer data|personal data\b", text))),
        ("monetary / payment exposure", bool(re.search(r"\bfunds?|payment|charge|refund|monetary\b", text))),
        ("regulatory exposure", bool(re.search(r"\bregulator|ukgc|dge|fine\b", text))),
        ("multi-jurisdiction", len([j for j in affected_jurisdictions if j and j.upper() != "GLOBAL"]) >= 2),
        ("high-severity CVE (CVSS >= 7.0)", cvss_score is not None and cvss_score >= 7.0),
    ]
    triggered = [label for label, hit in confidential_signals if hit]
    if triggered:
        rationale.extend(triggered)
        return Sensitivity.CONFIDENTIAL, rationale

    # Anything touching customers/jurisdictions but not the above is internal.
    rationale.append("operational incident, no confidential markers")
    return Sensitivity.INTERNAL, rationale


def _slo_impact(primary, ttr_minutes: float | None, breach_fraction: float) -> SloImpact:
    if primary is None:
        return SloImpact()
    # Monthly error budget in minutes for the service's SLO.
    minutes_per_month = 30 * 24 * 60
    budget = round(minutes_per_month * (1 - primary.slo / 100.0), 1)
    burn = float(ttr_minutes or 0)
    burn_pct = round((burn / budget) * 100, 1) if budget > 0 else None
    breach = bool(budget > 0 and burn >= budget * breach_fraction)
    return SloImpact(
        primary_service=primary.name,
        slo_target=primary.slo,
        monthly_budget_minutes=budget,
        budget_burn_minutes=round(burn, 1),
        budget_burn_pct=burn_pct,
        budget_breach=breach,
    )


def _fingerprint(services: list[str], root_cause: str, incident_type: str) -> str:
    tokens = re.sub(r"[^a-z0-9 ]+", " ", root_cause.lower()).split()
    keywords = sorted({t for t in tokens if t not in _STOPWORDS and len(t) > 2})[:6]
    basis = "|".join([incident_type] + sorted(services) + keywords)
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()[:12]


def _adjust_confidence(g: GeminiResult, threshold: float) -> tuple[float, float, list[str]]:
    conf = g.confidence_score
    notes: list[str] = []
    penalty = 0.0
    if not g.root_cause.strip():
        penalty += 0.20
        notes.append("missing root cause (-0.20)")
    if not g.action_items:
        penalty += 0.10
        notes.append("no action items extracted (-0.10)")
    if not g.affected_services:
        penalty += 0.10
        notes.append("no affected services identified (-0.10)")
    if g.metrics_present is False:  # see property below
        penalty += 0.05
        notes.append("no timing metrics (-0.05)")
    adjusted = max(0.0, min(1.0, conf - penalty))
    if adjusted < threshold:
        notes.append(f"below review threshold {threshold}")
    return round(adjusted, 3), round(adjusted - conf, 3), notes


def enrich(g: GeminiResult, settings: Settings, catalog: ServiceCatalog) -> EnrichedResult:
    correlation = g.correlation_id or str(uuid.uuid4())

    resolved = catalog.resolve_many(g.affected_services)
    resolved_names = [e.name for e in resolved]
    teams = sorted({e.team for e in resolved}) or [catalog.team_for_type(g.incident_type)]
    department = teams[0]

    # Union of jurisdictions: those Gemini found + those the catalog implies.
    jx = set(j.upper() for j in g.affected_jurisdictions if j)
    for e in resolved:
        jx.update(e.jurisdictions)
    jx.discard("GLOBAL") if len(jx) > 1 else None
    jurisdictions = sorted(jx)

    # Severity rubric.
    verdict = score_severity(
        reported=g.severity,
        incident_type=g.incident_type,
        resolved_services=resolved,
        affected_jurisdictions=jurisdictions,
        metrics=g.metrics_obj,
        summary=g.summary,
        catalog=catalog,
        cvss_score=g.cvss_score,
    )

    # Sensitivity.
    entities_blob = " ".join(
        g.entities.people + g.entities.teams + g.entities.systems + g.entities.error_codes
    )
    sensitivity, sens_rationale = classify_sensitivity(
        incident_type=g.incident_type,
        affected_jurisdictions=jurisdictions,
        entities_blob=entities_blob,
        summary=g.summary,
        cvss_score=g.cvss_score,
        cve_ids=g.cve_ids,
    )

    # SLO impact — driven by the most critical resolved service.
    primary = None
    if resolved:
        order = {"critical": 4, "high": 3, "standard": 2, "internal": 1}
        primary = max(resolved, key=lambda e: order.get(e.tier, 1))
    slo = _slo_impact(primary, g.metrics_obj.ttr_minutes, settings.budget_breach_fraction)

    # Recurrence.
    fp = _fingerprint(resolved_names or g.affected_services, g.root_cause, g.incident_type)
    _seen_fingerprints[fp] += 1
    seen_count = _seen_fingerprints[fp]

    # Confidence.
    adj_conf, conf_delta, conf_notes = _adjust_confidence(g, settings.review_confidence_threshold)

    # Action-item quality.
    total_actions = len(g.action_items)
    no_owner = sum(1 for a in g.action_items if not (a.owner and a.owner.strip()))
    open_p0 = sum(1 for a in g.action_items if (a.priority or "").upper() == "P0")

    # Routing tags drive downstream automation in n8n.
    tags: list[str] = ["auto-filed"]
    if verdict.computed in {verdict.computed.SEV1, verdict.computed.SEV2}:
        tags.append("exec-escalation")
    if verdict.computed == verdict.computed.SEV1:
        tags.append("page-oncall")
    if len(jurisdictions) >= 2:
        tags.append("regulatory-review")
    if verdict.review_needed:
        tags.append("severity-review")
    if adj_conf < settings.review_confidence_threshold:
        tags.append("needs-review")
    if no_owner > 0:
        tags.append("unowned-actions")
    if slo.budget_breach:
        tags.append("budget-breach")
    if seen_count > 1:
        tags.append("repeat-offender")
    if g.blameless_quality == "poor":
        tags.append("blameless-coaching")
    # De-dup while preserving order.
    tags = list(dict.fromkeys(tags))

    # Single-value routing decision (assignment rubric: escalate / needs-review /
    # auto-approved), derived from the richer tag set.
    if verdict.computed == Severity.SEV1 or (g.cvss_score is not None and g.cvss_score >= 9.0):
        routing_tag = "escalate"
    elif "needs-review" in tags or "severity-review" in tags:
        routing_tag = "needs-review"
    else:
        routing_tag = "auto-approved"

    return EnrichedResult(
        document_id=str(uuid.uuid4()),
        processed_at=_now_iso(),
        correlation_id=correlation,
        incident_title=g.incident_title,
        summary=g.summary[:500],
        reported_severity=g.severity,
        computed_severity=verdict.computed,
        severity_score=verdict.score,
        severity_rationale=verdict.rationale,
        severity_review_needed=verdict.review_needed,
        department=department,
        routed_teams=teams,
        affected_services_resolved=resolved_names,
        affected_jurisdictions=jurisdictions,
        sensitivity=sensitivity,
        sensitivity_rationale=sens_rationale,
        slo_impact=slo,
        recurrence_fingerprint=fp,
        recurrence_seen_count=seen_count,
        cvss_score=g.cvss_score,
        cve_ids=g.cve_ids,
        routing_tags=tags,
        routing_tag=routing_tag,
        action_item_total=total_actions,
        action_items_without_owner=no_owner,
        open_p0_actions=open_p0,
        confidence_score=adj_conf,
        confidence_delta=conf_delta,
        confidence_notes=conf_notes,
    )


def reset_recurrence_memory() -> None:
    """Test helper — clears the ephemeral recurrence counter."""
    _seen_fingerprints.clear()
