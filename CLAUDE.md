# CLAUDE.md — HINDSIGHT

> Project context for Claude Code. This is the canonical brief; `.cursor/rules` may defer here.
> Environment: Windows, PowerShell, repo at `c:\dev\hindsight`, virtualenv at repo root `.venv`.

## What this is

**HINDSIGHT — cyber incident log intelligence.** It is the *Cybersecurity incident logs*
scenario of the n8n "Intelligent Cloud Document Analyst" course brief: upload a document
(SIEM export, vuln scan, phishing/intrusion writeup), Gemini extracts a strict JSON schema,
a deterministic enrichment service re-scores severity, classifies sensitivity, assigns a
routing tag, and files one row per document to Google Sheets plus an HTML Gmail summary.

**Core principle: the LLM extracts; the service decides.** Extraction is the *only* LLM step.
All scoring/routing is deterministic and unit-tested — e.g. CVSS 9.8 on a Nessus report
floors to SEV1 with `routing_tag=escalate` even if the author typed SEV3.

Two execution paths share the same SecOps rubric:

| Path | Trigger | Enrichment | Output |
|---|---|---|---|
| **n8n Cloud** (grading path) | Form upload | Cloud Code node (`enrich.js`) | Google Sheets + Gmail |
| **Self-hosted** (docker) | `incoming_docs/` watcher | FastAPI `/enrich` | Sheets + Gmail + `output_docs/` |

## Repo map

| Path | Role |
|---|---|
| `services/enrichment-api/` | **Graded FastAPI brain** (Python 3.12). `app/`: `enrichment`, `severity`, `routing`, `embeddings`, `search_store`, `digest`, `batch`, `compare`, `models`, `config`, `main`. `data/service_catalog.yaml` = SecOps catalog. |
| `n8n/cloud/nodes/*.js` | **Source of truth** for the deployed Cloud Code-node bodies. Synced via `scripts/sync_n8n_cloud_nodes.py`. |
| `n8n/cloud/tests/*.mjs` | Node-body tests (run with Node 20). |
| `n8n/hindsight_workflow.json` | Self-hosted workflow import. `n8n/Dockerfile` = n8n + PyMuPDF + python-docx. |
| `extractors/extract_document.py` | PDF/DOCX/text extraction (PyMuPDF) + embedded-image pull for Vision. |
| `prompts/` | `extraction_prompt.md`, `vision_prompt.md`. |
| `dashboard/index.html` | Live dashboard (CVSS / sensitivity / routing_tag); reads a published-sheet CSV via `?csv=`. |
| `samples/` | Cyber incident fixtures (`.md`, generated `.pdf`, `batch_incidents.zip`). |
| `scripts/` | Operational tooling: audit / sync / bootstrap / poll executions / screenshots / render architecture / merge env. |
| `migrations/001_pgvector_incidents.sql` | Supabase pgvector schema for semantic search (BON-5). |
| `docs/` | `SETUP-GUIDE.md` (manual checklist), `VALIDATION.md`, `architecture.*`, `traceability-matrix.md`, `edge-case-matrix.md`, screenshots. |

## Commands

All Python runs through the repo-root venv.

**Tests** (CI runs all of these on push/PR to `main`):
```powershell
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q   # FastAPI enrichment suite
.\.venv\Scripts\python.exe -m pytest tests\test_extractor.py -q   # extractor / Vision
node n8n\cloud\tests\test_node_bodies.mjs                          # deployed Code-node bodies
node n8n\cloud\tests\test_bonus_nodes.mjs                          # bonus node bodies
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py             # live Cloud audit (read-only)
```

**Run the enrichment API locally:**
```powershell
cd services\enrichment-api
..\..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
# OpenAPI: http://localhost:8000/docs   probe: /health   metrics: /metrics
```
Endpoints: `POST /enrich`, `GET /health`, `GET /categories`, `POST /sensitivity`,
`POST /search`, `POST /index`, `POST /compare`, `POST /digest/preview`, `GET /metrics`.

**Self-hosted stack:**
```powershell
docker compose up --build -d   # n8n → http://localhost:5678 ; enrichment → http://localhost:8000
```

**Cloud sync / setup (mutating — run deliberately):**
```powershell
.\.venv\Scripts\python.exe scripts\sync_n8n_cloud_nodes.py                       # push n8n/cloud/nodes/*.js to the live workflow
.\.venv\Scripts\python.exe scripts\setup_n8n_hindsight.py 1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk
.\.venv\Scripts\python.exe scripts\bootstrap_incidents_tab.py                    # headers only
```

**Environment bootstrap:**
```powershell
copy .env.example .env
.\.venv\Scripts\python.exe scripts\merge_amdocs_env.py   # merges N8N_API_KEY etc. from the sibling course repo
```

## Conventions

- Python 3.12, FastAPI + **pydantic v2**, 12-factor config (everything overridable via env in `app/config.py`), structured JSON logs + correlation IDs, `pytest`.
- Keep all enrichment/scoring logic **deterministic and unit-tested**. Extraction is the only place an LLM is allowed to make a decision.
- Node 20 for the Cloud Code-node tests.
- After changing the API, run the enrichment pytest suite; after changing a Cloud Code node, run the node-body tests. Don't open a PR red — CI gates on `test.yml`.

## Guardrails (do not)

- **Never commit secrets.** `.env` and `*.key` are gitignored; live Gemini / Google OAuth credentials exist **only** in the n8n Cloud credential vault, never in the repo.
- **`n8n/cloud/nodes/*.js` is the source of truth.** Edit node bodies there, then run `sync_n8n_cloud_nodes.py`. Do not hand-edit nodes in the Cloud UI.
- **Don't break the data contracts:** the Google Sheet `Incidents` tab headers and the JSON schema the Code nodes parse. Sheet headers (assignment §7.2 + cyber bonus):
  `document_id | filename | file_type | processed_at | classification | department | sentiment | confidence_score | summary | routing_tag | sensitivity | action_items | cvss_score | cve_ids`
- **Don't commit scratch:** `batch_submit_resp*.txt`, `.playwright-mcp/`, git worktrees.

## Gotchas

- **n8n Cloud disables the Execute Command node**, so the Python extractor runs only on the self-hosted stack. On Cloud, use n8n's native *Extract from File* (text-only); the Gemini **Vision** branch needs the self-hosted extractor to pull embedded images.
- **OAuth lives in n8n, not the repo.** `GEMINI_API_KEY` / `GOOGLE_OAUTH_*` in the amdocs course files are placeholders/empty. The repo `.env` is only for scripts and dev MCP.
- **Gemini 404** → switch the model URL to `gemini-3-flash-preview`.
- **n8n Cloud (grading):** instance `https://reemmor.app.n8n.cloud`, workflow `aYEv22StywIPL3Rq`, registry sheet `1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk` tab `Incidents`. Full manual steps in `docs/SETUP-GUIDE.md`.
