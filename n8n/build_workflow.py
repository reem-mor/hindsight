#!/usr/bin/env python3
"""Builds the importable HINDSIGHT n8n workflow JSON.
Written as a generator so the emitted JSON is always structurally valid.
"""
import json, uuid

def nid():  # n8n uses uuid-ish node ids
    return str(uuid.uuid4())

def node(name, ntype, version, x, y, params=None, extra=None):
    n = {
        "parameters": params or {},
        "id": nid(),
        "name": name,
        "type": ntype,
        "typeVersion": version,
        "position": [x, y],
    }
    if extra:
        n.update(extra)
    return n

def sticky(content, x, y, w=300, h=220, color=7):
    return {
        "parameters": {"content": content, "height": h, "width": w, "color": color},
        "id": nid(),
        "name": "Note " + nid()[:6],
        "type": "n8n-nodes-base.stickyNote",
        "typeVersion": 1,
        "position": [x, y],
    }

# ---- column x positions ----
X = {c: 200 + c * 260 for c in range(13)}
Y0 = 300

nodes = []

trigger = node(
    "📂 New postmortem", "n8n-nodes-base.localFileTrigger", 1, X[0], Y0,
    {
        "triggerOn": "folder",
        "path": "/data/incoming_docs",
        "events": ["add"],
        "options": {"usePolling": True, "ignored": "**/.*"},
    },
)

extract = node(
    "🗜 Extract text + images", "n8n-nodes-base.executeCommand", 1, X[1], Y0,
    {
        "command": '=python3 /data/extractors/extract_document.py "{{ $json.path }}" '
                   '--image-dir /data/tmp_images',
    },
)

parse_extract = node(
    "Parse extraction", "n8n-nodes-base.code", 2, X[2], Y0,
    {
        "jsCode": (
            "// stdout of the extractor is a single JSON object\n"
            "const raw = $input.first().json.stdout;\n"
            "let doc;\n"
            "try { doc = JSON.parse(raw); }\n"
            "catch (e) { throw new Error('Extractor did not return JSON: ' + raw?.slice(0,200)); }\n"
            "if (!doc.ok) { throw new Error('Extraction failed for ' + doc.filename); }\n"
            "// correlation id ties logs across Gemini + enrichment + sheets\n"
            "const corr = 'hs-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2,7);\n"
            "return [{ json: { ...doc, correlation_id: corr,\n"
            "  has_images: Array.isArray(doc.images) && doc.images.length > 0 } }];"
        ),
    },
)

