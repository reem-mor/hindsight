# HINDSIGHT — Assignment traceability (n8n_hw docx)

Scenario chosen: **Cybersecurity incident logs** (§10). This maps the course brief
(`n8n_hw (1).docx`) to repo artifacts, tests, and evidence.

Legend: ✅ automated · 📸 screenshot · ⚙️ config · ✋ live credential

## §1–2 Project summary & objectives

| Requirement | HINDSIGHT implementation | Evidence |
|---|---|---|
| Cloud Gemini pipeline | n8n Cloud workflow `aYEv22StywIPL3Rq` | `audit_n8n_cloud.py` ✅ |
| Structured extraction | `prompts/extraction_prompt.md`, `parse.js` | `test_node_bodies.mjs` ✅ |
| Multi-modal (Vision) | Self-hosted PyMuPDF + Vision branch; Cloud PDF `inline_data` | `test_extractor.py` ✅ BON-1 |
| Python microservice | `services/enrichment-api/` FastAPI | pytest 61+ ✅ |
| Google Sheets registry | Append to Registry + `sheet_row.js` flatten | audit + 📸 sheet |
| Gmail notifications | Page On-Call + Postmortem Filed | audit + 📸 email |
| Retries & logging | Gemini 5×/3s; enrichment 3× | audit BON-4 ✅ |

## §3 System architecture (DIAG-1)

| Figure | Doc | Repo |
|---|---|---|
| End-to-end pipeline | §3.3 Figure 1 | [architecture.png](architecture.png), [architecture.mmd](architecture.mmd) |
| Dual path (Cloud + self-hosted) | §3.1 Components | [architecture.md](architecture.md) § Dual deployment |
| Tech stack table | §3.2 | [AGENTS.md](../AGENTS.md), [README.md](../README.md) |

## §4 Functional pipeline (REQ-P1→P6)

| Step | Assignment | Cloud node | Self-hosted | Test |
|---|---|---|---|---|
| P1 File detection | Form / watched folder | `Submit a Postmortem` | `incoming_docs/` trigger | SETUP-GUIDE ✅ |
| P2 Text + image extract | Python / Code | `prepare.js` | `extract_document.py` | `test_prepare.mjs`, `test_extractor.py` ✅ |
| P3 Gemini JSON | HTTP POST Flash | `Gemini — Extract Incident` | same pattern | audit + parse tests ✅ |
| P4 Metadata enrich | Student API | `HINDSIGHT Enrich` (`enrich.js`) | `POST /enrich` | pytest + node tests ✅ |
| P5 Google Sheets | Append row | `Flatten for Sheets` → Append | Append node | 14-column contract ✅ |
| P6 Output + email | Markdown + Gmail | `Compose Outputs` → Gmail | `output_docs/` write | `compose.js` + 📸 ✅ |

## §5 Gemini API (REQ-G*)

| Item | Assignment | HINDSIGHT |
|---|---|---|
| Model | gemini-3-flash | `gemini-3-flash-preview` URL (404-safe) |
| Temperature | 0.2 | `prepare.js` `generationConfig.temperature: 0.2` ✅ |
| JSON mode | `responseMimeType: application/json` | ✅ |
| Prompt fields | summary, classification, entities, sentiment, action_items | Cyber schema in `extraction_prompt.md` ✅ |
| Auth | n8n credential vault | No keys in repo ✅ |

## §6 Student Metadata API (REQ-E*)

| Endpoint | Required | Implemented |
|---|---|---|
| `POST /enrich` | ✅ | ✅ `test_enrich.py` |
| `GET /health` | ✅ | ✅ `test_ops.py` |
| `GET /categories` | ✅ | ✅ |
| `POST /sensitivity` | public / internal / confidential | ✅ `test_logic.py` |
| Sensitivity keywords | entities / regulatory | `classify_sensitivity()` ✅ |
| routing_tag | needs-review / auto-approved / escalate | enrich brain ✅ |
| document_id UUID | ✅ | enrich output ✅ |
| confidence adjust | entity completeness | `_adjust_confidence()` ✅ |

## §7 Google Sheets (REQ-S*)

14 columns (§7.2 + cyber bonus): see [traceability-matrix.md](traceability-matrix.md) REQ-S2.
Sheet ID default: `1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk`, tab **`Incidents`**.

## §8 Gmail (REQ-M*)

| Item | Assignment §8.2 | HINDSIGHT |
|---|---|---|
| Subject pattern | `[classification] New document processed: filename` | `compose.js` ✅ |
| HTML fields | file, classification, sentiment, department, sensitivity, routing_tag, summary, action_items | ✅ |
| Sheet row link | link to registry row | `compose.js` Registry link + `document_id` ✅ |
| SEV1 high-priority branch | implied by scenario | BON-8 Page On-Call ✅ |

## §9 Bonus challenges — see [bonus-challenges.md](bonus-challenges.md)

All eight bonuses implemented; verification in [VALIDATION.md](VALIDATION.md).

## §10 Scenario

**Cybersecurity incident logs** — SIEM exports, vuln scans, phishing, intrusion writeups.
Samples under `samples/`; rubric in `service_catalog.yaml` and `enrichment.py` / `enrich.js`.
