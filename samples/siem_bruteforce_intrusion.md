# SIEM Alert Export — Credential brute force against identity service

**Alert time:** 2026-06-20T02:14:00Z
**Status:** Resolved
**Source:** Splunk ES correlation search "Excessive failed auth + success from new ASN"
**Author:** SecOps on-call (Tier 2)

## Summary
A Splunk Enterprise Security correlation search fired on a distributed credential
brute-force against the identity service. ~140k failed logins from 1,900 IPs across a
single hosting ASN preceded three successful logins to player accounts from the same ASN.
The three sessions were terminated and the accounts locked pending reset. This is treated
as an intrusion attempt with limited account takeover.

## Impact
- Affected services: identity
- Affected jurisdictions: GLOBAL
- Incident type: intrusion (credential stuffing -> limited ATO)
- 3 player accounts confirmed accessed; no funds movement detected
- No CVE; this is an active-threat / abuse incident, not a software vulnerability

## Timeline (UTC)
- 02:14 — Correlation search fires on failed-auth spike + anomalous-ASN success
- 02:19 — SecOps on-call paged; ASN identified as a bulletproof hosting range
- 02:31 — ASN range rate-limited at the edge; affected sessions revoked
- 02:58 — 3 accessed accounts locked, password reset forced; incident closed

## Root cause
Credential stuffing using a leaked third-party password list. Affected accounts had no MFA
enabled, and the identity service lacked per-ASN velocity limits on the login endpoint.

## Detection
Splunk ES correlation search (SIEM), not customer report.

## Action items
- [ ] Enforce step-up MFA on login from new ASNs — owner: Identity-SRE — priority: P0
- [ ] Add per-ASN and per-credential velocity limits at the edge — owner: SecOps — priority: P1
- [ ] Notify the 3 affected players per breach-notification policy — owner: Compliance-Eng — priority: P1

## Notes
Customer-account access occurred, so treat as confidential. Detected at 02:14, contained by
02:58 (TTR ~44 min). Recommend a sweep for the leaked credential list across all accounts.