has_images = node(
    "Has dashboard image?", "n8n-nodes-base.if", 2, X[3], Y0,
    {
        "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "loose"},
            "conditions": [{
                "id": nid(),
                "leftValue": "={{ $json.has_images }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            }],
            "combinator": "and",
        },
        "options": {},
    },
)

vision = node(
    "👁 Gemini Vision — read chart", "n8n-nodes-base.httpRequest", 4.2, X[4], Y0 - 130,
    {
        "method": "POST",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Content-Type", "value": "application/json"},
            {"name": "x-goog-api-key", "value": "={{ $credentials.geminiApi.apiKey }}"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": (
            '={\n'
            '  "contents": [{ "parts": [\n'
            '    { "text": "Read this SRE dashboard screenshot. Return ONLY JSON: '
            '{image_kind, metric_name, unit, anomaly_observed, approx_peak_value, '
            'approx_baseline_value, time_window, one_line_summary}." },\n'
            '    { "inline_data": { "mime_type": "image/png",'
            ' "data": "{{ $binary.data0 ? $binary.data0.toString(\'base64\') : \'\' }}" } }\n'
            '  ]}],\n'
            '  "generationConfig": { "temperature": 0.1, "responseMimeType": "application/json" }\n'
            '}'
        ),
        "options": {},
    },
)
vision["credentials"] = {"httpHeaderAuth": {"id": "REPLACE_GEMINI", "name": "Gemini API"}}
vision["retryOnFail"] = True
vision["maxTries"] = 3
vision["waitBetweenTries"] = 2000
vision["onError"] = "continueRegularOutput"

merge_vision = node(
    "Attach vision notes", "n8n-nodes-base.code", 2, X[5], Y0,
    {
        "jsCode": (
            "// Fold any vision JSON into the extraction item as vision_notes.\n"
            "const items = $input.all();\n"
            "const base = items.find(i => i.json.extracted_text) || items[0];\n"
            "let visionNotes = '';\n"
            "const v = items.find(i => i.json.candidates || i.json.metric_name);\n"
            "if (v) {\n"
            "  try {\n"
            "    const t = v.json.candidates?.[0]?.content?.parts?.[0]?.text || JSON.stringify(v.json);\n"
            "    visionNotes = typeof t === 'string' ? t : JSON.stringify(t);\n"
            "  } catch (e) { visionNotes = ''; }\n"
            "}\n"
            "return [{ json: { ...base.json, vision_notes: visionNotes } }];"
        ),
    },
)

build_prompt = node(
    "Build extraction prompt", "n8n-nodes-base.code", 2, X[6], Y0,
    {
        "jsCode": (
            "const j = $input.first().json;\n"
            "const prompt = `You are HINDSIGHT, an SRE postmortem analyst. Read the incident "
            "document and return ONLY a valid JSON object matching this schema exactly:\\n"
            "{incident_title, summary, severity (SEV1|SEV2|SEV3|SEV4), incident_type, status, "
            "affected_services[], affected_jurisdictions[], root_cause, trigger, detection_method, "
            "entities:{people[],teams[],systems[],dates[],error_codes[]}, "
            "action_items:[{action,owner,priority}], contributing_factors[], sentiment, "
            "blameless_quality, confidence_score, "
            "metrics:{detected_at,resolved_at,ttd_minutes,ttr_minutes,customer_impact}}\\n"
            "When unsure of severity pick the LOWER one (a rubric re-scores it). Use null for unknowns.\\n\\n"
            "VISION NOTES (from embedded dashboards):\\n${j.vision_notes || 'none'}\\n\\n"
            "DOCUMENT:\\n${j.extracted_text}`;\n"
            "return [{ json: { ...j, prompt } }];"
        ),
    },
)

gemini = node(
    "🧠 Gemini — extract incident", "n8n-nodes-base.httpRequest", 4.2, X[7], Y0,
    {
        "method": "POST",
        "url": "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Content-Type", "value": "application/json"},
            {"name": "x-goog-api-key", "value": "={{ $credentials.geminiApi.apiKey }}"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": (
            '={\n'
            '  "contents": [{ "parts": [{ "text": {{ JSON.stringify($json.prompt) }} }] }],\n'
            '  "generationConfig": { "temperature": 0.1, "responseMimeType": "application/json" }\n'
            '}'
        ),
        "options": {},
    },
)
gemini["credentials"] = {"httpHeaderAuth": {"id": "REPLACE_GEMINI", "name": "Gemini API"}}
gemini["retryOnFail"] = True
gemini["maxTries"] = 5
gemini["waitBetweenTries"] = 3000  # backs off on 429 rate limits

parse_gemini = node(
    "Parse Gemini JSON", "n8n-nodes-base.code", 2, X[8], Y0,
    {
        "jsCode": (
            "const prev = $('Build extraction prompt').first().json;\n"
            "const resp = $input.first().json;\n"
            "let txt = resp.candidates?.[0]?.content?.parts?.[0]?.text;\n"
            "if (!txt) throw new Error('Gemini returned no text');\n"
            "txt = txt.replace(/^```json/,'').replace(/```$/,'').trim();\n"
            "let g; try { g = JSON.parse(txt); } catch(e){ throw new Error('Bad JSON from Gemini: '+txt.slice(0,200)); }\n"
            "// shape payload for the enrichment API\n"
            "g.filename = prev.filename;\n"
            "g.correlation_id = prev.correlation_id;\n"
            "return [{ json: g }];"
        ),
    },
)

enrich = node(
    "⚙️ Enrich (FastAPI)", "n8n-nodes-base.httpRequest", 4.2, X[9], Y0,
    {
        "method": "POST",
        "url": "=http://enrichment-api:8000/enrich",
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": "={{ JSON.stringify($json) }}",
        "options": {},
    },
)
enrich["retryOnFail"] = True
enrich["maxTries"] = 3
enrich["waitBetweenTries"] = 1500

