# HINDSIGHT — Validation & Test Report

**Status:** automated suites green · **Scenario:** cyber incident logs · **Workflow:** `aYEv22StywIPL3Rq` (active)

## 1. Summary

| Suite | What it proves | Checks | Result |
|---|---|---:|:---:|
| FastAPI `pytest` | Core + bonus endpoints (search, compare, digest, batch) | 60+ | ✅ |
| Extractor `pytest` | Markdown/PDF extraction path (BON-1) | 2 | ✅ |
| Cloud Code nodes | `enrich.js` + `parse.js` parity | 60 | ✅ |
| Bonus Code nodes | digest + compare (BON-2/6) | 5 | ✅ |
| `audit_n8n_cloud.py` | Nodes, credentials, retry policy, activation | 1 report | ✅ |
| Live E2E | Form → Gemini → Sheet → Gmail | exec 507/510/523/524 | ✅ |
| Batch zip (BON-7) | Stored ZIP fan-out on n8n Cloud | exec 523 (2 files → 2 rows) | ✅ |
| Live pgvector (BON-5) | Supabase `hindsight_incidents` + `POST /search` | sim=1.0 on indexed doc | ✅ |

## 2. Reproduce

```powershell
cd c:\dev\hindsight
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
.\.venv\Scripts\python.exe -m pytest tests\test_extractor.py -q
node n8n\cloud\tests\test_node_bodies.mjs
node n8n\cloud\tests\test_bonus_nodes.mjs
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py
.\.venv\Scripts\python.exe scripts\sync_n8n_cloud_nodes.py
.\.venv\Scripts\python.exe scripts\patch_cloud_workflow.py
.\.venv\Scripts\python.exe scripts\activate_n8n_cloud.py
python scripts\build_digest_workflow.py
node scripts\render_architecture.mjs
```

## 3. Bonus verification (all 8)

| Bonus | Proof |
|---|---|
| **BON-1 Vision** | `tests/test_extractor.py`; `samples/vuln_scan_sev1_critical_rce.pdf` |
| **BON-2 Daily Digest** | `test_digest.py`; `n8n/cloud/digest_workflow.json` |
| **BON-3 Dashboard** | `dashboard/index.html`; `?csv=` param; `dashboard/fixtures/incidents.csv`; screenshot-dashboard |
| **BON-4 Retry** | audit `Gemini retry policy (BON-4)` OK |
| **BON-5 Semantic Search** | `test_search.py`; `migrations/001_pgvector_incidents.sql`; live Supabase project `zduaexkkhdnltyelvuwn`; `POST /search` |
| **BON-6 Compare** | `test_compare.py`; `POST /compare`; `compare_models.js` |
| **BON-7 Batch** | `test_batch.py`; `samples/batch_incidents.zip` (ZIP_STORED); exec **523** fan-out 2× |
| **BON-8 Alerting** | `patch_cloud_workflow.py`; exec 507 Page On-Call |

## 4. Live E2E

**Prerequisite:** Sheet tab **`Incidents`**; workflow **active**.

1. Submit `samples/vuln_scan_critical_openssl.md` via form Production URL
2. Confirm Sheet row + Page On-Call Gmail at `reem.mor3@gmail.com`
3. Optional: submit `samples/siem_bruteforce_intrusion.md` for digest branch

```
Live execution ID: 510 (success, 2026-06-23)
Sample: samples/vuln_scan_critical_openssl.md
Path: Page On-Call (SEV1) — CVSS 9.8, routing_tag escalate

Batch zip (BON-7): exec 523 — Prepare Document fan-out 2 items (siem_alert.md, phishing_report.txt) → 2× Append to Registry
Single-file verify: exec 524 — vuln_scan_critical_openssl.md
Note: exec 522 failed (Gemini rate limit); use stored ZIP only on Cloud (no zlib).
```

Self-hosted: `docker compose up --build -d` · drop PDF into `incoming_docs/` · extractor returns Vision image + CVSS fields (`extract_document.py` verified on `vuln_scan_sev1_critical_rce.pdf`).

**Supabase (BON-5):** run `migrations/001_pgvector_incidents.sql` (includes table grants for `service_role`). Index via `POST /index` or `/enrich`; search via `POST /search`. With mock embeddings (no valid `GEMINI_API_KEY`), query text must overlap indexed text for similarity ≥ threshold.

**Dashboard (BON-3):** publish Sheet CSV or open `dashboard/index.html?csv=http://127.0.0.1:8765/fixtures/incidents.csv` (fixture mirrors live exec 523/524 shape).
