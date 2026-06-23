---
name: hindsight-mcp
description: Configure and verify HINDSIGHT MCP servers (n8n Cloud, Playwright, context7) and run E2E checks. Use when setting up .cursor/mcp.json, validating n8n workflows, or capturing submission screenshots.
version: 0.2.0
---

# HINDSIGHT MCP & E2E

## Quick path

1. Copy `.env.example` → `.env`; run `scripts/merge_amdocs_env.py`; set `N8N_API_KEY`.
2. Reload MCP in Cursor after editing `.env`.
3. Run automated checks:

```powershell
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
node n8n\cloud\tests\test_node_bodies.mjs
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py
python scripts\sync_n8n_cloud_nodes.py
node scripts\capture_screenshots.mjs
```

## n8n Cloud

- Workflow id: `aYEv22StywIPL3Rq`
- Canonical Code bodies: `n8n/cloud/nodes/*.js` — deploy with `sync_n8n_cloud_nodes.py`
- Sheet: `1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk`

## Screenshots

| File | Source |
|---|---|
| `docs/screenshot-dashboard.png` | `scripts/capture_screenshots.mjs` |
| `docs/screenshot-fastapi.png` | same |
| `docs/screenshot-workflow.png` | Playwright MCP → n8n editor |
| `docs/screenshot-execution.png` | Playwright MCP → execution view |
| `docs/screenshot-sheet.png` | Playwright MCP → Google Sheets |
| `docs/screenshot-email.png` | Gmail UI |

Setup details: `docs/SETUP-GUIDE.md`.
