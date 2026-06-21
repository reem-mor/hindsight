# Postmortem: Stale internal reporting dashboards

**Date:** 2026-05-28
**Status:** Resolved
**Authors:** Data on-call

## Summary
The nightly ETL that refreshes internal reporting dashboards failed silently for two nights,
so analysts were looking at two-day-old numbers. There was no player-facing impact — this
affected internal reporting only. The failure was a schema change in an upstream table that
the ETL did not tolerate.

## Impact
- Affected services: reporting-db, internal-tooling
- Internal dashboards stale by ~48 hours
- Jurisdictions affected: none (internal)
- No customer or regulatory impact

## Timeline (UTC)
- 02:10 (Mon) — ETL job fails; no alert configured on this job
- 02:10 (Tue) — ETL fails again
- 10:30 (Tue) — analyst notices figures haven't moved and reports it
- 11:15 (Tue) — ETL patched to handle the new column; backfilled

## Root cause
An upstream table added a non-nullable column. The ETL's insert did not handle the new
column and errored out. The job had no failure alerting, so two runs failed before a human
noticed. To be blunt, Jordan from the data team shipped the upstream schema change without
telling anyone, which is why this slipped through.

## Detection
Manual — an analyst noticed stale numbers.

## Action items
- [ ] Add failure alerting to the nightly ETL job — owner: Data-Platform — priority: high
- [ ] Make the ETL tolerant of additive schema changes — owner: Data-Platform — priority: medium
- [ ] Add a schema-change checklist for upstream tables — owner: Data-Platform — priority: medium

## Notes
Detected ~32h after first failure (TTR for the fix ~45 min once seen). Low severity, internal
only — but the detection gap is the real lesson here.
