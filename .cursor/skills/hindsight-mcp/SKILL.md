---
name: hindsight-mcp
description: Configure and verify HINDSIGHT MCP servers (n8n Cloud, Playwright, AWS) and run E2E checks. Use when setting up .cursor/mcp.json, validating n8n workflows, or capturing submission screenshots.
version: 0.1.0
---

# HINDSIGHT MCP & E2E

## Quick path

1. Copy `.env.example` → `.env` and set `N8N_API_KEY`, `AMDOCS_COURSE_ROOT`.
2. Reload MCP in Cursor after editing `.env`.
3. Run automated checks:

```bash
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
node n8n\cloud\tests\test_node_bodies.mjs
.\.venv\Scripts\python.exe scripts\verify_n8n_cloud.py
node scripts\capture_screenshots.mjs
```

## n8n Cloud

- Workflow id: `aYEv22StywIPL3Rq`
- Use `n8n-workflows` MCP to `get_workflow_details`, deploy updates from `n8n/cloud/workflow.ts`, and pin dry-runs.
- Gemini HTTP credential must be selected in the UI.

## Screenshots

| File | Source |
|---|---|
| `docs/screenshot-dashboard.png` | `scripts/capture_screenshots.mjs` |
| `docs/screenshot-fastapi.png` | same |
| `docs/screenshot-workflow.png` | Playwright MCP → n8n editor |
| `docs/screenshot-execution.png` | Playwright MCP → execution view |
| `docs/screenshot-sheet.png` | Playwright MCP → Google Sheets |
| `docs/screenshot-email.png` | Gmail UI or inbox screenshot |

Full MCP server list: `docs/MCP-SETUP.md`.
