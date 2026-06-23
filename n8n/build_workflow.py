#!/usr/bin/env python3
"""Builds the importable HINDSIGHT n8n workflow JSON.
Written as a generator so the emitted JSON is always structurally valid.
"""
import json, uuid, os

ROOT = os.path.dirname(os.path.abspath(__file__))

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
            '    { "text": "Read this SIEM or vulnerability-scan chart screenshot. Return ONLY JSON: '
            '{image_kind, metric_name, unit, anomaly_observed, approx_peak_value, '
            'approx_baseline_value, time_window, one_line_summary}." },\n'
            '    { "inline_data": { "mime_type": "image/png",'
            ' "data": "{{ $binary.data0 ? $binary.data0.toString(\'base64\') : \'\' }}" } }\n'
            '  ]}],\n'
            '  "generationConfig": { "temperature": 0.2, "responseMimeType": "application/json" }\n'
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
            "const prompt = `You are HINDSIGHT, a cybersecurity incident-log analyst. Read the SIEM export, vuln scan, or phishing report and return ONLY a valid JSON object matching this schema exactly:\\n"
            "{incident_title, summary, severity (SEV1|SEV2|SEV3|SEV4), incident_type (security|data-incident|vulnerability-scan|malware|phishing|intrusion|ddos|other), status, "
            "affected_services[], affected_jurisdictions[], root_cause, trigger, detection_method, "
            "entities:{people[],teams[],systems[],dates[],error_codes[]}, "
            "action_items:[{action,owner,priority}], contributing_factors[], sentiment, blameless_quality, "
            "cvss_score, cve_ids[], confidence_score, "
            "metrics:{detected_at,resolved_at,ttd_minutes,ttr_minutes,customer_impact}}\\n"
            "For vuln scans set cvss_score and cve_ids verbatim. When unsure of severity pick the LOWER one.\\n\\n"
            "VISION NOTES (from embedded SIEM/scan charts):\\n${j.vision_notes || 'none'}\\n\\n"
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
            '  "generationConfig": { "temperature": 0.2, "responseMimeType": "application/json" }\n'
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
            "const FENCE = String.fromCharCode(96, 96, 96);\n"
            "const REQUIRED = ['summary', 'sentiment', 'action_items', 'confidence_score'];\n"
            "function validateGeminiShape(g) {\n"
            "  const missing = [];\n"
            "  for (let i = 0; i < REQUIRED.length; i++) {\n"
            "    if (g[REQUIRED[i]] === undefined) missing.push(REQUIRED[i]);\n"
            "  }\n"
            "  if (!g.incident_type && !g.classification) missing.push('incident_type|classification');\n"
            "  if (!Array.isArray(g.action_items)) missing.push('action_items(array)');\n"
            "  if (missing.length) throw new Error('Gemini JSON missing required fields: ' + missing.join(', '));\n"
            "}\n"
            "const prev = $('Build extraction prompt').first().json;\n"
            "const resp = $input.first().json;\n"
            "let txt = resp.candidates?.[0]?.content?.parts?.[0]?.text;\n"
            "if (!txt) throw new Error('Gemini returned no text');\n"
            "txt = String(txt).trim();\n"
            "if (txt.indexOf(FENCE) !== -1) {\n"
            "  txt = txt.split(FENCE).join('');\n"
            "  if (txt.toLowerCase().indexOf('json') === 0) txt = txt.slice(4);\n"
            "  txt = txt.trim();\n"
            "}\n"
            "let g; try { g = JSON.parse(txt); } catch(e){ throw new Error('Bad JSON from Gemini: '+txt.slice(0,200)); }\n"
            "validateGeminiShape(g);\n"
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
            "function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}\n"
            "function actionsCsv(a){if(!a||!a.length)return'';return a.map(x=>{const o=(x&&x.owner&&String(x.owner).trim())?String(x.owner):'UNOWNED';const p=(x&&x.priority)?String(x.priority):'-';return p+': '+String(x.action||'')+' ('+o+')';}).join('; ');}\n"
            "function fileType(n){const m=String(n||'').match(/\\.([^.]+)$/);return m?m[1].toLowerCase():'txt';}\n"
            "const g=$('Parse Gemini JSON').first().json;\n"
            "const e=$input.first().json;\n"
            "const classification=String(e.incident_type||g.incident_type||'other');\n"
            "const filename=String(e.source_filename||g.filename||g.source_filename||'unknown');\n"
            "const sentiment=String(g.sentiment||'neutral');\n"
            "const routingTag=String(e.routing_tag||'auto-approved');\n"
            "const summary=String(g.summary||'').slice(0,500);\n"
            "const actionItems=actionsCsv(g.action_items||[]);\n"
            "const row={document_id:e.document_id,filename:filename,file_type:fileType(filename),processed_at:e.processed_at,"
            "classification:classification,department:e.department,sentiment:sentiment,confidence_score:e.confidence_score,"
            "summary:summary,routing_tag:routingTag,sensitivity:e.sensitivity,action_items:actionItems,"
            "cvss_score:e.cvss_score,cve_ids:(e.cve_ids||[]).join(', ')};\n"
            "const emailHtml='<h2>Document Processed</h2><p><b>File:</b> '+esc(filename)+'</p>"
            "+'<p><b>Classification:</b> '+esc(classification)+'</p><p><b>Sentiment:</b> '+esc(sentiment)+'</p>"
            "+'<p><b>Department:</b> '+esc(e.department)+'</p><p><b>Sensitivity:</b> '+esc(e.sensitivity)+'</p>"
            "+'<p><b>Routing tag:</b> '+esc(routingTag)+'</p><h3>Summary</h3><p>'+esc(summary)+'</p>"
            "+'<h3>Action items</h3><p>'+esc(actionItems||'(none)')+'</p>';"
            "const subjDigest='['+classification+'] New document processed: '+filename;\n"
            "const subjSev1='[CONFIDENTIAL ESCALATE] '+filename+' - '+e.department;\n"
            "const isSev1=e.computed_severity==='SEV1';\n"
            "return [{json:{row,markdown:'# '+e.computed_severity+' - '+classification,is_sev1:isSev1,e,g,"
            "emailSubjectDigest:subjDigest,emailHtmlDigest:emailHtml,emailSubjectSev1:subjSev1,emailHtmlSev1:emailHtml,"
            "out_path:`/data/output_docs/${e.document_id}.md`}}];"
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
        "sendTo": "=reem.mor3@gmail.com",
        "subject": "={{ $('Compose record + outputs').first().json.emailSubjectSev1 }}",
        "emailType": "html",
        "message": "={{ $('Compose record + outputs').first().json.emailHtmlSev1 }}",
        "options": {"priority": "high"},
    },
)
page["credentials"] = {"gmailOAuth2": {"id": "REPLACE_GMAIL", "name": "Gmail"}}

