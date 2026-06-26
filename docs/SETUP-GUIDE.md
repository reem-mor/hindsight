# HINDSIGHT — Setup guide (cyber incident logs)

**Workflow:** `aYEv22StywIPL3Rq` on `https://reemmor.app.n8n.cloud`  
**Scenario:** Cybersecurity incident logs (SIEM, vuln scans, phishing, intrusion writeups)

---

## 1. Architecture (two paths)

| Path | Trigger | Enrichment | Output |
|---|---|---|---|
| **n8n Cloud** (grading) | Form upload | Code node (`enrich.js`) | Google Sheets + Gmail |
| **Self-hosted** | `incoming_docs/` watcher | FastAPI `/enrich` | Sheets + Gmail + `output_docs/` |

Both use Gemini 3 Flash extraction and the same SecOps routing rubric (CVSS floor, `routing_tag`, sensitivity).

### Supported file formats

| Format | n8n Cloud (grading) | Self-hosted (`incoming_docs/`) |
|---|---|---|
| `.pdf` | Yes (native inline upload) | Yes (+ embedded-image Vision branch) |
| `.md`, `.txt`, `.markdown` | Yes | Yes |
| `.zip` | Yes (batch fan-out, `.md`/`.txt` inside; max **25** files per archive) | Yes |
| `.docx` | **No** — rejected in `prepare.js` with a clear error | Yes (`extractors/extract_document.py`) |

DOCX on Cloud would be UTF-8 garbage through the text path; use `docker compose` for Word documents. Nested ZIPs inside a batch archive are not extracted — only top-level `.md`/`.txt` entries.

---

## 2. Why Google credentials are not in the repo

`GEMINI_API_KEY` and `GOOGLE_OAUTH_*` in amdocs course files are **placeholders or empty**. Live OAuth for Sheets and Gmail lives in the **n8n Cloud credential vault** only. You verify/reconnect in the n8n UI — you cannot copy them from `amdocs-ai-course` files.

What *does* merge from amdocs: `N8N_API_KEY`, optional dev keys (`CONTEXT7_API_KEY`, etc.) via `scripts/merge_amdocs_env.py`.

**MCP (optional dev):** `.cursor/mcp.json` — `n8n-workflows`, `playwright`, `context7`. Reload MCP after editing `.env`.

---

## 3. Local setup (once)

```powershell
cd c:\dev\hindsight
copy .env.example .env
.\.venv\Scripts\python.exe scripts\merge_amdocs_env.py
```

| Variable | Source |
|---|---|
| `N8N_API_KEY` | n8n Cloud → Settings → API |
| `N8N_API_URL` | Defaults to `https://reemmor.app.n8n.cloud` (never overwritten by placeholder) |
| `HINDSIGHT_SHEET_ID` | Optional; default `1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk` |
| `N8N_SHEETS_CRED_ID` | **Required only** by `setup_n8n_hindsight.py` / `bootstrap_incidents_tab.py` — the n8n Google Sheets credential **ID** (from the n8n vault, not a secret). These scripts fail fast if it is unset; no vault IDs are hardcoded in the repo. |

```powershell
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
node n8n\cloud\tests\test_node_bodies.mjs
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py
```

---

## 4. n8n Cloud checklist

Open: https://reemmor.app.n8n.cloud/workflow/aYEv22StywIPL3Rq

### Credentials (verify in UI)

| Credential | Nodes |
|---|---|
| `Google Gemini(PaLM) Api account` | Gemini — Extract Incident |
| `Google Sheets Amdocs Course API` | Append to Registry |
| `Gmail Amdocs course API` | Page On-Call / Postmortem Filed |

### Google Sheet

Spreadsheet: `1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk` · tab **`Incidents`**

**Row 1 headers** (assignment §7.2 + cyber bonus):

```
document_id | filename | file_type | processed_at | classification | department | sentiment | confidence_score | summary | routing_tag | sensitivity | action_items | cvss_score | cve_ids
```

Patch workflow + node bodies from repo:

```powershell
.\.venv\Scripts\python.exe scripts\sync_n8n_cloud_nodes.py
# Sheet ID + Incidents tab bootstrap:
.\.venv\Scripts\python.exe scripts\setup_n8n_hindsight.py 1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk
# Or tab/headers only:
.\.venv\Scripts\python.exe scripts\bootstrap_incidents_tab.py
```

### Troubleshooting: Append to Registry fails

