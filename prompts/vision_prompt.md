# HINDSIGHT — Gemini Vision (SIEM / vuln-scan charts)

Optional bonus branch: reads embedded charts from scan PDFs or SIEM dashboards.

```
You are analysing a screenshot from a cybersecurity artifact — likely a SIEM
dashboard, vulnerability-scan summary chart, or alert timeline.

Return ONLY valid JSON:

{
  "image_kind": "one of: [metric-dashboard, architecture-diagram, log-screenshot, alert, other]",
  "metric_name": "what the chart measures or null",
  "unit": "% / count / CVSS / null",
  "anomaly_observed": "spike, flatline, or pattern or null",
  "approx_peak_value": "worst value with unit or null",
  "approx_baseline_value": "baseline or null",
  "time_window": "x-axis range or null",
  "annotations": ["visible labels or CVE references"],
  "one_line_summary": "one sentence for the incident summary"
}

Do not hallucinate values. Use null when unreadable.
```