summary_mail = node(
    "📧 Send digest", "n8n-nodes-base.gmail", 2, X[12] + 260, Y0 + 110,
    {
        "operation": "send",
        "sendTo": "=reem.mor3@gmail.com",
        "subject": "={{ $('Compose record + outputs').first().json.emailSubjectDigest }}",
        "emailType": "html",
        "message": "={{ $('Compose record + outputs').first().json.emailHtmlDigest }}",
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
    sticky("## HINDSIGHT — cyber incident log pipeline\n"
           "Drop a SIEM export, vuln scan, or phishing report (.pdf/.md) into **/data/incoming_docs**.\n"
           "Gemini extracts → FastAPI re-scores severity & routes → Sheets + Gmail.",
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
    "name": "HINDSIGHT — Cyber Incident Intelligence",
    "nodes": nodes,
    "connections": connections,
    "active": False,
    "settings": {"executionOrder": "v1", "saveManualExecutions": True,
                 "callerPolicy": "workflowsFromSameOwner"},
    "tags": [{"name": "hindsight"}, {"name": "sre"}],
    "meta": {"templateid": "hindsight-postmortem-intelligence"},
}

with open(os.path.join(ROOT, "hindsight_workflow.json"), "w") as f:
    json.dump(workflow, f, indent=2)

print("nodes:", len([n for n in nodes if n['type'] != 'n8n-nodes-base.stickyNote']))
print("connections:", sum(len(v['main']) for v in connections.values()))
print("OK")