| Symptom | Fix |
|---|---|
| **Sheet/tab not found (`Incidents`)** | Run `bootstrap_incidents_tab.py` (writes headers on `Sheet1`) then **rename tab to `Incidents`**. Or rename `Sheet1` → `Incidents` and paste headers manually. |
| **Unexpected fields in node input** | In **Append to Registry** set Handling extra fields → **Ignore them**, or run `sync_n8n_cloud_nodes.py` (adds **Flatten for Sheets** node). |
| **LangChain `tool_use_id` in AI chat** | n8n workflow **assistant** error — ignore it. Use **Executions** tab for real failures. |
| **Permission denied** | Reconnect **Google Sheets Amdocs Course API**; share spreadsheet with that Google account. |

### Activate + live test

**Production form URL:** `https://reemmor.app.n8n.cloud/form/21593841-f8b8-43a2-88a8-8595ad3e2f39` (see 📸 `docs/screenshot-form-cloud.png`)

1. Toggle workflow **Active**
2. Submit `samples/vuln_scan_critical_openssl.md` via the form above
4. Confirm row in Sheet + email at `reem.mor3@gmail.com`

If Gemini 404: model URL is set to `gemini-3-flash-preview` in repo + Cloud patch script. Re-run `patch_cloud_workflow.py` after pulling.

**Known limitation:** if Gemini succeeds but Sheets/Gmail fails, n8n retry may append a duplicate row or resend email. There is no Cloud-side dedupe by `document_id` today.

### Bonus: multi-model compare (BON-6)

Wired into the live Cloud workflow as a **non-blocking parallel branch** off `Parse Gemini JSON`:
`Gemini — Extract (Pro)` (`gemini-3.1-pro-preview`) → `Parse Gemini Pro` → `Compare Models`. Every
Pro-branch node is `onError=continueRegularOutput`, so a Pro outage/429 can't block the registry
write or SEV1 alert. Deploy/refresh via `scripts/sync_n8n_cloud_nodes.py`. Also exposed as
`POST /compare` on the enrichment API.

---

## 5. Self-hosted (bonus path)

```powershell
docker compose up --build -d
.\.venv\Scripts\python.exe n8n\build_workflow.py
.\.venv\Scripts\python.exe scripts\import_selfhosted_workflow.py
```

Import `n8n/hindsight_workflow.json`, configure credentials per `n8n/SETUP.md`, drop files in `incoming_docs/`.

---

## 6. Bonus features (all 8)

| Bonus | Implementation |
|---|---|
| **BON-1 Vision** | Self-hosted Vision branch; cloud PDF `inline_data`; `samples/vuln_scan_sev1_critical_rce.pdf` |
| **BON-2 Daily Digest** | Import `n8n/cloud/digest_workflow.json` (run `build_digest_workflow.py` first); cron 08:00 UTC |
| **BON-3 Dashboard** | `dashboard/index.html`; optional live CSV via `?csv=` query param |
| **BON-4 Retry** | Gemini 5× / 3s — verified by `audit_n8n_cloud.py` |
| **BON-5 Semantic Search** | Apply `migrations/001_pgvector_incidents.sql`; set `SUPABASE_*` in `.env`; `POST /search` |
| **BON-6 Compare** | Wired in Cloud wf: `Gemini — Extract (Pro)` → `Parse Gemini Pro` → `Compare Models` (non-blocking); also `POST /compare`; `compare_models.js` |
| **BON-7 Batch** | Form accepts `.zip`; `prepare.js` fans out; fixture `samples/batch_incidents.zip` |
| **BON-8 Alerting** | `patch_cloud_workflow.py` — pages on SEV1, confidential, or escalate |

---

## 7. Scripts

| Script | Purpose |
|---|---|
| `merge_amdocs_env.py` | Pull keys into `.env` |
| `setup_n8n_hindsight.py` | Patch spreadsheet ID on Cloud workflow |
| `sync_n8n_cloud_nodes.py` | Push `n8n/cloud/nodes/*.js` + Flatten node to Cloud |
| `patch_cloud_workflow.py` | BON-7 zip accept, BON-8 alert routing, BON-4 retry |
| `activate_n8n_cloud.py` | Activate grading workflow |
| `build_digest_workflow.py` | Inject digest JS into digest workflow JSON |
| `bootstrap_incidents_tab.py` | Create `Incidents` tab + header row via n8n |
| `audit_n8n_cloud.py` | Health report → `docs/n8n-cloud-audit.json` |
| `capture_screenshots.mjs` | Dashboard + FastAPI screenshots |
| `render_architecture.mjs` | Export `docs/architecture.png` |

---

## 8. Related docs

- [`docs/traceability-matrix.md`](traceability-matrix.md) — grading map
- [`docs/VALIDATION.md`](VALIDATION.md) — test commands + evidence
- [`n8n/cloud/README.md`](../n8n/cloud/README.md) — Cloud node bodies
