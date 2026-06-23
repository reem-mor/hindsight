<div align="center">

# HINDSIGHT

### Cyber incident log intelligence

**SIEM exports, vuln scans, and phishing reports → structured, routed, filed automatically.**

`n8n Cloud` · `Gemini 3 Flash (+ Vision)` · `FastAPI` · `Google Sheets` · `Gmail`

</div>

---

## What it does

HINDSIGHT is the **Cybersecurity incident logs** scenario from the n8n homework: upload a
document, Gemini extracts a strict JSON schema, a deterministic enrichment brain re-scores
severity (including **CVSS floor**), classifies **sensitivity**, assigns **routing_tag**, and
files one row per document to Google Sheets plus an HTML Gmail summary.

```mermaid
flowchart TB
  subgraph input [Input detection]
    Form[Cloud form upload]
    Watch[incoming_docs watch]
  end
  subgraph extract [Extraction]
    Prep[Prepare / Python extractor]
    Vision[Gemini Vision optional]
  end
  subgraph analyze [Gemini analysis]
    Flash[Gemini 3 Flash JSON]
    Parse[Parse + validate JSON]
  end
  subgraph decide [Enrichment brain]
    Enrich[CVSS floor + routing_tag]
  end
  subgraph outputs [Three output channels]
    Sheets[Google Sheets]
    Files[output_docs]
    Gmail[Gmail Page or Digest]
  end
  Form --> Prep
  Watch --> Prep
  Prep --> Vision
  Prep --> Flash
  Vision --> Flash
  Flash --> Parse --> Enrich
  Enrich --> Sheets
  Enrich --> Files
  Enrich --> Gmail
```

See [Figure 1 — architecture.png](docs/architecture.png) and [docs/architecture.md](docs/architecture.md).

**The LLM extracts; the service decides.** CVSS 9.8 on a Nessus report floors to SEV1 and
`routing_tag=escalate` even when the author typed SEV3.

---

## n8n Cloud (grading path)

| Item | Value |
|---|---|
| Instance | https://reemmor.app.n8n.cloud |
| Workflow | `HINDSIGHT — Postmortem Intelligence (Cloud)` · id `aYEv22StywIPL3Rq` |
| Registry sheet | `1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk` · tab `Incidents` |
| Code nodes | `n8n/cloud/nodes/*.js` (synced via `scripts/sync_n8n_cloud_nodes.py`) |

| Credential | Used by |
|---|---|
| `Google Gemini(PaLM) Api account` | Gemini — Extract Incident |
| `Google Sheets Amdocs Course API` | Append to Registry |
| `Gmail Amdocs course API` | Page On-Call / Postmortem Filed → `reem.mor3@gmail.com` |

**Manual before live run:** activate workflow, verify sheet headers (see [`docs/SETUP-GUIDE.md`](docs/SETUP-GUIDE.md)), submit `samples/vuln_scan_critical_openssl.md` via the form Production URL.

---

## Self-hosted (docker)

```powershell
docker compose up --build -d
```

Drop `.pdf` / `.md` into `incoming_docs/`. Import `n8n/hindsight_workflow.json` into local n8n
or use the compose stack. Vision branch reads embedded SIEM/scan charts; output markdown lands in
`output_docs/`.

---

## FastAPI enrichment API

```powershell
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
```

Endpoints: `POST /enrich`, `GET /health`, `GET /categories`, `POST /sensitivity`,
`POST /search`, `POST /index`, `POST /compare`, `POST /digest/preview`. SecOps catalog
in `services/enrichment-api/data/service_catalog.yaml`.

---

## Bonus challenges (all 8 delivered)

| Bonus | Where | Verified |
|---|---|---|
| **BON-1 Gemini Vision** | Self-hosted Vision + cloud PDF `inline_data`; `prompts/vision_prompt.md`; `samples/vuln_scan_sev1_critical_rce.pdf` | `tests/test_extractor.py` |
| **BON-2 Daily Digest** | `n8n/cloud/digest_workflow.json` + `digest_aggregate.js` | `test_digest.py`, bonus node tests |
| **BON-3 Live dashboard** | [`dashboard/index.html`](dashboard/index.html) — CVSS, sensitivity, routing_tag; `?csv=` URL | `docs/screenshot-dashboard.png` |
| **BON-4 Retry logic** | Gemini HTTP 5× / 3s backoff | `audit_n8n_cloud.py` retry check |
| **BON-5 Semantic search** | `POST /search`, pgvector migration, auto-index on `/enrich` | `test_search.py` |
| **BON-6 Multi-model compare** | `POST /compare`, `compare_models.js`, Gemini 3 Pro | `test_compare.py` |
| **BON-7 Multi-file batch** | `.zip` in form; `prepare.js` fan-out; `samples/batch_incidents.zip` | `test_batch.py` |
| **BON-8 Sensitivity alerting** | SEV1 / confidential / escalate → Page On-Call | exec 507; `patch_cloud_workflow.py` |

---

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
.\.venv\Scripts\python.exe -m pytest tests\test_extractor.py -q
node n8n\cloud\tests\test_node_bodies.mjs
node n8n\cloud\tests\test_bonus_nodes.mjs
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py
```

---

## Screenshots

| Artifact | Path |
|---|---|
| n8n workflow canvas | `docs/screenshot-workflow.png` |
| Execution detail | `docs/screenshot-execution.png` |
| Google Sheet row | `docs/screenshot-sheet.png` |
| Gmail notification | `docs/screenshot-email.png` |
| Dashboard | `docs/screenshot-dashboard.png` |
| FastAPI OpenAPI | `docs/screenshot-fastapi.png` |

Regenerate local shots: `node scripts/capture_screenshots.mjs`

---

## Repo map

| Path | Role |
|---|---|
| `n8n/cloud/nodes/` | Live Cloud Code-node bodies (source of truth) |
| `services/enrichment-api/` | Graded FastAPI brain |
| `samples/` | Cyber incident fixtures |
| `docs/SETUP-GUIDE.md` | Manual checklist |
| `docs/traceability-matrix.md` | Requirement mapping |
| `docs/VALIDATION.md` | Evidence trail |

Full setup: [`docs/SETUP-GUIDE.md`](docs/SETUP-GUIDE.md)
