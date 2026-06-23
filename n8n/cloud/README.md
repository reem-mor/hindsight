# HINDSIGHT — n8n Cloud deployment

Cyber incident log pipeline for **n8n Cloud** (no local FS / Execute Command).

- **Workflow:** `HINDSIGHT — Postmortem Intelligence (Cloud)` · id `aYEv22StywIPL3Rq`
- **Instance:** https://reemmor.app.n8n.cloud

## Flow

Form upload → Prepare Document (PDF `inline_data` vision) → Gemini extract → Parse →
HINDSIGHT Enrich → Compose Outputs → Sheets + (SEV1? → Page On-Call | digest email).

## Source of truth

| File | Node |
|---|---|
| `nodes/prepare.js` | Prepare Document |
| `nodes/parse.js` | Parse Gemini JSON |
| `nodes/enrich.js` | HINDSIGHT Enrich |
| `nodes/compose.js` | Compose Outputs |

Deploy to Cloud:

```powershell
python scripts/sync_n8n_cloud_nodes.py
```

`workflow.ts` is the Workflow-SDK reference; live bodies are synced from `nodes/*.js`.

## Tests

```bash
node tests/test_node_bodies.mjs   # 58 checks, no n8n required
```

## Sheet columns (assignment §7.2)

`document_id`, `filename`, `file_type`, `processed_at`, `classification`, `department`,
`sentiment`, `confidence_score`, `summary`, `routing_tag`, `sensitivity`, `action_items`,
`cvss_score`, `cve_ids`
