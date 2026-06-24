# HINDSIGHT — Architecture

**Contract:** the LLM extracts; the service decides. Gemini returns strict JSON; the enrichment
brain (FastAPI or inline `enrich.js`) applies the CVSS floor, sensitivity keywords, department
routing, and `routing_tag` deterministically.

![Figure 1 — End-to-end architecture](architecture.png)

## Pipeline sequence (DIAG-2 — REQ-P1→P6)

```mermaid
flowchart LR
  P1[Form / incoming_docs] --> P2[Extract text + images]
  P2 --> P3[Gemini 3 Flash JSON]
  P3 --> P4[HINDSIGHT Enrich]
  P4 --> P5[Append to Registry]
  P4 --> P6a[output_docs markdown]
  P4 --> P6b[Gmail Page or Digest]
```

Cloud node names: `Submit a Postmortem` → `Prepare Document` → `Gemini — Extract Incident` →
`Parse Gemini JSON` → `HINDSIGHT Enrich` → `Compose Outputs` → `Flatten for Sheets` /
`Page On-Call (SEV1)` / `Postmortem Filed`.

## Enrichment decision logic (DIAG-3)

```mermaid
flowchart TD
  IN[Gemini JSON + CVSS + entities] --> CVSS{cvss_score >= 9?}
  CVSS -->|yes| SEV1[Floor computed_severity SEV1]
  CVSS -->|no| RUB[Apply severity rubric]
  SEV1 --> SENS[Sensitivity keywords + CVSS >= 7]
  RUB --> SENS
  SENS --> RT{routing_tag}
  RT -->|SEV1 or CVSS>=9| ESC[escalate + page-oncall]
  RT -->|low confidence / review| NR[needs-review]
  RT -->|clean minor| AA[auto-approved]
```

## Dual deployment paths

```mermaid
flowchart LR
  subgraph cloud [Cloud grading path]
    Form[Submit incident log]
    Prepare[Prepare Document]
    Gemini[Gemini Extract]
    EnrichJS[HINDSIGHT Enrich JS]
    Sheets[Google Sheets]
    Gmail[Gmail]
    Form --> Prepare --> Gemini --> EnrichJS --> Sheets
    EnrichJS --> Gmail
  end
  subgraph local [Self-hosted Vision path]
    Watch[incoming_docs]
    Extract[Python extractor]
    Vision[Gemini Vision]
    API[FastAPI enrich]
    Out[output_docs]
    Watch --> Extract --> Vision
    Extract --> API --> Out
  end
```

## Bonus data flows (DIAG-4)

### BON-1 Gemini Vision (self-hosted)

```mermaid
flowchart LR
  PDF[PDF with chart] --> Ext[extract_document.py]
  Ext --> Img[PNG per page]
  Img --> Vision[Gemini Vision HTTP]
  Ext --> Text[extracted_text]
  Text --> Gemini[Main JSON extract]
  Vision --> Notes[Vision notes merged]
  Notes --> Gemini
```

### BON-3 Live Dashboard

```mermaid
flowchart LR
  Sheet[Google Sheets Incidents] --> Pub[Publish to web CSV]
  Pub --> Dash[dashboard/index.html ?csv=]
  Dash --> Charts[SEV CVSS sensitivity routing charts]
```

### BON-8 Sensitivity alerting

```mermaid
flowchart TD
  E[Enrich output] --> IF{SEV1 OR confidential OR escalate?}
  IF -->|yes| Page[Page On-Call Gmail priority high]
  IF -->|no| Digest[Postmortem Filed standard email]
  E --> Sheets[Append to Registry]
```

See [bonus-challenges.md](bonus-challenges.md) for all eight bonuses, tests, and evidence paths.

### BON-5 Semantic Search

```mermaid
flowchart LR
  Ingest[POST /enrich] --> Embed[Gemini embedding]
  Embed --> Upsert[Supabase pgvector]
  Query[POST /search] --> QEmbed[Query embed]
  QEmbed --> RPC[match_hindsight_incidents]
  RPC --> TopK[Top-k hits]
```

### BON-6 Multi-model Compare

```mermaid
flowchart LR
  Text[Document text] --> Flash[Gemini 3 Flash]
  Text --> Pro[Gemini 3 Pro]
  Flash --> Diff[compare_extractions]
  Pro --> Diff
  Diff --> Report[Compare report / POST /compare]
```

### BON-2 Daily Digest

```mermaid
flowchart LR
  Cron[Schedule 08:00 UTC] --> Read[Read Incidents sheet]
  Read --> Agg[digest_aggregate 24h window]
  Agg --> Mail[Gmail HTML digest]
```

### BON-7 Multi-file Batch

```mermaid
flowchart LR
  Zip[Upload .zip] --> Unzip[prepare.js unzip fan-out]
  Unzip --> Loop[Per-file Gemini + enrich]
  Loop --> Rows[One Sheets row per file]
```

## Cyber/SecOps hybrid layer

- **CVSS floor:** `>= 9.0 → SEV1`, `>= 7.0 → SEV2`, `>= 4.0 → SEV3` — authoritative over Gemini severity.
- **SecOps routing:** `vulnerability-scan`, `phishing`, `intrusion`, etc. map via `service_catalog.yaml`.
- **Sensitivity:** `public` / `internal` / `confidential` via keyword + CVSS + CVE signals.
- **Alerting (BON-8):** `Is SEV1?` pages on SEV1, `confidential`, or `routing_tag=escalate`.

The Python brain (`services/enrichment-api`) and deployed JavaScript (`n8n/cloud/nodes/enrich.js`)
implement identical logic, verified by parallel test suites.

## Component summary

| Layer | Technology | Responsibility |
|---|---|---|
| Orchestration | n8n Cloud + self-hosted | Triggers, Gemini calls, Sheets, Gmail |
| Extraction | PyMuPDF, python-docx, prepare.js | Text + images; ZIP fan-out |
| Reasoning | Gemini 3 Flash (+ Vision) | Strict JSON extraction |
| Decision | FastAPI / enrich.js | CVSS floor, sensitivity, routing_tag |
| Registry | Google Sheets | One row per document |
| Search | pgvector / in-memory | Semantic incident lookup (BON-5) |
| Insight | dashboard/index.html | Severity, CVSS, sensitivity, routing charts |

Render Figure 1 PNG: `node scripts/render_architecture.mjs`
