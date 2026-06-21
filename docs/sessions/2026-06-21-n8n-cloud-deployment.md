# Session log — Live n8n Cloud deployment & validation (2026-06-21)

Deployed the HINDSIGHT pipeline live into an n8n **Cloud** instance, ported the enrichment
brain into the workflow, proved it end-to-end, and added regression coverage to the repo.

## Goal

Take the completed HINDSIGHT repo (FastAPI enrichment + importable n8n JSON) and stand up a
**Cloud-runnable** variant that works without local infrastructure, then validate it.

## What was built / done

1. **Cloud-compatible workflow** (`n8n/cloud/workflow.ts`, 15 nodes) authored with the n8n
   Workflow SDK and deployed via MCP into the personal project. Form upload → Gemini extract →
   parse → enrich → compose → Google Sheets registry + SEV1 paging / digest email.
2. **Two genuine upgrades over the brief:**
   - PDFs sent to Gemini as native `inline_data` → real Vision on Cloud (reads embedded charts).
   - Enrichment brain ported into a Code node (`nodes/enrich.js`) → end-to-end with **zero**
     extra infrastructure; a faithful JS mirror of `services/enrichment-api`.
3. **Solved a non-obvious deployment bug — template-literal cooking.** A probe workflow proved
   n8n stores Code-node bodies by taking the *cooked* template value: `\b` became a literal
   backspace, `\n` a real newline. A naïve embed would have silently corrupted every regex in
   the enrichment brain. Fix: embed each body with backslashes doubled so the cooked value
   reconstructs the source byte-for-byte; verified by evaluation pre-deploy and via
   `get_workflow_details` post-deploy. (Full write-up: `docs/VALIDATION.md` §5.)
4. **Credentials.** Bound Google Sheets + both Gmail nodes to existing project credentials via
   the MCP `setNodeCredential` op. The Gemini HTTP node is selected in-UI (HTTP Request nodes
   reject programmatic credential binding).
5. **Live validation (pinned dry-runs; external nodes mocked):**
   - Run `481` — author SEV2 → computed **SEV1** (score 13), routed to Payments-SRE, confidential,
     439.8% error-budget burn, **Page On-Call** branch.
   - Run `483` — author SEV3 → computed **SEV3** (score 4), routed to DevEx, **Postmortem Filed**
     branch (paging skipped). Both IF branches proven.
6. **Regression coverage added to the repo:**
   - `services/enrichment-api/tests/test_edge_cases.py` — 12 adversarial/edge/guardrail tests
     (suite now **32**).
   - `n8n/cloud/tests/test_node_bodies.mjs` — **46** edge-case + guardrail tests run against the
     exact deployed Code-node JavaScript.
7. **Docs:** `docs/VALIDATION.md` (evidence trail), `n8n/cloud/README.md` (deploy specifics),
   this session log.

## Verified facts / decisions

- Deployed into personal project `NPuAWxoY544fPaul` (co-located with the course credentials).
- Model: `gemini-3-flash`, `temperature 0.1`, `responseMimeType application/json`, 5× retry.
- Recurrence is ephemeral in the Cloud Code-node variant; the Google Sheet is the durable record.
- Sensitivity/impact matching is keyword-based and recall-favoring (no negation parsing) — a
  deliberate compliance-safe default, documented as a known limitation.
- Left as a **draft** by request; activate after selecting the Gemini credential and creating
  the registry `Incidents` tab.

## Result

Workflow deployed and proven on n8n Cloud; 80 automated checks green (32 pytest + 46 node-body
+ 2 live executions); repo updated to reflect exactly what runs in production.
