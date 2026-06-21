# Postmortem: Elevated login latency after identity deploy

**Date:** 2026-06-05
**Status:** Monitoring
**Authors:** Identity on-call

## Summary
A routine identity-service deployment introduced a synchronous call to the KYC service on
the login hot path. Under normal load this added 300–900 ms to sign-in; p95 login latency
roughly tripled for about 40 minutes until the change was rolled back. No sign-ins failed
outright, but the experience degraded noticeably.

## Impact
- Affected services: identity, kyc
- p95 login latency 410 ms → ~1.3 s for ~40 minutes
- Jurisdictions affected: UKGC
- No failed logins; degraded experience only

## Timeline (UTC)
- 09:12 — identity v4.18 rolled out
- 09:19 — login latency alert (p95) fires
- 09:34 — change identified as the new synchronous KYC lookup
- 09:52 — v4.18 rolled back; latency returns toward baseline

## Root cause
The KYC enrichment, intended to run asynchronously after login, was placed inline on the
authentication path. The dependency is slower and less available than the auth store, so its
latency leaked directly into sign-in.

## Detection
Automated p95 latency alert on the login endpoint.

## Action items
- [ ] Move KYC enrichment off the login hot path (async/after-auth) — owner: Identity-SRE — priority: high
- [ ] Add a latency budget check to the identity deploy gate — owner: Identity-SRE — priority: medium
- [ ] Document the login hot-path dependencies — owner: — priority: low

## Notes
Detected at 09:19, mitigated at 09:52 (TTR ~33 min). Watching p95 over the next 24h before
marking fully resolved.
