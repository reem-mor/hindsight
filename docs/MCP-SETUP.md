# MCP & tooling setup (Oz VeRuach course parity)

This repo mirrors the MCP servers from `amdocs-ai-course` so Cursor agents can manage n8n
Cloud, capture Playwright evidence, and use the same AWS / research tooling during grading.

## 1. Environment

Copy `.env.example` → `.env` and fill in the values you use locally. **Never commit `.env`.**

| Variable | Used by |
|---|---|
| `N8N_API_URL` | `n8n-workflows` MCP (`https://reemmor.app.n8n.cloud`) |
| `N8N_API_KEY` | `n8n-workflows` MCP — create in n8n → Settings → API |
| `AMDOCS_COURSE_ROOT` | `course-tools` MCP (sibling repo path) |
| `AWS_PROFILE` / `AWS_REGION` | `aws-api`, `bedrock-kb` |
| `CONTEXT7_API_KEY` | `context7` |
| `PERPLEXITY_API_KEY` | `perplexity` |
| `LOVABLE_CLIENT_ID` | `lovable` (optional) |
| `GEMINI_API_KEY` | Live Gemini calls (n8n credential or local tests) |

## 2. Cursor MCP config

Project MCP servers live in [`.cursor/mcp.json`](../../.cursor/mcp.json). After editing
`.env`, reload MCP in Cursor: **Settings → MCP → Reload**.

### Servers

| Server | Purpose |
|---|---|
| `n8n-workflows` | Deploy, validate, execute workflows on n8n Cloud |
| `playwright` | Browser automation for screenshots / E2E |
| `aws-api` | AWS API operations |
| `bedrock-kb` | Bedrock knowledge-base retrieval |
| `aws-knowledge` | AWS documentation MCP (HTTP) |
| `course-tools` | Lecture 08 FastMCP demo tools (requires `AMDOCS_COURSE_ROOT`) |
| `context7` | Up-to-date library docs |
| `perplexity` | Web-grounded research |
| `sequential-thinking` | Structured reasoning helper |
| `lovable` | Lovable.dev integration (optional) |

## 3. Verification scripts (no MCP required)

```bash
# Automated suites
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
node n8n\cloud\tests\test_node_bodies.mjs

# n8n Cloud API smoke (needs N8N_API_KEY in .env)
.\.venv\Scripts\python.exe scripts\verify_n8n_cloud.py

# Local screenshots → docs/screenshot-*.png
node scripts\capture_screenshots.mjs
```

## 4. n8n Cloud workflow

- **Name:** `HINDSIGHT — Postmortem Intelligence (Cloud)`
- **ID:** `aYEv22StywIPL3Rq` (draft)
- **Source:** `n8n/cloud/workflow.ts` + `n8n/cloud/nodes/*.js`

Before activation: bind Gemini HTTP credential on *Gemini — Extract Incident*, create the
`Incidents` sheet tab (28 columns from `Compose Outputs`). Sheets + Gmail nodes were bound in
the initial deployment — re-check in the n8n UI after any credential rotation.

## 5. Skills

Course MCP integration guidance is vendored under `.cursor/skills/mcp-integration/` (from
`amdocs-ai-course`). Use when adding or debugging MCP servers.
