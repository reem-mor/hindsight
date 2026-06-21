const PROMPT_HEAD = [
"You are HINDSIGHT, an incident-postmortem intelligence analyst for a regulated,",
"multi-jurisdiction online gaming platform (jurisdictions include UKGC, NJ-DGE,",
"MGM). You read engineering postmortems and extract a precise, structured record.",
"",
"Return ONLY a valid JSON object - no markdown, no code fences, no commentary -",
"with EXACTLY these fields:",
"{",
'  "incident_title": "short human title for the incident",',
'  "summary": "2-3 sentence executive summary of what happened and the impact",',
'  "severity": "one of: [SEV1, SEV2, SEV3, SEV4]",',
'  "incident_type": "one of: [outage, degradation, data-incident, security, deployment-failure, capacity, dependency-failure, configuration, other]",',
'  "status": "one of: [resolved, monitoring, ongoing]",',
'  "affected_services": ["service names exactly as written in the document"],',
'  "affected_jurisdictions": ["any of: UKGC, NJ-DGE, MGM, GLOBAL - only if explicitly impacted"],',
'  "root_cause": "the underlying root cause in one or two sentences",',
'  "trigger": "the immediate trigger that started the incident",',
'  "detection_method": "one of: [alert, monitoring, customer-report, manual, synthetic, unknown]",',
'  "entities": {"people": [], "teams": [], "systems": [], "dates": [], "error_codes": []},',
'  "action_items": [{"action": "follow-up action", "owner": "owner name or null", "priority": "one of: [P0, P1, P2] or null"}],',
'  "contributing_factors": ["secondary factors that made it worse or slower to resolve"],',
'  "sentiment": "one of: [positive, neutral, negative]",',
'  "blameless_quality": "one of: [good, acceptable, poor, unknown]",',
'  "confidence_score": 0.0,',
'  "metrics": {"detected_at": "ISO or null", "resolved_at": "ISO or null", "ttd_minutes": 0, "ttr_minutes": 0, "customer_impact": "one sentence or null"}',
"}",
"",
"RULES:",
"- SEV1 = critical service fully down OR data/security/regulatory exposure OR multi-jurisdiction customer impact; SEV2 = major degradation of a critical service or single-jurisdiction impact; SEV3 = partial/minor; SEV4 = negligible/internal. When unsure pick the LOWER severity; a downstream rubric re-scores and flags disagreements.",
"- Compute ttr_minutes from detected_at/resolved_at when present, else infer from the timeline, else 0.",
"- blameless_quality = 'poor' ONLY when the text blames a named person rather than a process/system gap.",
"- Use null (not empty string) where a value is genuinely unknown.",
"- Do not invent services, people, or jurisdictions not in the document.",
""
].join("\n");

const items = $input.all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const item = items[idx];
  const bin = item.binary || {};
  const keys = Object.keys(bin);
  if (keys.length === 0) {
    throw new Error("No file was uploaded. Please attach a postmortem (.pdf, .md, or .txt).");
  }
  const key = keys[0];
  const meta = bin[key] || {};
  const fileName = meta.fileName || "postmortem";
  const mimeType = String(meta.mimeType || "").toLowerCase();
  const ext = String(meta.fileExtension || (fileName.split(".").pop() || "")).toLowerCase();
  const isPdf = mimeType.indexOf("pdf") !== -1 || ext === "pdf";

  let buf;
  try {
    buf = await this.helpers.getBinaryDataBuffer(idx, key);
  } catch (e) {
    buf = Buffer.from(meta.data || "", "base64");
  }

  let parts;
  let documentText = "";
  if (isPdf) {
    const b64 = buf.toString("base64");
    const promptText = PROMPT_HEAD
      + "VISION NOTES: The source PDF is attached below. Read any embedded dashboard/Grafana charts or screenshots directly and fold the numbers (error rates, latency, durations) into metrics and summary.\n"
      + "DOCUMENT: (see attached PDF)";
    parts = [ { text: promptText }, { inline_data: { mime_type: "application/pdf", data: b64 } } ];
  } else {
    documentText = buf.toString("utf-8");
    const promptText = PROMPT_HEAD
      + "VISION NOTES: (none)\n"
      + "DOCUMENT TEXT:\n" + documentText;
    parts = [ { text: promptText } ];
  }

  let correlationId;
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    correlationId = globalThis.crypto.randomUUID();
  } else {
    correlationId = "hs-" + Date.now() + "-" + Math.floor(Math.random() * 1e6);
  }

  const geminiBody = {
    contents: [ { role: "user", parts: parts } ],
    generationConfig: { temperature: 0.1, responseMimeType: "application/json" }
  };

  out.push({ json: {
    correlationId: correlationId,
    sourceFilename: fileName,
    mimeType: mimeType,
    isPdf: isPdf,
    receivedAt: new Date().toISOString(),
    geminiBody: geminiBody
  } });
}
return out;
