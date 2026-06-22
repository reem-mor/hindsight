# HINDSIGHT — n8n Cloud deployment

A Cloud-compatible build of the HINDSIGHT pipeline, deployed live to an **n8n Cloud** instance
(which has no Execute Command / local FS). It over-delivers on the brief in two ways:

1. **Real Gemini Vision on Cloud** — PDFs are sent to `gemini-3-flash` natively as `inline_data`,
   so embedded dashboard / Grafana charts are read by the model directly (no separate OCR).
2. **Zero extra infrastructure** — the enrichment brain (the faithful port of the FastAPI
   `/enrich` service) runs in-process inside a Code node, so nothing else needs hosting. Swap
   that node for an HTTP call if you prefer to run the microservice.

- **Workflow:** `HINDSIGHT — Postmortem Intelligence (Cloud)` · id `aYEv22StywIPL3Rq` · personal project · **draft**

## Flow

`Form (file upload)` → `Prepare Document` (build multimodal/text Gemini request) →
`Gemini — Extract Incident` (HTTP, strict JSON, 5× retry) → `Parse Gemini JSON` (fence-strip + guard) →
`HINDSIGHT Enrich` (deterministic re-scoring) → `Compose Outputs` (registry row + postmortem + emails) →
fan-out to **Append to Registry** (Google Sheets) and **Is SEV1?** → **Page On-Call** (true) / **Postmortem Filed** (false).

## Files

| Path | Purpose |
|---|---|
| `workflow.ts` | The n8n Workflow-SDK source that was deployed |
| `nodes/prepare.js` | Code node 1 — intake, PDF→`inline_data` vision, prompt assembly |
| `nodes/parse.js` | Code node 2 — defensive JSON parsing of the model output |
| `nodes/enrich.js` | Code node 3 — the enrichment brain (port of `services/enrichment-api`) |
| `nodes/compose.js` | Code node 4 — registry row, postmortem markdown, two email variants |
| `tests/test_node_bodies.mjs` | 46 edge-case + guardrail tests against the bodies above |

## Test the deployed logic

```bash
node tests/test_node_bodies.mjs     # 61/61 passed — no n8n required
```

## One-time setup before activating

1. **Gemini credential** — open *Gemini — Extract Incident* and pick the Gemini credential
   (HTTP Request nodes can't be bound programmatically). Sheets + both Gmail nodes are already bound.
2. **Registry** — open *Append to Registry*, choose your Google Sheet, and add an `Incidents`
   tab whose header row matches the 28 columns emitted by `Compose Outputs`.

> ⚠️ **Embedding note:** n8n stores Code-node bodies by *cooking* the template literal, so a raw
> backtick embed corrupts regex escapes (`\b` → backspace). `workflow.ts` embeds each body with
> backslashes doubled so the cooked value equals the source byte-for-byte. See
> [`docs/VALIDATION.md` §5](../../docs/VALIDATION.md).
