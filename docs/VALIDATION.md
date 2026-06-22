# HINDSIGHT — Validation & Test Report

**Status:** ✅ all suites green &nbsp;·&nbsp; **Date:** 2026-06-21 &nbsp;·&nbsp; **Live workflow:** `aYEv22StywIPL3Rq` (n8n Cloud, draft)

This report is the evidence trail for the HINDSIGHT submission: what is tested, how to
reproduce it, and proof that the system deployed to n8n Cloud behaves identically to the
graded enrichment service.

---

## 1. Summary

| Suite | What it proves | Checks | Result |
|---|---|---:|:---:|
| FastAPI enrichment — `pytest` | The graded `/enrich` brain: routing, severity rubric, sensitivity, SLO, recurrence, cyber CVSS | 48 | ✅ |
| Deployed Cloud Code nodes — `node` | The **exact** JavaScript running in n8n Cloud, hammered with edge cases + guardrails | 61 | ✅ |
| Live workflow dry-runs — n8n Cloud | True end-to-end execution on the deployed workflow, **both** routing branches | 2 | ✅ |
| n8n Cloud API smoke — `verify_n8n_cloud.py` | Workflow `aYEv22StywIPL3Rq` nodes + credential binding | 1 | ✅ |
| **Total automated** | | **112** | ✅ |

## 2. How to reproduce

```bash
# Graded enrichment microservice (Python)
cd services/enrichment-api
pip install -r requirements.txt
pytest -q                       # 48 passed

# The actual code deployed to the n8n Cloud Code nodes (no n8n needed — globals are mocked)
node n8n/cloud/tests/test_node_bodies.mjs    # 61/61 passed

# n8n Cloud API smoke (N8N_API_KEY in .env or environment)
python scripts/verify_n8n_cloud.py
```

## 3. Coverage matrix

**Severity rubric** — upgrade *and* downgrade both raise `severity_review` when the rubric
disagrees with the author; tier / multi-jurisdiction / high-impact-language / downtime /
security weights; SEV1–SEV4 band boundaries.
**Routing** — alias resolution, duplicate collapsing, unknown-service → incident-type
fallback (`security → Security-IR`, `data-incident → Compliance-Eng`).
**Jurisdictions** — `GLOBAL`-only is kept but earns no regulatory weight; `GLOBAL` is
dropped once a real jurisdiction appears; union of reported + service-implied jurisdictions.
**Data sensitivity** — security / data-incident / PII / monetary / regulatory / multi-jurisdiction
signals all escalate to `confidential` (recall-favoring; see §7).
**SLO error budget** — per-service monthly budget, burn %, breach boundary tested at
*exactly* 50% of budget (`>=`), and null budget when no catalogued service matches.
**Recurrence fingerprint** — 12-hex, deterministic, **word-order independent** (tokens are
sorted), and distinct for a different root cause.
**Confidence** — penalties for missing root cause / action items / services / timing metrics;
floors at 0; drives the `needs-review` tag.
**Action accounting** — whitespace-only owner counts as unowned; `P0` detection is
case-insensitive.
**Robustness** — empty payload defaults safely; a ~20k-character multibyte/emoji summary
does not crash.

### Guardrails & error handling (explicitly tested)

- **Extraction prompt** (`prompts/extraction_prompt.md`, embedded in `Prepare Document`): strict
  JSON-only output, controlled vocabulary, `null`-not-empty, and an instruction to pick the
  *lower* severity when unsure — the deterministic rubric re-scores afterwards.
- **Gemini HTTP node:** `responseMimeType: application/json` forces structured output;
  `retryOnFail` 5× with 3s backoff absorbs transient model/network failures.