build_row = node(
    "Compose record + outputs", "n8n-nodes-base.code", 2, X[10], Y0,
    {
        "jsCode": (
            "const g = $('Parse Gemini JSON').first().json;\n"
            "const e = $input.first().json;\n"
            "const services = (e.affected_services_resolved || []).join(', ');\n"
            "const md = `# ${g.incident_title}\\n\\n"
            "**Computed severity:** ${e.computed_severity}  (reported ${e.reported_severity})\\n"
            "**Team:** ${e.department}    **Sensitivity:** ${e.sensitivity}\\n"
            "**Services:** ${services}\\n"
            "**Jurisdictions:** ${(e.affected_jurisdictions||[]).join(', ')}\\n\\n"
            "## Summary\\n${g.summary}\\n\\n## Root cause\\n${g.root_cause || 'n/a'}\\n\\n"
            "## Routing\\n${(e.routing_tags||[]).join(', ')}\\n`;\n"
            "const row = {\n"
            "  document_id: e.document_id,\n"
            "  processed_at: e.processed_at,\n"
            "  incident_title: g.incident_title,\n"
            "  incident_type: g.incident_type,\n"
            "  reported_severity: e.reported_severity,\n"
            "  computed_severity: e.computed_severity,\n"
            "  department: e.department,\n"
            "  affected_services: services,\n"
            "  affected_jurisdictions: (e.affected_jurisdictions||[]).join(', '),\n"
            "  sensitivity: e.sensitivity,\n"
            "  ttr_minutes: g.metrics?.ttr_minutes ?? '',\n"
            "  status: g.status || 'resolved',\n"
            "  recurrence_fingerprint: e.recurrence_fingerprint,\n"
            "  routing_tags: (e.routing_tags||[]).join(', '),\n"
            "  action_item_total: e.action_item_total ?? '',\n"
            "  action_items_without_owner: e.action_items_without_owner ?? '',\n"
            "  summary: (g.summary||'').slice(0,500),\n"
            "  confidence_score: e.confidence_score ?? g.confidence_score ?? ''\n"
            "};\n"
            "const isSev1 = e.computed_severity === 'SEV1';\n"
            "return [{ json: { row, markdown: md, is_sev1: isSev1, e, g,\n"
            "  out_path: `/data/output_docs/${e.document_id}.md` } }];"
        ),
    },
)

sheets = node(
    "📊 Append to registry", "n8n-nodes-base.googleSheets", 4, X[11], Y0,
    {
        "operation": "append",
        "documentId": {"__rl": True, "mode": "list", "value": "REPLACE_WITH_SHEET_ID"},
        "sheetName": {"__rl": True, "mode": "list", "value": "Incidents"},
        "columns": {
            "mappingMode": "autoMapInputData",
            "value": {},
            "matchingColumns": [],
        },
        "options": {},
    },
)
sheets["credentials"] = {"googleSheetsOAuth2Api": {"id": "REPLACE_SHEETS", "name": "Google Sheets"}}
# feed the flat row to sheets
prep_sheet = node(
    "Flatten row", "n8n-nodes-base.code", 2, X[10] + 130, Y0 + 150,
    {"jsCode": "return [{ json: $input.first().json.row }];"},
)

write_out = node(
    "💾 Write output doc", "n8n-nodes-base.readWriteFile", 1, X[11], Y0 + 200,
    {
        "operation": "write",
        "fileName": "={{ $('Compose record + outputs').first().json.out_path }}",
        "dataPropertyName": "data",
        "options": {},
    },
)
# the write node needs binary; build it
to_binary = node(
    "Markdown → file", "n8n-nodes-base.code", 2, X[10] + 130, Y0 + 330,
    {
        "jsCode": (
            "const j = $('Compose record + outputs').first().json;\n"
            "const buff = Buffer.from(j.markdown, 'utf8');\n"
            "return [{ json: { out_path: j.out_path },\n"
            "  binary: { data: { data: buff.toString('base64'),\n"
            "    mimeType: 'text/markdown', fileName: j.document_id + '.md' } } }];"
        ),
    },
)

sev_if = node(
    "SEV1?", "n8n-nodes-base.if", 2, X[12], Y0,
    {
        "conditions": {
            "options": {"caseSensitive": True, "typeValidation": "loose"},
            "conditions": [{
                "id": nid(),
                "leftValue": "={{ $json.is_sev1 }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "true", "singleValue": True},
            }],
            "combinator": "and",
        },
        "options": {},
    },
)

page = node(
    "🚨 Page on-call (SEV1)", "n8n-nodes-base.gmail", 2, X[12] + 260, Y0 - 110,
    {
        "operation": "send",
        "sendTo": "=oncall@example.com",
        "subject": "=🚨 SEV1 PAGE — {{ $json.g.incident_title }} ({{ $json.e.department }})",
        "emailType": "html",
        "message": (
            "=<h2 style='color:#FF4D5E'>SEV1 incident filed</h2>"
            "<p><b>{{ $json.g.incident_title }}</b></p>"
            "<p>Team: {{ $json.e.department }} · Services: "
            "{{ ($json.e.affected_services_resolved||[]).join(', ') }}</p>"
            "<p>Jurisdictions: {{ ($json.e.affected_jurisdictions||[]).join(', ') }}</p>"
            "<p>{{ $json.g.summary }}</p>"
            "<p>Routing: {{ ($json.e.routing_tags||[]).join(', ') }}</p>"
            "<hr><i>HINDSIGHT · auto-paged because computed severity = SEV1</i>"
        ),
        "options": {"priority": "high"},
    },
)
page["credentials"] = {"gmailOAuth2": {"id": "REPLACE_GMAIL", "name": "Gmail"}}

