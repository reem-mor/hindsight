# HINDSIGHT — Setup guide & session summary

**Saved:** 2026-06-22 · **Workflow:** `aYEv22StywIPL3Rq` on `https://reemmor.app.n8n.cloud`

This document captures what we built, what is already verified, and **exactly what you
must configure yourself** before a live end-to-end run (real Gemini call → Sheet row → Gmail).

---

## 1. What we built (conversation summary)

| Layer | What it does | Where |
|---|---|---|
| **n8n Cloud pipeline** | Form upload → Gemini extract → enrich → Sheets + SEV1 email branch | `n8n/cloud/` · workflow id `aYEv22StywIPL3Rq` |
| **n8n self-hosted pipeline** | File trigger + Python extractor + Vision + FastAPI enrich | `n8n/hindsight_workflow.json` + `docker compose` |
| **Enrichment brain** | Severity rubric, CVSS floor, SecOps routing, SLO, sensitivity | `services/enrichment-api/` |
| **Cyber hybrid** | CVSS ≥9 → SEV1, vuln-scan/SIEM/phishing types, `routing_tag` | models + `enrich.js` parity |
| **Dashboard** | Severity, sensitivity, routing, CVSS from CSV or sample JSON | `dashboard/index.html` |
| **MCP + scripts** | n8n API verify, Playwright screenshots, course-parity MCP | `.cursor/mcp.json`, `scripts/` |
| **Tests** | 48 pytest + 61 node-body + API smoke | `docs/VALIDATION.md` |

**Design principle:** LLM extracts; deterministic service decides (severity, routing, CVSS).

---

## 2. Live audit results (your n8n Cloud — today)

Run anytime: `.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py`

| Check | Status | Detail |
|---|---|---|
| Workflow exists | ✅ | `HINDSIGHT — Postmortem Intelligence (Cloud)` |
| All 15 nodes | ✅ | Present |
| Gemini credential | ✅ | `Google Gemini(PaLM) Api account` (`466Fl1znBcikPxtF`) |
| Google Sheets OAuth | ✅ | `Google Sheets Amdocs Course API` |
| Gmail OAuth | ✅ | `Gmail Amdocs course API` → **To:** `reem.mor3@gmail.com` |
| Pinned dry-runs | ✅ | Executions `481`, `483` = `success` |
| **Workflow active** | ⚠️ **YOU** | `active: false` (still draft) |
| **Spreadsheet ID** | ⚠️ **YOU** | **Empty** — node still says “PASTE your HINDSIGHT registry spreadsheet ID here” |
| **Gemini model** | ⚠️ **YOU** | URL uses `gemini-3-flash` — use `gemini-3-flash-preview` if API returns 404 |
| Playwright UI login | ⚠️ **YOU** | Browser automation hits sign-in (no session cookie) — use your logged-in browser for canvas screenshots |

Full JSON: [`n8n-cloud-audit.json`](n8n-cloud-audit.json)

---

## 3. What you must configure (checklist)

### A. Local repo (`c:\dev\hindsight`)

| Step | Where | Action |
|---|---|---|
| 1 | Copy `.env.example` → `.env` | Set at minimum: `N8N_API_KEY`, `N8N_API_URL`, `AMDOCS_COURSE_ROOT` |
| 2 | Cursor → Settings → MCP | Reload MCP after editing `.env` |
| 3 | Python venv | `py -3.12 -m venv .venv` then `pip install -r services/enrichment-api/requirements.txt` |
| 4 | Verify | `pytest services/enrichment-api -q` and `node n8n/cloud/tests/test_node_bodies.mjs` |

`N8N_API_KEY`: n8n Cloud → **Settings** → **API** → Create API key.

### B. n8n Cloud — **blocking for live E2E**

Open: https://reemmor.app.n8n.cloud/workflow/aYEv22StywIPL3Rq

#### B1. Create the Google Sheet registry ⚠️ **REQUIRED**

1. Google Sheets → **New spreadsheet** → name it e.g. `HINDSIGHT Incident Registry`.
2. Add tab **`Incidents`** with **row 1 headers** (exact names — auto-map depends on this):

```
document_id | processed_at | correlation_id | source_filename | incident_title | incident_type | status | reported_severity | computed_severity | severity_score | severity_review | department | routed_teams | affected_services | affected_jurisdictions | sensitivity | slo_target | budget_burn_pct | budget_breach | recurrence_fingerprint | routing_tags | action_items_total | action_items_unowned | open_p0_actions | confidence_score | ttr_minutes | summary
```

3. Copy the **spreadsheet ID** from the URL:  
   `https://docs.google.com/spreadsheets/d/<SPREADSHEET_ID>/edit`
4. In n8n → node **Append to Registry**:
   - Credential: `Google Sheets Amdocs Course API` (already selected)
   - **Document:** paste spreadsheet ID
   - **Sheet:** `Incidents`
   - Operation: Append row · Mapping: auto-map

