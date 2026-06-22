# HINDSIGHT — Edge-case & resilience matrix

How the pipeline behaves on the unhappy path. "Verified" cites the test or command that
proves it. Run the suites with `pytest -q` (services/enrichment-api), `node
n8n/cloud/tests/test_node_bodies.mjs`, and the extractor with the local Python venv.

| Case | Trigger | Expected behaviour | Verified |
|---|---|---|---|
| Empty / zero-byte file | drop a 0-byte file in `incoming_docs/` | extractor returns `ok:false` (`empty file (0 bytes)`); `Parse extraction` node throws → never sent to Gemini | ✅ extractor run (`extract_document.py` empty-file guard) |
| Text-less / scanned PDF, no images | image-only PDF with no text layer and no extractable images | extractor returns `ok:false` (`no extractable text…`) → skipped, not sent to Gemini | ✅ `extract()` guard (`bool(text or images)`) |
| Scanned PDF **with** an embedded chart | PDF with no text but a dashboard image | `ok:true`, image extracted → routed to the Gemini Vision branch | ✅ extractor run on `vuln_scan_sev1_critical_rce.pdf` (chars + 1 image) |
| Corrupt / unparseable PDF | garbage or password-protected `.pdf` | extractor catches the parser error, returns `ok:false` (`could not parse PDF: …`) — no crash, no non-JSON stdout | ✅ extractor run on a malformed `.pdf` |
| Gemini returns non-JSON / fenced / partial JSON | model wraps output in ```` ```json ```` or trails text | `Parse Gemini JSON` strips fences (with/without lang tag) and throws a clear error on truly malformed output | ✅ node harness: `parse.clean*`, `parse.fenced_json`, `parse.fenced_plain`, `parse.malformed_throws`, `parse.missing_candidates_throws` |
| Gemini 429 / rate-limit / 5xx / timeout | transient model/network failure | HTTP Request node `retryOnFail`, 5 tries, 3 s backoff; Vision node `onError: continueRegularOutput` so a vision miss never blocks the run | ⚙️ workflow config (`maxTries:5`, `waitBetweenTries:3000`); live retry not exercised offline |
| Oversized document beyond context | very large input | relies on Gemini 3 Flash's 1M-token context window; no manual chunking | ⚙️ by design — documented in README; not chunked |
| Missing entities / fields from Gemini | model omits root_cause, services, metrics, etc. | enrichment defaults every field, still produces a valid row, and penalises confidence → `needs-review` | ✅ pytest `test_empty_payload_is_safe`, `test_confidence_floors_at_zero_with_notes` |
| Long / multibyte / emoji input | ~20k-char unicode summary | enrichment does not crash; severity still computed | ✅ pytest `test_long_unicode_summary_does_not_crash`; node `robust.unicode` |
| Duplicate filename / re-processed incident | same incident processed twice | each run gets a fresh `document_id` (no double-write protection), but the recurrence fingerprint is stable and flags `repeat-offender` on the 2nd sighting | ✅ pytest `test_recurrence_fingerprint_stable_and_counts` — note: dedupe is by fingerprint surfacing, not idempotent write |
| Network failure to the FastAPI service | enrichment unreachable | `Enrich (FastAPI)` HTTP node `retryOnFail`, 3 tries, 1.5 s backoff | ⚙️ workflow config (`maxTries:3`) |
| Unknown service name from Gemini | service not in the catalog | falls back to incident-type routing (e.g. `security → Security-IR`, `vulnerability-scan → SecOps`); SLO is null but the row is still produced | ✅ pytest `test_unknown_service_security_routes_to_security_ir…`, `test_vuln_scan_unknown_service_routes_to_secops`; node `sec.department` |
| Severity disagreement (both directions) | author over- or under-calls severity | rubric re-scores and flags `severity-review` whether it is an upgrade or a downgrade | ✅ pytest `test_severity_downgrade_also_flags_review`; node `downgrade.review` |
| **Cyber: critical CVE** | `cvss_score >= 9.0` (e.g. CVE-2026-21841, 9.8) | severity floored to SEV1, `routing_tag=escalate`, `sensitivity=confidential`, `page-oncall` | ✅ pytest `test_critical_cvss_floors_to_sev1_and_escalates`; node `cvss.sev1` |
| **Cyber: out-of-range CVSS** | `cvss_score` > 10 or < 0 | clamped to 0.0–10.0 in both the FastAPI brain and the cloud node (parity) | ✅ pytest `test_cvss_is_clamped`, `test_score_severity_endpoint_clamps_cvss`; node `cvss.clamp` |
| Bad input to the API | malformed JSON body / wrong types | FastAPI returns a 422 with a structured error body; the service never 500s on validation | ✅ Pydantic v2 validation on every request model |

## Legend
- ✅ verified by an automated test or a reproducible command in this environment.
- ⚙️ enforced by n8n node configuration; the offline harness cannot exercise a live external 429/timeout, so it is verified by configuration + the documented Cloud dry-runs, not by a live failure here.
