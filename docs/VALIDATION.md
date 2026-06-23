# HINDSIGHT — Validation & Test Report

**Status:** ✅ automated suites green · **Scenario:** cyber incident logs · **Workflow:** `aYEv22StywIPL3Rq`

## 1. Summary

| Suite | What it proves | Checks | Result |
|---|---|---:|:---:|
| FastAPI `pytest` | `/enrich` brain: SecOps routing, CVSS floor, sensitivity, routing_tag | 48 | ✅ |
| Cloud Code nodes `node` | Exact JS in `n8n/cloud/nodes/*.js` | 58 | ✅ |
| `audit_n8n_cloud.py` | Live workflow nodes, credentials, sheet ID, executions | 1 report | ✅ |
| Live E2E (form → Gemini → Sheet → Gmail) | Full external path | — | ✋ activate + submit sample |

## 2. Reproduce

```powershell
cd c:\dev\hindsight
.\.venv\Scripts\python.exe -m pytest services\enrichment-api -q
node n8n\cloud\tests\test_node_bodies.mjs
.\.venv\Scripts\python.exe scripts\audit_n8n_cloud.py
.\.venv\Scripts\python.exe scripts\sync_n8n_cloud_nodes.py   # push node bodies to Cloud
```

## 3. Bonus challenge verification

| Bonus | Proof |
|---|---|
| **Vision** | Self-hosted: `Has dashboard image?` → Gemini Vision (`retryOnFail` 5×). Cloud: PDF `inline_data` in Prepare Document. Sample PDF: `samples/make_cyber_pdf_sample.py` |
| **Dashboard** | `dashboard/index.html` — CVSS badges, sensitivity chart, routing_tag breakdown; data from `dashboard/data/incidents.sample.json` or published Sheet CSV |
| **Retry** | `geminiExtract` `maxTries: 5`, `waitBetweenTries: 3000`; enrich HTTP `maxTries: 3` in self-hosted workflow |
| **Sensitivity alert** | `Is SEV1?` → Page On-Call with `[CONFIDENTIAL ESCALATE]` subject; CVSS ≥ 9 floors to SEV1 (`test_critical_cvss_floors_to_sev1_and_escalates`) |

## 4. Cloud deployment parity

Canonical Code-node source: `n8n/cloud/nodes/*.js`. Deploy with `scripts/sync_n8n_cloud_nodes.py`
(PUT strips extra `settings` fields that Cloud API rejects).

Pinned dry-runs (pre-cyber trim): executions `481`, `483` — re-run live after activation.

## 5. Live E2E checklist

**Prerequisite:** Google Sheet tab must be named **`Incidents`** (rename `Sheet1` after running `bootstrap_incidents_tab.py`).

1. Activate workflow `aYEv22StywIPL3Rq`
2. Submit `samples/vuln_scan_critical_openssl.md` via form Production URL
3. Confirm Sheet row (assignment columns) + Gmail at configured address
4. Record execution id below:

```
Live execution ID: pending — last failure 503 (Incidents tab missing). Headers bootstrapped on Sheet1; rename tab then re-run.
```

After success, update this line with the green execution id from n8n **Executions**.
