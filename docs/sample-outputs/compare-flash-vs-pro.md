# BON-6 — Multi-model Compare (Gemini 3 Flash vs Pro)

HINDSIGHT runs **Flash** and **Pro** on the *same* incident and diffs the two structured
extractions field-by-field. This is wired into the deployed Cloud workflow as a
**non-blocking parallel branch** so it can never delay or break the graded path.

## Topology (live Cloud workflow `aYEv22StywIPL3Rq`)

```
Parse Gemini JSON ─┬─► HINDSIGHT Enrich ─► … ─► Append to Registry / Gmail   (unchanged main path)
                   └─► Gemini — Extract (Pro) ─► Parse Gemini Pro ─► Compare Models   (BON-6, terminal)
```

- The branch hangs off **Parse Gemini JSON**, so by the time `Compare Models` runs the Flash
  extraction is guaranteed to exist (`$("Parse Gemini JSON")`) — no parallel-branch race.
- Every Pro-branch node is **failure-isolated** (`onError = continueRegularOutput`). A Pro
  outage, 429, or malformed response degrades the comparison to empty **without** failing the
  execution or blocking the registry write / SEV1 alert.
- Flash → `gemini-3-flash-preview`; Pro → `gemini-3.1-pro-preview`. Same prepared request body
  (`$('Prepare Document').item.json.geminiBody`) so the comparison is apples-to-apples.

`Compare Models` ([compare_models.js](../../n8n/cloud/nodes/compare_models.js), parity with the
Python [`/compare`](../../services/enrichment-api/app/compare.py)) emits:
`classification_agreement`, `confidence_delta` (Pro − Flash), `entity_overlap_ratio` (Jaccard),
`field_diff_count`, the per-field diffs, both summaries, and a `compare_markdown` table.

## Live evidence — execution 759 (populated Flash-vs-Pro diff)

The OpenSSL critical-RCE incident (`vuln_scan_critical_openssl.md`) was submitted through the
production form. Both models extracted successfully and `Compare Models` produced a real diff:

| Compare metric | Value |
|---|---|
| `classification_agreement` | **true** — both call it `vulnerability-scan` |
| `confidence_delta` (Pro − Flash) | **−0.05** — Pro marginally more conservative |
| `entity_overlap_ratio` (Jaccard) | **0.90** — 90 % of extracted entities shared |
| `field_diff_count` | **10** — mostly phrasing/granularity, no classification conflict |

The deterministic brain floored both to the same verdict — `vulnerability-scan` · CVSS **9.8** →
**SEV1** · `escalate` · `confidential` · SecOps — so the registry row and SEV1 page are identical
regardless of which model fed them; the compare is a *quality signal*, not a routing input.

## Live evidence — execution 757 (real-world rate-limit resilience)

An earlier run (before Pro quota was available) exercised the failure path: the Pro call returned
**HTTP 429** and, because every Pro-branch node is `onError=continueRegularOutput`, the comparison
degraded to empty **without** failing the execution — the Incidents row was still written and the
SEV1 alert still sent (**execution = success**). The heavier Pro model carries a stricter quota
than Flash; when it is throttled, HINDSIGHT still files the incident and pages on-call. The compare
is best-effort; the system of record is not. (See also BON-4 retry/backoff.)
