#!/usr/bin/env python3
"""Generate a realistic HINDSIGHT incident registry for the dashboard demo.

Produces records shaped exactly like the rows the n8n workflow appends to the
Google Sheets registry (i.e. the /enrich output, flattened). Seeded for
reproducibility, with a gently improving MTTR trend and a few recurring
fingerprints so the dashboard's "repeat-offender" detection has something to
show.

    python generate_sample_registry.py > ../dashboard/data/incidents.sample.json
"""
from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone

random.seed(17)

SERVICES = {
    "payments-gateway": ("Payments-SRE", "critical", ["UKGC", "NJ-DGE", "MGM"]),
    "wallet": ("Payments-SRE", "critical", ["UKGC", "NJ-DGE", "MGM"]),
    "casino-platform": ("Platform-SRE", "critical", ["UKGC", "NJ-DGE"]),
    "sportsbook": ("Sportsbook-SRE", "critical", ["UKGC", "NJ-DGE", "MGM"]),
    "identity": ("Identity-SRE", "critical", ["GLOBAL"]),
    "kyc": ("Compliance-Eng", "high", ["UKGC", "NJ-DGE"]),
    "geo-compliance": ("Compliance-Eng", "critical", ["NJ-DGE", "MGM"]),
    "promotions": ("Engagement-Eng", "high", ["UKGC", "NJ-DGE"]),
    "edge-cdn": ("Platform-SRE", "high", ["GLOBAL"]),
    "reporting-db": ("Data-Platform", "high", ["UKGC", "NJ-DGE"]),
    "notifications": ("Engagement-Eng", "standard", ["GLOBAL"]),
    "internal-tooling": ("DevEx", "internal", ["GLOBAL"]),
}

# Selection weights — a real estate sees far more minor incidents than majors.
WEIGHTS = {
    "payments-gateway": 1, "wallet": 1, "casino-platform": 2, "sportsbook": 2,
    "identity": 2, "kyc": 2, "geo-compliance": 1, "promotions": 3,
    "edge-cdn": 3, "reporting-db": 3, "notifications": 4, "internal-tooling": 4,
}

TYPES = [
    "outage", "degradation", "deployment-failure", "dependency-failure",
    "capacity", "configuration", "security", "data-incident",
]

ROOT_CAUSES = {
    "payments-gateway": "Connection pool exhaustion in the PSP adapter",
    "wallet": "Ledger write lock contention under peak load",
    "casino-platform": "Game RNG service OOM after memory leak",
    "sportsbook": "Odds feed provider timeout cascaded to trading",
    "identity": "Session store failover did not promote a replica",
    "kyc": "Third-party verification vendor returned 5xx",
    "geo-compliance": "Stale geolocation ruleset blocked valid players",
    "promotions": "Bonus calculation overflow on a malformed campaign",
    "edge-cdn": "WAF rule update dropped legitimate traffic",
    "reporting-db": "Nightly ETL deadlock delayed regulatory reporting",
    "notifications": "SMS provider rate-limited outbound messages",
    "internal-tooling": "CI runner disk filled and stalled the pipeline",
}

TITLES = {
    "payments-gateway": "Payments gateway outage",
    "wallet": "Wallet balance errors",
    "casino-platform": "Casino platform degradation",
    "sportsbook": "Sportsbook trading halt",
    "identity": "Login failures",
    "kyc": "KYC onboarding delays",
    "geo-compliance": "Geo-gate false rejections",
    "promotions": "Bonus engine miscalculation",
    "edge-cdn": "Edge traffic drop",
    "reporting-db": "Regulatory reporting delay",
    "notifications": "Notification delivery delay",
    "internal-tooling": "CI pipeline stall",
}


def fingerprint(service: str, root_cause: str, itype: str) -> str:
    basis = f"{itype}|{service}|{root_cause.lower()}"
    return hashlib.sha1(basis.encode()).hexdigest()[:12]


def severity_for(service: str, itype: str, jx: list[str], ttr: int) -> str:
    tier = SERVICES[service][1]
    score = {"critical": 4, "high": 3, "standard": 2, "internal": 1}[tier]
    real_jx = [j for j in jx if j != "GLOBAL"]
    score += 3 if len(real_jx) >= 2 else (1 if real_jx else 0)
    if itype in ("security", "data-incident"):
        score += 3
    score += 3 if ttr >= 120 else (2 if ttr >= 30 else 1 if ttr else 0)
    if score >= 9:
        return "SEV1"
    if score >= 6:
        return "SEV2"
    if score >= 3:
        return "SEV3"
    return "SEV4"


def build() -> list[dict]:
    now = datetime.now(timezone.utc)
    records: list[dict] = []
    n = 22
    # Recurring offenders: a couple of services repeat the same root cause.
    repeat_plan = ["sportsbook", "edge-cdn", "sportsbook"]

    for i in range(n):
        days_ago = int((n - i) * (100 / n) + random.uniform(-2, 2))
        ts = now - timedelta(days=max(days_ago, 0), hours=random.randint(0, 23))

        if i < len(repeat_plan):
            service = repeat_plan[i]
            itype = "dependency-failure" if service == "sportsbook" else "configuration"
        else:
            pool = list(SERVICES)
            service = random.choices(pool, weights=[WEIGHTS[s] for s in pool], k=1)[0]
            itype = random.choice(TYPES)

        team, tier, jx = SERVICES[service]
        # MTTR gently improves over time (earlier incidents take longer).
        trend = max(0.4, days_ago / 100)
        base = random.randint(5, 110)
        ttr = int(base * (0.5 + 0.7 * trend))
        sev = severity_for(service, itype, jx, ttr)

        root = ROOT_CAUSES[service]
        fp = fingerprint(service, root, itype)
        action_total = random.randint(1, 5)
        unowned = random.randint(0, max(0, action_total - 1))

        sensitivity = "confidential" if (
            service in ("payments-gateway", "wallet", "kyc", "geo-compliance")
            or itype in ("security", "data-incident")
            or len([j for j in jx if j != "GLOBAL"]) >= 2
        ) else "internal"

        tags = ["auto-filed"]
        if sev in ("SEV1", "SEV2"):
            tags.append("exec-escalation")
        if sev == "SEV1":
            tags.append("page-oncall")
        if len([j for j in jx if j != "GLOBAL"]) >= 2:
            tags.append("regulatory-review")
        if unowned:
            tags.append("unowned-actions")

        records.append({
            "document_id": f"inc-{ts.strftime('%Y%m%d')}-{i:03d}",
            "processed_at": ts.isoformat(),
            "incident_title": f"{TITLES[service]} ({ts.strftime('%b %d')})",
            "incident_type": itype,
            "reported_severity": sev,
            "computed_severity": sev,
            "department": team,
            "affected_services_resolved": [service],
            "affected_jurisdictions": [j for j in jx if j != "GLOBAL"] or ["GLOBAL"],
            "sensitivity": sensitivity,
            "ttr_minutes": ttr,
            "status": random.choice(["resolved", "resolved", "resolved", "monitoring"]),
            "recurrence_fingerprint": fp,
            "routing_tags": tags,
            "action_item_total": action_total,
            "action_items_without_owner": unowned,
            "summary": f"{root}. Impact on {service} across {', '.join(j for j in jx if j!='GLOBAL') or 'global'}.",
        })

    records.sort(key=lambda r: r["processed_at"])
    return records


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
