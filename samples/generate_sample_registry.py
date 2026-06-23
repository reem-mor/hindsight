#!/usr/bin/env python3
"""Generate cyber-focused HINDSIGHT incident registry for the dashboard demo."""

from __future__ import annotations

import hashlib
import json
import random
from datetime import datetime, timedelta, timezone

random.seed(17)

SERVICES = {
    "siem": ("SecOps", "high", ["GLOBAL"]),
    "endpoint-security": ("SecOps", "high", ["GLOBAL"]),
    "vulnerability-scanner": ("SecOps", "standard", ["GLOBAL"]),
    "auth": ("Identity-Sec", "high", ["GLOBAL"]),
    "network": ("NetSec", "high", ["GLOBAL"]),
    "email-gateway": ("SecOps", "standard", ["GLOBAL"]),
    "internal-tooling": ("SecOps", "internal", ["GLOBAL"]),
}

WEIGHTS = {
    "siem": 3,
    "endpoint-security": 2,
    "vulnerability-scanner": 3,
    "auth": 2,
    "network": 2,
    "email-gateway": 2,
    "internal-tooling": 2,
}

TYPES = [
    "security",
    "data-incident",
    "vulnerability-scan",
    "malware",
    "phishing",
    "intrusion",
    "ddos",
    "other",
]

ROOT_CAUSES = {
    "siem": "Brute-force login attempts from distributed botnet IPs",
    "endpoint-security": "Malware beacon detected on finance workstation",
    "vulnerability-scanner": "Critical OpenSSL RCE flagged on perimeter hosts",
    "auth": "Credential stuffing against SSO login endpoints",
    "network": "Volumetric DDoS against edge ingress",
    "email-gateway": "Phishing campaign impersonating IT helpdesk",
    "internal-tooling": "Unpatched dependency in CI runner image",
}

TITLES = {
    "siem": "SIEM alert — brute force intrusion",
    "endpoint-security": "EDR malware detection",
    "vulnerability-scanner": "Critical vulnerability scan finding",
    "auth": "Authentication anomaly",
    "network": "Network perimeter attack",
    "email-gateway": "Phishing email campaign",
    "internal-tooling": "Internal tooling vulnerability",
}


def fingerprint(service: str, root_cause: str, itype: str) -> str:
    basis = f"{itype}|{service}|{root_cause.lower()}"
    return hashlib.sha1(basis.encode()).hexdigest()[:12]


def severity_for(service: str, itype: str, ttr: int, cvss: float | None) -> str:
    tier = SERVICES[service][1]
    score = {"high": 3, "standard": 2, "internal": 1}[tier]
    if itype in ("security", "data-incident", "intrusion", "malware"):
        score += 3
    if itype == "vulnerability-scan" and cvss is not None:
        if cvss >= 9.0:
            score = max(score, 9)
        elif cvss >= 4.0:
            score = max(score, 3)
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
    n = 18
    repeat_plan = ["siem", "vulnerability-scanner", "siem"]

    for i in range(n):
        days_ago = int((n - i) * (90 / n) + random.uniform(-2, 2))
        ts = now - timedelta(days=max(days_ago, 0), hours=random.randint(0, 23))

        if i < len(repeat_plan):
            service = repeat_plan[i]
            itype = "intrusion" if service == "siem" else "vulnerability-scan"
        else:
            pool = list(SERVICES)
            service = random.choices(pool, weights=[WEIGHTS[s] for s in pool], k=1)[0]
            itype = random.choice(TYPES)

        team, tier, jx = SERVICES[service]
        trend = max(0.4, days_ago / 90)
        ttr = int(random.randint(5, 90) * (0.5 + 0.7 * trend))
        cvss = None
        cve_ids: list[str] = []
        if itype == "vulnerability-scan":
            cvss = round(random.choice([2.1, 5.6, 7.4, 9.8]), 1)
            if cvss >= 4.0:
                cve_ids = [f"CVE-2026-{random.randint(10000, 99999)}"]
        sev = severity_for(service, itype, ttr, cvss)

        root = ROOT_CAUSES[service]
        fp = fingerprint(service, root, itype)
        action_total = random.randint(1, 4)
        unowned = random.randint(0, max(0, action_total - 1))

        sensitivity = "confidential" if (
            itype in ("security", "data-incident", "intrusion", "malware", "phishing")
            or (cvss is not None and cvss >= 7.0)
        ) else "internal"

        routing_tag = "escalate" if sev == "SEV1" or (cvss is not None and cvss >= 9.0) else (
            "needs-review" if unowned or sev == "SEV2" else "auto-approved"
        )

        records.append({
            "document_id": f"inc-{ts.strftime('%Y%m%d')}-{i:03d}",
            "filename": f"{service.replace('-', '_')}_{ts.strftime('%Y%m%d')}.md",
            "file_type": "md",
            "processed_at": ts.isoformat(),
            "classification": itype,
            "department": team,
            "sentiment": random.choice(["neutral", "neutral", "negative"]),
            "confidence_score": round(random.uniform(0.72, 0.95), 2),
            "summary": f"{root}. Impact on {service}.",
            "routing_tag": routing_tag,
            "sensitivity": sensitivity,
            "action_items": f"P1: investigate ({team}); P2: document",
            "cvss_score": cvss,
            "cve_ids": ", ".join(cve_ids) if cve_ids else "",
            "computed_severity": sev,
            "incident_title": f"{TITLES[service]} ({ts.strftime('%b %d')})",
            "recurrence_fingerprint": fp,
            "ttr_minutes": ttr,
            "status": random.choice(["resolved", "resolved", "monitoring"]),
        })

    records.sort(key=lambda r: r["processed_at"])
    return records


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