5. **(Optional, for dashboard)** File → Share → Publish to web → CSV → paste URL into `SHEETS_CSV_URL` at top of `dashboard/index.html`.

#### B2. Confirm Gmail targets

Nodes **Page On-Call (SEV1)** and **Postmortem Filed**:

- Credential: `Gmail Amdocs course API` ✅
- **To:** currently `reem.mor3@gmail.com` — change if you want a different inbox.

#### B3. Gemini model (if live extract fails)

Node **Gemini — Extract Incident** → URL:

- Rubric string: `.../models/gemini-3-flash:generateContent`
- If 404: change to `.../models/gemini-3-flash-preview:generateContent`

Credential `Google Gemini(PaLM) Api account` is already bound ✅.

#### B4. Activate the workflow ⚠️ **REQUIRED**

Top-right toggle **Inactive → Active**.  
Until active, the **Submit a Postmortem** form URL will not accept live uploads.

Form URL (after activate): open node **Submit a Postmortem** → **Test URL** / production form link.

#### B5. First live test

1. Upload `samples/vuln_scan_critical_openssl.md` or `samples/payments_sev1_checkout_outage.md` via the form.
2. Check execution log (all green).
3. Confirm new row in `Incidents` tab.
4. SEV1 sample → email `[SEV1 PAGE] ...` in Gmail; SEV3 sample → digest email.

### C. Self-hosted Docker stack (optional — local file trigger)

| Step | Where | Action |
|---|---|---|
| 1 | `docker compose up --build` | Starts n8n + enrichment-api on compose network |
| 2 | Import | `n8n/hindsight_workflow.json` into **local** n8n (not Cloud) |
| 3 | Credentials | Gemini HTTP header, Sheets OAuth, Gmail OAuth — see [`n8n/SETUP.md`](../n8n/SETUP.md) |
| 4 | Drop file | `incoming_docs/` |

Cloud and self-hosted are **two deployments** — configure both only if you need both.

### D. Google Cloud / API console (behind n8n credentials)

You do **not** paste keys into the repo. n8n stores them:

| Integration | n8n credential type | Where to create key / OAuth |
|---|---|---|
| Gemini | `googlePalmApi` or HTTP `x-goog-api-key` | [Google AI Studio](https://aistudio.google.com/app/apikey) |
| Google Sheets | `googleSheetsOAuth2Api` | Google Cloud Console → APIs → Sheets API enabled + OAuth client used by n8n |
| Gmail | `gmailOAuth2` | Google Cloud Console → Gmail API enabled + OAuth consent |

Your instance already has course credentials; re-authorize if you see “credential expired” on a node.

---

## 4. What agents cannot do for you

| Action | Why |
|---|---|
| Log into n8n UI | Playwright session is not authenticated (sign-in page) |
| Create your Google Sheet | Needs your Google account in browser |
| Send real Gmail | Needs OAuth token in n8n + active workflow + successful run |
| Activate workflow without your UI click | API can update, but you should verify nodes first |
| Store secrets in git | `.env` and n8n credentials stay out of repo |

---

## 5. Quick verification commands

```powershell
cd c:\dev\hindsight

# Unit + node parity
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
node n8n\cloud\tests\test_node_bodies.mjs

# n8n Cloud API
.\.venv\Scripts\python.exe scripts\verify_n8n_cloud.py
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py
.\.venv\Scripts\python.exe scripts\list_n8n_executions.py

# Regenerate screenshots
node scripts\capture_screenshots.mjs
node scripts\capture_n8n_evidence.mjs
node scripts\capture_registry_evidence.mjs
```

---

## 6. Submission artifacts (already in repo)

| Artifact | Path |
|---|---|
| Screenshots | `docs/screenshot-*.png` |
| Traceability | `docs/traceability-matrix.md` |
| Edge cases | `docs/edge-case-matrix.md` |
| Validation report | `docs/VALIDATION.md` |
| MCP setup | `docs/MCP-SETUP.md` |

---

## 7. Your minimum “go live” order

1. **Create Sheet + paste ID** in **Append to Registry** ← only true blocker found in audit  
2. **Fix Gemini model** if first live run fails on model name  
3. **Activate** workflow  
4. **Submit** a SEV1 sample via form → confirm **Sheet row + email**  
5. **(Optional)** Publish sheet CSV → dashboard live data  

After step 4, re-run `scripts/audit_n8n_cloud.py` — `Workflow active` should show `True` and Sheets document should show your spreadsheet ID.

---

## 8. Related docs

- Cloud deployment: [`n8n/cloud/README.md`](../n8n/cloud/README.md)
- Self-hosted import: [`n8n/SETUP.md`](../n8n/SETUP.md)
- Architecture: [`docs/architecture.md`](architecture.md)
- Prior deployment session: [`docs/sessions/2026-06-21-n8n-cloud-deployment.md`](sessions/2026-06-21-n8n-cloud-deployment.md)
