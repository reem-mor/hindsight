# Why Google credentials are not in MCP (and what we did instead)

## Short answer

**Google Gemini, Sheets, and Gmail do not live in `amdocs-ai-course` git files** — they live in
**n8n Cloud’s encrypted credential vault**, bound to your instance at `reemmor.app.n8n.cloud`.

There is no separate “Google MCP” in this project. n8n nodes call Google using OAuth tokens
stored server-side when you connected credentials in the n8n UI.

| Secret | In amdocs `.env` files? | Where it actually is |
|---|---|---|
| `N8N_API_KEY` | Placeholder in `.env.example`; real key in **Windows user env** | Copied into `hindsight/.env` via `scripts/merge_amdocs_env.py` |
| `GEMINI_API_KEY` | **Placeholder** in all course `.env` files | n8n credential `Google Gemini(PaLM) Api account` (id `466Fl1znBcikPxtF`) |
| Google Sheets OAuth | **Not in repo** | n8n `Google Sheets Amdocs Course API` (id `6CH1fQ50fz9t2M9G`) |
| Gmail OAuth | **Not in repo** | n8n `Gmail Amdocs course API` (id `klYiZaTrlUMuEunt`) |
| `GOOGLE_OAUTH_*` | Empty in `oz_veruach_bot/.env` | Not available to copy |

MCP servers configured in `.cursor/mcp.json` are: **n8n-workflows**, **playwright**, AWS,
Perplexity, etc. — not a raw Google Sheets/Gmail MCP.

## What was automated (2026-06-22)

1. **Merged env** from amdocs → `hindsight/.env` (`N8N_API_KEY`, `AWS_PROFILE`, etc.)
2. **Fixed** `N8N_API_URL` → `https://reemmor.app.n8n.cloud` (amdocs example URL was wrong)
3. **Created** Google Spreadsheet via n8n + your existing Sheets OAuth:
   - ID: `1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk`
   - URL: https://docs.google.com/spreadsheets/d/1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk/edit
   - See `docs/hindsight-sheet-id.txt`

## What you still need in n8n UI (2 minutes)

1. Open **Append to Registry** → set Document to spreadsheet ID above (if not auto-patched)
2. Rename default tab to **`Incidents`** or add tab `Incidents` + header row (see SETUP-GUIDE)
3. **Activate** workflow `aYEv22StywIPL3Rq`
4. If Gemini 404s: change model to `gemini-3-flash-preview` on *Gemini — Extract Incident*

Or run:

```powershell
cd c:\dev\hindsight
.\.venv\Scripts\python.exe scripts\setup_n8n_hindsight.py 1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk
```

## Already verified on your instance

- Gemini credential: bound
- Sheets credential: bound
- Gmail credential: bound → `reem.mor3@gmail.com`
- Dry-runs `481`, `483`: success
