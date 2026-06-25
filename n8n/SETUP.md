# Importing the HINDSIGHT workflow into n8n

`hindsight_workflow.json` is a ready-to-import workflow. It will import cleanly; the only
post-import work is attaching three credentials and pointing two nodes at your own
Sheet / inbox. Everything else (nodes, wiring, prompts, retry policy) is pre-built.

> Node `typeVersion`s target n8n 1.6x+. If your instance is older, n8n will open the node
> with its installed version and flag anything it wants you to re-pick — this never blocks the
> import, it just surfaces a yellow dot on the affected node.

---

## 1. Import

n8n → **Workflows** → top-right **⋯** → **Import from File** → choose
`hindsight_workflow.json`. You'll see the graph below.

```
📂 New postmortem → 🗜 Extract → Parse → Has image? ─true→ 👁 Gemini Vision ─┐
                                              └false────────────────────────┴→ Attach notes
   → Build prompt → 🧠 Gemini extract → Parse JSON → ⚙️ Enrich (FastAPI)
   → Compose record ┬→ Flatten → 📊 Append to registry
                    ├→ Markdown→file → 💾 Write output doc
                    └→ SEV1? ─true→ 🚨 Page on-call
                              └false→ 📧 Send digest
```

## 2. Credentials (3)

| Credential | Type | Used by |
|---|---|---|
| **Gemini API** | HTTP Header Auth — name `x-goog-api-key`, value = your key from [aistudio.google.com](https://aistudio.google.com/app/apikey) | `🧠 Gemini — extract incident`, `👁 Gemini Vision` |
| **Google Sheets** | Google Sheets OAuth2 | `📊 Append to registry` |
| **Gmail** | Gmail OAuth2 | `🚨 Page on-call`, `📧 Send digest` |

Open each of those nodes and select the matching credential from the dropdown
(they import with a `REPLACE_*` placeholder so they're easy to spot).

> The Gemini nodes read the key as `{{ $credentials.geminiApi.apiKey }}`. If you prefer,
> you can instead paste the key directly into the `x-goog-api-key` header value — but never
> commit it.

## 3. Point it at your Sheet & inboxes

- **📊 Append to registry** → set *Document* to your Google Sheet and *Sheet* to a tab
  named `Incidents`. Create the tab with these headers in row 1 (matches the dashboard schema):

  ```
  document_id | filename | file_type | processed_at | classification | department |
  sentiment | confidence_score | summary | routing_tag | sensitivity | action_items |
  cvss_score | cve_ids
  ```
  Mapping mode is **auto-map**, so as long as the headers match, every field lands in the
  right column.

- **🚨 Page on-call** → set *To* to your on-call address.
- **📧 Send digest** → set *To* to your reliability/team address.

## 4. Paths (Execute Command + file nodes)

The workflow assumes the repo is reachable from the n8n runtime at `/data`:

```
/data/incoming_docs      ← watched folder (drop postmortems here)
/data/output_docs        ← rendered .md summaries land here
/data/tmp_images         ← extracted dashboard images (transient)
/data/extractors/extract_document.py
```

`docker-compose.yml` at the repo root already mounts the repo to `/data` inside the n8n
container and installs PyMuPDF/python-docx, so if you bring the stack up with compose these
paths exist with no extra work. Running n8n elsewhere? Edit the `path` on **📂 New postmortem**
and the `--image-dir` / script path on **🗜 Extract** to wherever the repo lives.

## 5. Point the enrichment URL at the service

**⚙️ Enrich (FastAPI)** posts to `http://enrichment-api:8000/enrich` — the service name on
the compose network. If you run the API somewhere else, change that URL (e.g.
`http://localhost:8000/enrich`).

## 6. Activate

Toggle **Active** (top-right). The Local File Trigger polls `incoming_docs/`. Drop a file
from `samples/` to watch a run end-to-end. First run with a SEV1 sample (e.g.
`vuln_scan_critical_openssl.md`) to see the paging branch fire.

### Automated local setup (Docker)

Uses the **same sheet ID and credential names as Cloud** (OAuth still requires one Google sign-in per credential type on local).

```powershell
copy .env.example .env   # HINDSIGHT_SHEET_ID, GEMINI_API_KEY, N8N_LOCAL_* 

.\.venv\Scripts\python.exe scripts\setup_local_stack.py
# or step-by-step:
#   import_local_credentials.py → import_selfhosted_workflow.py → publish → restart
```

**OAuth (once per machine):** Credentials → create with **exact Cloud names**:
- `Google Sheets Amdocs Course API` → Connect → pick registry sheet / `Incidents` tab
- `Gmail Amdocs course API` → Connect → same Gmail as Cloud

Stable local credential IDs (override in `.env` if n8n assigns different IDs):
`hindsight-gemini-local-001`, `hindsight-sheets-local-001`, `hindsight-gmail-local-001`

---

> **Self-hosted build note.** The official n8n image is now a Docker Hardened Image
> (Alpine without `apk`), so the extractor's Python deps are installed in a matching
> `alpine:3.22` builder stage and copied in (see [`n8n/Dockerfile`](Dockerfile)).
> `docker compose up --build` handles this for you. On n8n Cloud, the Python extractor
> isn't used at all — swap that node for the native *Extract from File* node.

### What's already wired for you
- **Retry / rate-limits** — the main Gemini extraction node: `retryOnFail`, 5 tries, 3 s backoff (survives 429s). The optional Vision node retries 3× / 2 s with `onError: continue`.
- **Multimodal** — embedded dashboard images are auto-detected and read by Gemini Vision;
  `onError: continue` means a vision miss degrades gracefully instead of failing the run.
- **Severity is recomputed** — the FastAPI rubric overrides the reported severity; SEV1 pages
  immediately (the "sensitivity alerting" bonus, applied to incident severity).
- **Correlation id** — minted in *Parse extraction* and carried through Gemini → enrich → Sheets
  so one incident is traceable across every hop.
