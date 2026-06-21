# HINDSIGHT — Gemini Vision Prompt (dashboard screenshot → metrics)

The multimodal upgrade. Postmortems almost always embed Grafana / Datadog /
CloudWatch screenshots — the actual evidence of the incident. Text-only models
throw that signal away. HINDSIGHT sends each embedded image to
`gemini-3-flash` (vision) and recovers the quantitative story the graph tells.

Used by the optional **Vision branch** in the n8n workflow. The output is folded
into `vision_notes` and passed to the main extraction prompt, so the LLM's
final record is grounded in the graph, not just the prose.

---

## Prompt

```
You are analysing a screenshot taken from an engineering incident postmortem.
It is most likely a monitoring dashboard (Grafana, Datadog, CloudWatch, Kibana)
or an architecture diagram.

Return ONLY valid JSON with these fields:

{
  "image_kind": "one of: [metric-dashboard, architecture-diagram, log-screenshot, alert, other]",
  "metric_name": "what the chart measures (e.g. 'error rate', 'p99 latency', 'request volume') or null",
  "unit": "the unit shown (%, ms, req/s, count) or null",
  "anomaly_observed": "describe the spike/dip/flatline and roughly when, or null",
  "approx_peak_value": "the approximate peak/worst value visible, with unit, or null",
  "approx_baseline_value": "the approximate normal/baseline value, with unit, or null",
  "time_window": "the time range shown on the x-axis, or null",
  "annotations": ["any visible deploy markers, alert lines, or text annotations"],
  "one_line_summary": "one sentence an SRE could paste into the postmortem"
}

RULES:
- Read values off the axes as precisely as the resolution allows; approximate is fine.
- If it is an architecture diagram, set image_kind accordingly and summarise the
  components and the likely failure path, leaving metric fields null.
- Do not hallucinate values you cannot see. Use null when unreadable.
```

---

## n8n HTTP Request body (JSON, vision)

```json
{
  "contents": [
    {
      "parts": [
        { "inline_data": { "mime_type": "image/png", "data": "{{ $json.image_base64 }}" } },
        { "text": "<the vision prompt above>" }
      ]
    }
  ],
  "generationConfig": { "temperature": 0.1, "responseMimeType": "application/json" }
}
```

The `image_base64` value comes from the extractor's `images[]` output, read and
base64-encoded by a small Code node (or `Read Binary File` → `Move Binary Data`).
Each image's `one_line_summary` is concatenated into `vision_notes` for the main
extraction call.
