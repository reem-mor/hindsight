# HINDSIGHT — Validation & Test Report

**Status:** automated suites green · **Scenario:** cyber incident logs · **Workflow:** `aYEv22StywIPL3Rq` (active)

Assignment mapping: [ASSIGNMENT-MAP.md](ASSIGNMENT-MAP.md) · Bonus detail: [bonus-challenges.md](bonus-challenges.md)

## 1. Summary

| Suite | What it proves | Checks | Result |
|---|---|---:|:---:|
| FastAPI `pytest` | Core + bonus endpoints + sensitivity/catalog/alias/digest-window/escaping regressions | 70 | ✅ |
| Extractor `pytest` | MD + PDF(+image) + DOCX + TXT + standalone-image + corrupt-DOCX + cp1252 | 8 | ✅ |
| Cloud `enrich` + `parse` | Parity + sensitivity-regex + sheet_row defaults + alias word-boundary + parse classification/fence | 76 | ✅ |
| Cloud `prepare` | Upload guards, ZIP, MIME | 7 | ✅ |
| Cloud `compose` | §7.2 row + §8.2 subject contract + Sheet link | 8 | ✅ |
| Bonus Code nodes | digest severity-from-CVSS + compare diff/type-mismatch/overlap (BON-2/6) | 9 | ✅ |
| Self-hosted workflow | every Code-node parses + §8.2 subject + output_docs JSON & MD + retry | 20 | ✅ |
| `verify_all_bonuses.py` | All 8 bonuses + workflow activation | 10 | ✅ |
| `docker_smoke_test.py` | Docker compose health + enrich smoke (Supabase optional) | 5 | ✅ |
| `audit_n8n_cloud.py` | Nodes, credentials, retry, Gemini model | 1 report | ✅ |
| Live E2E | Form → Gemini → Sheet → Gmail | exec 507/510/523/524 | ✅ |

## 2. Reproduce

```powershell
cd c:\dev\hindsight
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
.\.venv\Scripts\python.exe -m pytest tests\test_extractor.py -q
node n8n\cloud\tests\test_node_bodies.mjs
node n8n\cloud\tests\test_prepare.mjs
node n8n\cloud\tests\test_compose.mjs
node n8n\cloud\tests\test_bonus_nodes.mjs
.\.venv\Scripts\python.exe scripts\verify_all_bonuses.py
.\.venv\Scripts\python.exe scripts\docker_smoke_test.py
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py
node scripts\render_architecture.mjs
node scripts\capture_screenshots.mjs
```

Cloud deploy (mutating):

```powershell
.\.venv\Scripts\python.exe scripts\sync_n8n_cloud_nodes.py
.\.venv\Scripts\python.exe scripts\patch_cloud_workflow.py
.\.venv\Scripts\python.exe n8n\build_workflow.py
.\.venv\Scripts\python.exe scripts\import_selfhosted_workflow.py
```

## 3. Bonus verification (all 8)

| Bonus | Proof |
|---|---|
| **BON-1 Vision** | `tests/test_extractor.py` extracts `samples/vuln_scan_sev1_critical_rce.pdf` text **and asserts an embedded image is exported**; self-hosted Vision node; Cloud PDF inline |
| **BON-2 Daily Digest** | `test_digest.py`; `digest_aggregate.js`; `build_digest_workflow.py` |
| **BON-3 Dashboard** | `dashboard/index.html`; `?csv=`; 📸 `screenshot-dashboard.png` |
| **BON-4 Retry** | audit `Gemini retry policy (BON-4)` OK |
| **BON-5 Semantic Search** | `test_search.py`; `migrations/001_pgvector_incidents.sql` |
| **BON-6 Compare** | `test_compare.py`; `POST /compare`; `compare_models.js` (API-only) |
| **BON-7 Batch** | `test_batch.py`; `test_prepare.mjs` zip; `batch_incidents.zip` |
| **BON-8 Alerting** | `patch_cloud_workflow.py`; `build_workflow.py`; exec 507 Page On-Call |

## 4. Edge cases

See [edge-case-matrix.md](edge-case-matrix.md) — zero-byte, MIME mismatch, parse fences, retry idempotency, Cloud stateless recurrence, nested ZIP limits.

## 5. Screenshots & diagrams

| Asset | Path | How to refresh |
|---|---|---|
| Figure 1 architecture | `docs/architecture.png` | `node scripts/render_architecture.mjs` |
| Dashboard (BON-3) | `docs/screenshot-dashboard.png` | `node scripts/capture_screenshots.mjs` |
| FastAPI OpenAPI | `docs/screenshot-fastapi.png` | same |
| Local n8n UI | `docs/screenshot-n8n-local.png` | same (Docker on :5678) |
| Cloud form (grading intake) | `docs/screenshot-form-cloud.png` | Playwright MCP public form URL |

## 6. Live E2E

**Prerequisite:** Sheet tab **`Incidents`**; workflow **active**.

1. Submit `samples/vuln_scan_critical_openssl.md` via form Production URL
2. Confirm Sheet row + Page On-Call Gmail
3. Optional: `samples/batch_incidents.zip` (BON-7)

```
Live execution ID: 510 (success, 2026-06-23)
Sample: samples/vuln_scan_critical_openssl.md
Path: Page On-Call (SEV1) — CVSS 9.8, routing_tag escalate

Batch zip (BON-7): exec 523 — 2 files → 2 rows
Single-file verify: exec 524
```

Self-hosted: `docker compose up -d` → `import_selfhosted_workflow.py` → activate workflow → drop file in `incoming_docs/`.