- **`Parse Gemini JSON` node:** strips ```` ``` ```` fences (with or without a `json` tag) and
  throws a clear, surfaced error on malformed or empty model output. *(tested: clean JSON,
  fenced JSON, fenced-without-language, malformed → throws, missing `candidates` → throws.)*
- **`Prepare Document` node:** reads the first binary key dynamically with a base64 fallback,
  and raises an explicit "No file uploaded" error rather than failing obscurely.
- **Enrichment brain:** total defaulting — never throws on missing or foreign fields; the
  re-scoring is deterministic and independent of the LLM.

## 4. Live end-to-end validation (n8n Cloud)

Two pinned dry-runs on the deployed workflow. Code and IF nodes execute for real; the Gemini,
Sheets, and Gmail nodes are pinned, so **no external calls, writes, or emails** occur.

### Run `481` — SEV1 upgrade → paging branch
Author labelled it **SEV2**; HINDSIGHT computed **SEV1** (score 13) and raised `severity-review`.
Routed to **Payments-SRE**, `confidential`, jurisdictions `MGM, NJ-DGE, UKGC`, SLO budget
21.6 min → **439.8% burn → breach**, fingerprint `c20419625ad1`, actions 3 / 2 unowned / 2 open-P0,
tags `auto-filed, exec-escalation, page-oncall, regulatory-review, severity-review, unowned-actions, budget-breach`.
`Is SEV1?` → **Page On-Call** executed; **Postmortem Filed** skipped. ✔

### Run `483` — minor incident → file branch
Author labelled it **SEV3**; HINDSIGHT computed **SEV3** (score 4), no review. Routed to **DevEx**
(`grafana` → `internal-tooling`), jurisdictions `GLOBAL`, SLO **1.4% burn, no breach**, fingerprint
`26b681548491`, tag `auto-filed` only, no paging. `Is SEV1?` → **Postmortem Filed** executed;
**Page On-Call** skipped. ✔ *(Demonstrates the IF false branch.)*

## 5. Deployment fidelity — the template-literal cooking problem (and the fix)

The n8n Workflow SDK stores a Code node's `jsCode` by taking the **cooked** value of the
template literal it is embedded in. This was confirmed empirically with a throwaway probe
workflow: a `\b` written inside a backtick literal was stored as a literal **backspace**
(`0x08`), and `\n` as a real newline. A naïve embedding would therefore have silently
corrupted every regex (`\b`, `\s`) and broken the inline string literals in the enrichment
brain — with no error at deploy time and a wrong answer at run time.

**Fix:** embed each Code body as a backtick literal with **every backslash doubled**
(`\` → `\\`), so the cooked value reconstructs the source byte-for-byte while the code stays
human-readable (real newlines preserved). This was verified two ways: (1) by evaluating each
embedded body's cooked value against the source file before deploy — `prepare`, `parse`,
`enrich`, `compose` all byte-identical; and (2) after deploy via `get_workflow_details`, where
the stored regexes are intact (`/\bdata (loss|breach|leak)\b/`, `/[_\-\/]+/g`, `/\s+/g`).

## 6. Repository ↔ deployment parity

The deployed Cloud enrichment (`n8n/cloud/nodes/enrich.js`) is a faithful JavaScript port of
the graded FastAPI brain (`services/enrichment-api`). The 46 node-body tests assert the same
outcomes the 32 pytest cases assert of the Python service — identical severity bands, routing
decisions, sensitivity calls, SLO math, fingerprints, and tags. The Cloud variant additionally
(a) runs Gemini **Vision natively** on PDF bytes via `inline_data`, and (b) carries the
enrichment **in-process**, so the workflow needs zero extra infrastructure to run end-to-end.

## 7. Known limitations (by design / scope)

- **Keyword sensitivity & impact matching does not parse negation.** A summary containing
  "no regulatory impact" still matches `regulatory` and is flagged `confidential`. This is an
  intentional, recall-favoring choice: for a UKGC / NJ-DGE / MGM operator, surfacing a
  postmortem for a brief human compliance glance is the safe default. A negation-aware NLP
  pass is the natural follow-up.
- **Recurrence is ephemeral in the Cloud Code-node variant** (`seen_count` is always 1
  in-memory). The Google Sheets registry is the durable record; the FastAPI variant keeps a
  process-lifetime counter. Production would back recurrence with the Sheet or a datastore.
- **Deployed as a draft.** The Gemini credential is selected in the UI (HTTP Request nodes
  reject programmatic credential binding) and the registry Sheet + `Incidents` tab are
  provisioned once before activation. Sheets + both Gmail credentials are already bound.
