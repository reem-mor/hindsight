# HINDSIGHT — Requirements Traceability Matrix

Scenario: **Cybersecurity incident logs** (SIEM, vulnerability scans, phishing, intrusion writeups).

Legend: ✅ automated test · 📸 screenshot · ⚙️ workflow config · ✋ live credential

## Architecture (REQ-A*, DIAG-*)

| ID | Requirement | File / node | Evidence | Status |
|---|---|---|---|---|
| REQ-A1 | n8n orchestrates pipeline | Cloud `aYEv22StywIPL3Rq`; [n8n/hindsight_workflow.json](../n8n/hindsight_workflow.json) | `scripts/audit_n8n_cloud.py`; exec 507/510 | ✅ |
| REQ-A2 | Full component chain wired | Cloud form→Gemini→enrich→Sheets/Gmail; self-hosted→output_docs | [docs/VALIDATION.md](VALIDATION.md) | ✅ |
| REQ-A3 | Tech stack (Gemini 3 Flash, FastAPI, Sheets, Gmail, PyMuPDF) | [prepare.js](../n8n/cloud/nodes/prepare.js), [extract_document.py](../extractors/extract_document.py) | pytest + node tests | ✅ |
| REQ-A4 | End-to-end architecture diagram | [README.md](../README.md), [docs/architecture.md](architecture.md), [docs/architecture.mmd](architecture.mmd) | [docs/architecture.png](architecture.png) | ✅ |
| DIAG-1 | Figure 1 — dual path + 3 outputs | README + architecture.md mermaid | architecture.png | ✅ |
| DIAG-2 | P1–P6 pipeline sequence | [docs/architecture.md](architecture.md) § Pipeline sequence | mermaid in docs | ✅ |
| DIAG-3 | Enrichment decision logic | [docs/architecture.md](architecture.md) § Enrichment | mermaid + `test_cyber.py` | ✅ |
| DIAG-4 | Bonus data flows | [docs/architecture.md](architecture.md) § Bonus flows | mermaid diagrams | ✅ |

## Functional pipeline (REQ-P*)

| ID | Step | File / node | Evidence | Status |
|---|---|---|---|---|
| REQ-P1 | File detection | Form trigger; `localFileTrigger` | SETUP-GUIDE | ✅ |
| REQ-P2 | Text + image extraction | [prepare.js](../n8n/cloud/nodes/prepare.js); [extract_document.py](../extractors/extract_document.py) | `test_extractor.py`; `test_prepare.mjs` | ✅ |
| REQ-P3 | Gemini strict JSON | Gemini HTTP + [extraction_prompt.md](../prompts/extraction_prompt.md) | exec 507 | ✅ |
| REQ-P4 | Metadata enrichment | [enrich.js](../n8n/cloud/nodes/enrich.js); `POST /enrich` | 60 node checks + pytest | ✅ |
| REQ-P5 | Google Sheets append | [sheet_row.js](../n8n/cloud/nodes/sheet_row.js) | 📸 screenshot-sheet | ✅ |
| REQ-P6 | Output file + email | [compose.js](../n8n/cloud/nodes/compose.js); self-hosted write node | 📸 screenshot-email | ✅ |

## Gemini (REQ-G*)

| ID | Requirement | File | Evidence | Status |
|---|---|---|---|---|
| REQ-G1 | Credential auth, no hardcoded keys | Cloud `googlePalmApi` credential | audit | ✅ |
| REQ-G2 | POST generateContent, JSON body, temp 0.2 | [prepare.js](../n8n/cloud/nodes/prepare.js) | audit retry row | ✅ |
| REQ-G3 | Cyber prompt template | [prompts/extraction_prompt.md](../prompts/extraction_prompt.md) | traceability | ✅ |
| REQ-G4 | Robust JSON parse + validate | [parse.js](../n8n/cloud/nodes/parse.js) | `test_node_bodies.mjs` parse tests | ✅ |

## Enrichment API (REQ-E*)

| ID | Endpoint / rule | File | Evidence | Status |
|---|---|---|---|---|
| REQ-E1 | `/enrich`, `/health`, `/categories`, `/sensitivity` | [main.py](../services/enrichment-api/app/main.py) | `test_ops.py` | ✅ |
| REQ-E2 | Routing, sensitivity (public/internal/confidential), confidence adjust | [enrichment.py](../services/enrichment-api/app/enrichment.py) | `test_enrich.py`; `test_logic.py` | ✅ |
| REQ-E3 | CVSS floor ≥9 → SEV1 + escalate | [severity.py](../services/enrichment-api/app/severity.py) | `test_critical_cvss_*` | ✅ |
| REQ-E4 | Service catalog | [service_catalog.yaml](../services/enrichment-api/data/service_catalog.yaml) | `test_logic.py` | ✅ |

## Google Sheets (REQ-S*)

