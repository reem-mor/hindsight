# HINDSIGHT — Requirements Traceability Matrix

Scenario: **Cybersecurity incident logs** (SIEM, vulnerability scans, phishing, intrusion writeups).

Verification legend: ✅ automated proof · ⚙️ workflow config · ✋ live credentials required

## 3. System components

| Requirement | Where | Verified |
|---|---|---|
| n8n orchestrates pipeline | Cloud `aYEv22StywIPL3Rq` + `n8n/hindsight_workflow.json` | ✅ API audit + JSON valid |
| Google Gemini API | Cloud HTTP + self-hosted Vision/extract nodes | ✋ live key in n8n vault |
| Student metadata API (FastAPI) | `services/enrichment-api/` | ✅ 48 pytest |
| Google Sheets registry | Append to Registry node | ✅ sheet ID patched via API |
| Filesystem trigger | `incoming_docs/` localFileTrigger | ⚙️ docker compose |
| Gmail notification | Page On-Call + digest nodes | ✋ OAuth in n8n vault |
| Output folder | `output_docs/` write node | ⚙️ self-hosted |

## 6. Metadata API

| Requirement | Where | Verified |
|---|---|---|
| `POST /enrich` | `app/main.py` | ✅ pytest |
| `GET /health` | `app/main.py` | ✅ pytest |
| `GET /categories` | `app/main.py` | ✅ pytest incl. cyber types |
| `POST /sensitivity` | `app/main.py` | ✅ pytest |
| Routing + `routing_tag` | `enrichment.py` + `enrich.js` parity | ✅ pytest + 58 node checks |
| CVSS floor / CVE echo | models + severity | ✅ `test_cyber.py` |

## 7. Google Sheets (assignment §7.2)

| Column | Source field | Verified |
|---|---|---|
| `document_id` | `document_id` | ✅ `compose.js` |
| `filename` | `source_filename` | ✅ |
| `file_type` | extension | ✅ |
| `processed_at` | `processed_at` | ✅ |
| `classification` | `incident_type` | ✅ |
| `department` | `department` | ✅ |
| `sentiment` | Gemini `sentiment` | ✅ |
| `confidence_score` | adjusted confidence | ✅ |
| `summary` | truncated ≤500 | ✅ |
| `routing_tag` | `routing_tag` | ✅ |
| `sensitivity` | `sensitivity` | ✅ |
| `action_items` | joined actions | ✅ |
| `cvss_score`, `cve_ids` (bonus) | enrich output | ✅ |

## 8. Gmail (assignment §8.2)

| Requirement | Where | Verified |
|---|---|---|
| HTML: file, classification, sentiment, department, sensitivity, routing_tag, summary, actions | `compose.js` `emailHtml*` | ✅ template in code |
| Configurable recipient | `sendTo` on Gmail nodes | ✅ `reem.mor3@gmail.com` in audit |

## 9. Bonus challenges

| Challenge | Where | Verified |
|---|---|---|
| 🌐 Gemini Vision | Self-hosted Vision branch; cloud PDF `inline_data`; `vision_prompt.md`; `make_cyber_pdf_sample.py` | ⚙️ + extractor image tests |
| 🛡️ Sensitivity alerting | SEV1 → Page On-Call (high priority); CVSS≥9 → escalate + page | ✅ pytest + node `cvss.sev1` |
| 🔁 Retry logic | Gemini 5×/3s; Enrich 3×/1.5s | ⚙️ `retryOnFail` on nodes |
| 📊 Live dashboard | `dashboard/index.html` + `incidents.sample.json` | ✅ CVSS/sensitivity/routing UI |

## 10. Scenario

| Requirement | Where | Verified |
|---|---|---|
| Cyber-only prompts, catalog, samples | `prompts/`, `service_catalog.yaml`, `samples/*` | ✅ no SRE payment samples |

## Verification commands

```powershell
pytest services\enrichment-api -q
node n8n\cloud\tests\test_node_bodies.mjs
python scripts\audit_n8n_cloud.py
python scripts\sync_n8n_cloud_nodes.py
```

Live E2E: ✋ activate workflow → form upload `samples/vuln_scan_critical_openssl.md` → Sheet + Gmail.
