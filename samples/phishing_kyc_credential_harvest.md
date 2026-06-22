# Phishing Incident Report — Spoofed KYC portal harvesting staff credentials

**Reported:** 2026-06-21T09:05:00Z
**Status:** Monitoring
**Source:** Staff report + email security gateway retro-hunt
**Author:** SecOps

## Summary
A phishing campaign impersonating the internal KYC review portal targeted compliance staff.
A look-alike domain (kyc-review-portal[.]com) hosted a credential-harvesting page styled on
the real onboarding tool. Two compliance analysts entered credentials before the domain was
blocked; both accounts were disabled and reset. No evidence the credentials were used, but
the KYC tool handles customer identity documents.

## Impact
- Affected services: kyc
- Affected jurisdictions: UKGC, NJ-DGE
- Incident type: phishing
- 2 staff accounts entered credentials; no successful login from attacker observed yet
- Customer KYC/PII data is in scope if credentials were used

## Timeline (UTC)
- 08:40 — Phishing emails delivered to ~30 compliance mailboxes
- 09:05 — An analyst reports the suspicious email; SecOps begins triage
- 09:20 — Look-alike domain confirmed malicious; blocked at the proxy and email gateway
- 09:35 — 2 affected accounts disabled and credentials reset; monitoring continues

## Root cause
A convincing look-alike domain plus the absence of phishing-resistant MFA on the KYC tool
allowed credential entry. The email gateway did not flag the new domain in time.

## Detection
Staff report, corroborated by an email security gateway retro-hunt.

## Action items
- [ ] Roll out FIDO2 phishing-resistant MFA to all compliance staff — owner: SecOps — priority: P0
- [ ] Add the look-alike domain pattern to proxy/email bl* lists and monitor for typosquats — owner: SecOps — priority: P1
- [ ] Review KYC access logs for the 2 accounts over the exposure window — owner: Compliance-Eng — priority: P1

## Notes
KYC/PII exposure potential -> treat as confidential. Status monitoring while access logs are
reviewed. No CVE involved; this is a social-engineering incident.