| ID | Requirement | File | Evidence | Status |
|---|---|---|---|---|
| REQ-S1 | OAuth2 append one row/doc | Append to Registry node | audit | ✅ |
| REQ-S2 | 14 columns mapped | [n8n_cloud_api.py](../scripts/n8n_cloud_api.py) SHEET_HEADERS | compose + exec 507 | ✅ |

## Gmail (REQ-M*)

| ID | Requirement | File | Evidence | Status |
|---|---|---|---|---|
| REQ-M1 | OAuth2 send, configurable recipient | Page On-Call + Postmortem Filed | audit `reem.mor3@gmail.com` | ✅ |
| REQ-M2 | HTML template fields + Sheet registry link | [compose.js](../n8n/cloud/nodes/compose.js) | 📸 screenshot-email; §8 link by `document_id` | ✅ |

## Reliability (REQ-R*)

| ID | Requirement | File | Evidence | Status |
|---|---|---|---|---|
| REQ-R1 | Retries + safe-fail parse | Gemini 5×/3s; parse throws | audit BON-4 row; parse tests | ✅ |
| REQ-R2 | Cyber scenario consistency | prompts, catalog, samples | `test_cyber.py` | ✅ |

## Bonus challenges (BON-*)

| ID | Bonus | File / node | Evidence | Status |
|---|---|---|---|---|
| BON-1 | Gemini Vision | Self-hosted Vision; cloud PDF `inline_data`; [vision_prompt.md](../prompts/vision_prompt.md) | [vuln_scan_sev1_critical_rce.pdf](../samples/vuln_scan_sev1_critical_rce.pdf); `test_extractor.py` | ✅ |
| BON-2 | Daily Email Digest | [digest_workflow.json](../n8n/cloud/digest_workflow.json); [digest_aggregate.js](../n8n/cloud/nodes/digest_aggregate.js) | `test_digest.py`; `test_bonus_nodes.mjs` | ✅ |
| BON-3 | Live Dashboard | [dashboard/index.html](../dashboard/index.html) | 📸 screenshot-dashboard; `?csv=` URL param | ✅ |
| BON-4 | Retry logic | Gemini HTTP 5×/3s | audit `Gemini retry policy` | ✅ |
| BON-5 | Semantic Search | [search_store.py](../services/enrichment-api/app/search_store.py); [embeddings.py](../services/enrichment-api/app/embeddings.py) (`gemini-embedding-001`, 768-dim); [001_pgvector_incidents.sql](../migrations/001_pgvector_incidents.sql); `POST /search` `/index` | `test_search.py` (InMemory **+ SupabaseVectorStore**); live Supabase `zduaexkkhdnltyelvuwn` · 5 rows · HNSW · `match_*` RPC (MCP-verified 2026-06-26) | ✅ |
| BON-6 | Multi-model Compare | **Wired in Cloud workflow**: `Gemini — Extract (Pro)` → `Parse Gemini Pro` → `Compare Models` (non-blocking, failure-isolated); [compare_models.js](../n8n/cloud/nodes/compare_models.js); [compare.py](../services/enrichment-api/app/compare.py) `POST /compare` | `test_compare.py`; bonus node test; **live exec 759** (Flash vs `gemini-3.1-pro-preview`: agreement=true, entity-overlap 0.90); [compare-flash-vs-pro.md](sample-outputs/compare-flash-vs-pro.md) | ✅ |
| BON-7 | Multi-file Batch | [prepare.js](../n8n/cloud/nodes/prepare.js) zip fan-out; [batch.py](../services/enrichment-api/app/batch.py) | [batch_incidents.zip](../samples/batch_incidents.zip); `test_batch.py` | ✅ |
| BON-8 | Sensitivity alerting | Cloud `Is SEV1?` OR confidential OR escalate; self-hosted `is_sev1` parity | `patch_cloud_workflow.py`; `build_workflow.py`; pytest | ✅ |

## Verification commands

```powershell
pytest services\enrichment-api -q
pytest tests\test_extractor.py -q
node n8n\cloud\tests\test_node_bodies.mjs
node n8n\cloud\tests\test_prepare.mjs
node n8n\cloud\tests\test_compose.mjs
node n8n\cloud\tests\test_bonus_nodes.mjs
node scripts\render_architecture.mjs
node scripts\capture_screenshots.mjs
python scripts\audit_n8n_cloud.py
python scripts\sync_n8n_cloud_nodes.py
python scripts\build_digest_workflow.py
```

Live E2E: exec **757** (2026-06-26) — SEV1 critical-RCE PDF → Gemini Flash → enrich (CVSS 9.8 → **SEV1 · escalate · confidential**) → Sheet append + **Page On-Call (SEV1)** email, with the BON-6 Flash-vs-Pro compare branch exercised in parallel (Pro 429 on the free tier → graceful degradation, execution still **success**). Earlier: exec 507 / 510.
