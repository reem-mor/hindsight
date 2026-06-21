# Postmortem: Checkout failures during Saturday peak

**Date:** 2026-06-13
**Status:** Resolved
**Authors:** Reliability on-call

## Summary
Between 20:42 and 21:51 UTC the payments gateway rejected a large share of deposit and
withdrawal attempts after an upstream PSP began returning malformed responses. Casino and
sportsbook checkout were both affected during Saturday-evening peak. Players saw "payment
could not be processed" on deposit.

## Impact
- Affected services: payments gateway, wallet, casino platform, sportsbook
- Player-facing deposit success rate fell from ~98% to ~31% for 69 minutes
- Jurisdictions affected: UKGC and NJ-DGE
- Estimated failed deposits: ~14,200

## Timeline (UTC)
- 20:42 — PSP "AcquirerEU" starts returning HTTP 200 with truncated JSON bodies
- 20:47 — Gateway error rate alert fires; on-call paged
- 21:05 — Root cause narrowed to upstream after retries fail to recover
- 21:23 — Failover to secondary acquirer initiated
- 21:51 — Deposit success rate recovers to baseline; incident closed

## Root cause
The primary acquirer pushed a change that truncated response payloads under high load.
Our gateway treated truncated-but-200 responses as retryable and retried into the same
failing path, amplifying load rather than failing over.

## Detection
Automated alert on gateway error-rate threshold.

## Action items
- [ ] Treat truncated/short-content 200s as failover-eligible, not retryable — owner: Payments-SRE — priority: high
- [ ] Add a circuit breaker per acquirer with automatic secondary failover — owner: Payments-SRE — priority: high
- [ ] Add synthetic deposit probe per acquirer — owner: Payments-SRE — priority: medium

## Notes
Detected at 20:42, mitigated at 21:51 (TTR ~69 min). No data loss. Reconciliation confirmed
no double-charges. This is the second acquirer-truncation incident this quarter.
