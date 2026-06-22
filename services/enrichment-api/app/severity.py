"""Severity rubric.

Rather than trusting the LLM's severity label, HINDSIGHT recomputes severity
from objective signals (service tier, jurisdiction breadth, customer-impact
language, downtime). When the rubric and the LLM disagree, the record is flagged
for human review — a guardrail against both LLM under-calling and on-call
adrenaline over-calling.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .models import SECURITY_FLOOR_TYPES, IncidentMetrics, Severity
from .routing import ServiceCatalog, ServiceEntry

# Signals that escalate severity regardless of the reported label.
_HIGH_IMPACT_PATTERNS = [
    r"\bdata (loss|breach|leak)\b",
    r"\bbreach\b",
    r"\bpii\b",
    r"\bregulator(y)?\b",
    r"\bfine[sd]?\b",
    r"\bfunds?\b",
    r"\bmonetary\b",
    r"\bdouble[- ]charg",
    r"\brevenue\b",
    r"\bpayment[s]? (fail|down|unavailable)",
    r"\bcomplete (outage|down)",
    r"\btotal outage\b",
    r"\ball (users|players|customers)\b",
]

_TIER_SCORE = {"critical": 4, "high": 3, "standard": 2, "internal": 1}
_SEVERITY_RANK = {Severity.SEV4: 4, Severity.SEV3: 3, Severity.SEV2: 2, Severity.SEV1: 1}


@dataclass
class SeverityVerdict:
    computed: Severity
    score: int
    rationale: list[str]
    review_needed: bool


def _impact_hits(text: str) -> list[str]:
    text = (text or "").lower()
    hits = []
    for pat in _HIGH_IMPACT_PATTERNS:
        if re.search(pat, text):
            hits.append(pat.strip("\\b").replace("\\b", "").replace("(", "").replace(")", ""))
    return hits


def _cvss_band(cvss: float) -> Severity | None:
    """Map a CVSS base score to the minimum severity it justifies."""
    if cvss >= 9.0:
        return Severity.SEV1
    if cvss >= 7.0:
        return Severity.SEV2
    if cvss >= 4.0:
        return Severity.SEV3
    return None


def score_severity(
    *,
    reported: Severity,
    incident_type: str,
    resolved_services: list[ServiceEntry],
    affected_jurisdictions: list[str],
    metrics: IncidentMetrics,
    summary: str,
    catalog: ServiceCatalog,  # reserved for future tier weighting tweaks
    cvss_score: float | None = None,
) -> SeverityVerdict:
    score = 0
    rationale: list[str] = []

    # 1. Highest tier among affected services.
    if resolved_services:
        top_tier = max(resolved_services, key=lambda e: _TIER_SCORE.get(e.tier, 1))
        tier_pts = _TIER_SCORE.get(top_tier.tier, 1)
        score += tier_pts
        rationale.append(f"highest-tier service '{top_tier.name}' is {top_tier.tier} (+{tier_pts})")
    else:
        rationale.append("no catalogued service matched (+0)")

    # 2. Jurisdiction breadth — multi-jurisdiction is a regulatory amplifier.
    real_jx = [j for j in affected_jurisdictions if j and j.upper() != "GLOBAL"]
    if len(real_jx) >= 2:
        score += 3
        rationale.append(f"multi-jurisdiction impact ({', '.join(real_jx)}) (+3)")
    elif len(real_jx) == 1:
        score += 1
        rationale.append(f"single-jurisdiction impact ({real_jx[0]}) (+1)")

    # 3. Customer-impact language in the summary.
    hits = _impact_hits(summary)
    if hits:
        pts = min(len(hits) * 2, 4)
        score += pts
        rationale.append(f"high-impact language ({len(hits)} signal/s) (+{pts})")

    # 4. Downtime magnitude.
    ttr = metrics.ttr_minutes or 0
    if ttr >= 120:
        score += 3
        rationale.append(f"downtime {ttr:.0f} min ≥ 2h (+3)")
    elif ttr >= 30:
        score += 2
        rationale.append(f"downtime {ttr:.0f} min ≥ 30m (+2)")
    elif ttr > 0:
        score += 1
        rationale.append(f"downtime {ttr:.0f} min (+1)")

    # 5. Security / active-compromise incidents carry an inherent floor.
    if incident_type in SECURITY_FLOOR_TYPES:
        score += 3
        rationale.append(f"incident type '{incident_type}' carries regulatory weight (+3)")

    # 6. CVSS (cyber hybrid): a scored CVE adds rubric weight AND, below, floors
    #    the band — a critical vuln is SEV1 even when no internal service matched.
    cvss_floor: Severity | None = None
    if cvss_score is not None and cvss_score > 0:
        cvss_floor = _cvss_band(cvss_score)
        cvss_pts = {Severity.SEV1: 5, Severity.SEV2: 3, Severity.SEV3: 1}.get(cvss_floor, 0)
        if cvss_pts:
            score += cvss_pts
            rationale.append(
                f"CVSS {cvss_score:.1f} ({cvss_floor.value}-class) (+{cvss_pts})"
            )
        else:
            rationale.append(f"CVSS {cvss_score:.1f} low (+0)")

    # Map score → severity band.
    if score >= 9:
        computed = Severity.SEV1
    elif score >= 6:
        computed = Severity.SEV2
    elif score >= 3:
        computed = Severity.SEV3
    else:
        computed = Severity.SEV4

    # CVSS floor: never rate a scored vulnerability lower than its CVSS band.
    if cvss_floor is not None and _SEVERITY_RANK[cvss_floor] < _SEVERITY_RANK[computed]:
        computed = cvss_floor
        rationale.append(f"severity floored to {cvss_floor.value} by CVSS {cvss_score:.1f}")

    # Review needed when rubric and reported label differ by >= 1 band.
    delta = abs(_SEVERITY_RANK[computed] - _SEVERITY_RANK[reported])
    review_needed = delta >= 1
    if review_needed:
        direction = "higher" if _SEVERITY_RANK[computed] < _SEVERITY_RANK[reported] else "lower"
        rationale.append(
            f"rubric ({computed.value}) is {direction} than reported ({reported.value}) → review"
        )

    return SeverityVerdict(
        computed=computed, score=score, rationale=rationale, review_needed=review_needed
    )