summary_mail = node(
    "📧 Send digest", "n8n-nodes-base.gmail", 2, X[12] + 260, Y0 + 110,
    {
        "operation": "send",
        "sendTo": "=reliability@example.com",
        "subject": "=[{{ $json.e.computed_severity }}] {{ $json.g.incident_title }}",
        "emailType": "html",
        "message": (
            "=<h2>Postmortem processed</h2>"
            "<p><b>{{ $json.g.incident_title }}</b> — {{ $json.e.computed_severity }}</p>"
            "<p>Team: {{ $json.e.department }} · Sensitivity: {{ $json.e.sensitivity }}</p>"
            "<p>{{ $json.g.summary }}</p>"
            "<p>Routing: {{ ($json.e.routing_tags||[]).join(', ') }}</p>"
            "<hr><i>HINDSIGHT · n8n + Gemini 3</i>"
        ),
        "options": {},
    },
)
summary_mail["credentials"] = {"gmailOAuth2": {"id": "REPLACE_GMAIL", "name": "Gmail"}}

nodes = [trigger, extract, parse_extract, has_images, vision, merge_vision,
         build_prompt, gemini, parse_gemini, enrich, build_row, prep_sheet,
         sheets, to_binary, write_out, sev_if, page, summary_mail]

# ---------- connections ----------
def conn(src, dst, src_out=0, dst_in=0):
    return src, dst, src_out, dst_in

links = [
    ("📂 New postmortem", "🗜 Extract text + images"),
    ("🗜 Extract text + images", "Parse extraction"),
    ("Parse extraction", "Has dashboard image?"),
    # IF true -> vision ; IF false -> straight to merge(passthrough)
    ("Has dashboard image?", "👁 Gemini Vision — read chart", 0),
    ("Has dashboard image?", "Attach vision notes", 1),
    ("👁 Gemini Vision — read chart", "Attach vision notes"),
    ("Attach vision notes", "Build extraction prompt"),
    ("Build extraction prompt", "🧠 Gemini — extract incident"),
    ("🧠 Gemini — extract incident", "Parse Gemini JSON"),
    ("Parse Gemini JSON", "⚙️ Enrich (FastAPI)"),
    ("⚙️ Enrich (FastAPI)", "Compose record + outputs"),
    ("Compose record + outputs", "Flatten row"),
    ("Flatten row", "📊 Append to registry"),
    ("Compose record + outputs", "Markdown → file"),
    ("Markdown → file", "💾 Write output doc"),
    ("Compose record + outputs", "SEV1?"),
    ("SEV1?", "🚨 Page on-call (SEV1)", 0),
    ("SEV1?", "📧 Send digest", 1),
]

connections = {}
for link in links:
    src, dst = link[0], link[1]
    out_idx = link[2] if len(link) > 2 else 0
    connections.setdefault(src, {}).setdefault("main", [])
    main = connections[src]["main"]
    while len(main) <= out_idx:
        main.append([])
    main[out_idx].append({"node": dst, "type": "main", "index": 0})

stickies = [
    sticky("## HINDSIGHT — postmortem intelligence pipeline\n"
           "Drop a postmortem (.pdf/.docx/.md) into **/data/incoming_docs**.\n"
           "Gemini extracts an SRE schema → FastAPI re-scores severity, routes to the owning "
           "team, computes error-budget burn & a recurrence fingerprint → Sheets + Gmail.",
           X[0] - 20, Y0 - 230, 540, 180, 4),
    sticky("### Multimodal branch\nIf the doc embeds a Grafana/dashboard image, Gemini Vision "
           "reads the chart and the notes are folded into the main extraction. "
           "`onError: continue` so a vision miss never blocks the pipeline.",
           X[4] - 20, Y0 - 360, 300, 150, 5),
    sticky("### Severity is computed, not trusted\nThe FastAPI service re-scores severity from a "
           "rubric (service tier × jurisdiction breadth × impact language). SEV1 → immediate page.",
           X[9] - 20, Y0 - 200, 320, 130, 3),
    sticky("### Retry / rate-limit handling\nGemini nodes: retryOnFail, 5 tries, 3s backoff — "
           "survives 429s. Enrichment: 3 tries.",
           X[7] - 20, Y0 + 200, 280, 120, 6),
]
nodes.extend(stickies)

workflow = {
    "name": "HINDSIGHT — Postmortem Intelligence",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    "settings": {"executionOrder": "v1", "saveManualExecutions": True,
                 "callerPolicy": "workflowsFromSameOwner"},
    "tags": [{"name": "hindsight"}, {"name": "sre"}],
    "meta": {"templateid": "hindsight-postmortem-intelligence"},
}

with open("/home/claude/hindsight/n8n/hindsight_workflow.json", "w") as f:
    json.dump(workflow, f, indent=2)

print("nodes:", len([n for n in nodes if n['type'] != 'n8n-nodes-base.stickyNote']))
print("connections:", sum(len(v['main']) for v in connections.values()))
print("OK")
