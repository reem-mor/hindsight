"""API contracts (Pydantic v2).

The input model mirrors what Gemini returns for a postmortem; the output model
is the enriched record that n8n appends to the Sheets incident registry and
feeds into the Gmail notification.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Severity(str, Enum):
    SEV1 = "SEV1"
    SEV2 = "SEV2"
    SEV3 = "SEV3"
    SEV4 = "SEV4"


class Sensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"


# --------------------------------------------------------------------------- #
# Input — Gemini extraction result
# --------------------------------------------------------------------------- #
class Entities(BaseModel):
    people: list[str] = Field(default_factory=list)
    teams: list[str] = Field(default_factory=list)
    systems: list[str] = Field(default_factory=list)
    dates: list[str] = Field(default_factory=list)
    error_codes: list[str] = Field(default_factory=list)


class ActionItem(BaseModel):
    action: str = ""
    owner: Optional[str] = None
    priority: Optional[str] = None  # P0 | P1 | P2


class IncidentMetrics(BaseModel):
    detected_at: Optional[str] = None
    resolved_at: Optional[str] = None
    ttd_minutes: Optional[float] = Field(default=None, description="Time to detect")
    ttr_minutes: Optional[float] = Field(default=None, description="Time to resolve (downtime)")
    customer_impact: Optional[str] = None


class GeminiResult(BaseModel):
    """What the Gemini node hands to /enrich."""

    incident_title: str = "Untitled incident"
    summary: str = ""
    severity: Severity = Severity.SEV3
    incident_type: str = "other"
    status: str = "resolved"
    affected_services: list[str] = Field(default_factory=list)
    affected_jurisdictions: list[str] = Field(default_factory=list)
    root_cause: str = ""
    trigger: str = ""
    detection_method: str = ""
    entities: Entities = Field(default_factory=Entities)
    action_items: list[ActionItem] = Field(default_factory=list)
    contributing_factors: list[str] = Field(default_factory=list)
    sentiment: str = "neutral"
    blameless_quality: str = "unknown"  # good | acceptable | poor | unknown
    confidence_score: float = 0.5
    filename: Optional[str] = None
    correlation_id: Optional[str] = None

    metrics: IncidentMetrics = Field(default_factory=IncidentMetrics)

    @field_validator("confidence_score")
    @classmethod
    def _clamp_conf(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @property
    def metrics_obj(self) -> IncidentMetrics:
        return self.metrics

    @property
    def metrics_present(self) -> bool:
        m = self.metrics
        return any(
            [m.detected_at, m.resolved_at, m.ttd_minutes is not None, m.ttr_minutes is not None]
        )


# --------------------------------------------------------------------------- #
# Output — enriched record
# --------------------------------------------------------------------------- #
class SloImpact(BaseModel):
    primary_service: Optional[str] = None
    slo_target: Optional[float] = None
    monthly_budget_minutes: Optional[float] = None
    budget_burn_minutes: Optional[float] = None
    budget_burn_pct: Optional[float] = None
    budget_breach: bool = False


class EnrichedResult(BaseModel):
    document_id: str
    processed_at: str
    correlation_id: str

    incident_title: str
    summary: str

    # Severity: Gemini's call vs. the rubric's call.
    reported_severity: Severity
    computed_severity: Severity
    severity_score: int
    severity_rationale: list[str]
    severity_review_needed: bool

    department: str
    routed_teams: list[str]
    affected_services_resolved: list[str]
    affected_jurisdictions: list[str]

    sensitivity: Sensitivity
    sensitivity_rationale: list[str]

    slo_impact: SloImpact
    recurrence_fingerprint: str
    recurrence_seen_count: int

    routing_tags: list[str]

    action_item_total: int
    action_items_without_owner: int
    open_p0_actions: int

    confidence_score: float
    confidence_delta: float
    confidence_notes: list[str]


# --------------------------------------------------------------------------- #
# Aux endpoints
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    uptime_seconds: float
    catalog_services: int


class CategoriesResponse(BaseModel):
    severities: list[str]
    incident_types: list[str]
    sensitivities: list[str]
    teams: list[str]


class SensitivityRequest(BaseModel):
    incident_type: str = "other"
    affected_jurisdictions: list[str] = Field(default_factory=list)
    entities: Entities = Field(default_factory=Entities)
    summary: str = ""


class SensitivityResponse(BaseModel):
    sensitivity: Sensitivity
    rationale: list[str]


class SeverityRequest(BaseModel):
    reported_severity: Severity = Severity.SEV3
    incident_type: str = "other"
    affected_services: list[str] = Field(default_factory=list)
    affected_jurisdictions: list[str] = Field(default_factory=list)
    metrics: IncidentMetrics = Field(default_factory=IncidentMetrics)
    summary: str = ""


class SeverityResponse(BaseModel):
    reported_severity: Severity
    computed_severity: Severity
    severity_score: int
    rationale: list[str]
    review_needed: bool
