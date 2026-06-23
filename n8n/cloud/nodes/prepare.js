const PROMPT_HEAD = [
"You are HINDSIGHT, a cybersecurity incident-log intelligence analyst. You read",
"SIEM exports, vulnerability-scan reports, phishing investigations, malware findings,",
"and intrusion writeups.",
"",
"Return ONLY a valid JSON object - no markdown, no code fences - with EXACTLY these fields:",
"{",
'  "incident_title": "short title for the finding or incident",',
'  "summary": "2-3 sentence summary of what happened and the impact",',
'  "severity": "one of: [SEV1, SEV2, SEV3, SEV4]",',
'  "incident_type": "one of: [security, data-incident, vulnerability-scan, malware, phishing, intrusion, ddos, other]",',
'  "status": "one of: [resolved, monitoring, ongoing]",',
'  "affected_services": ["systems or services named in the document"],',
'  "affected_jurisdictions": ["GLOBAL only if explicitly scoped"],',
'  "root_cause": "underlying root cause in one or two sentences",',
'  "trigger": "what triggered the alert or finding",',
'  "detection_method": "one of: [alert, monitoring, customer-report, manual, synthetic, unknown]",',
'  "entities": {"people": [], "teams": [], "systems": [], "dates": [], "error_codes": []},',
'  "action_items": [{"action": "follow-up action", "owner": "owner or null", "priority": "one of: [P0, P1, P2] or null"}],',
'  "contributing_factors": [],',
'  "sentiment": "one of: [positive, neutral, negative]",',
'  "blameless_quality": "one of: [good, acceptable, poor, unknown]",',
'  "cvss_score": null,',
'  "cve_ids": [],',
'  "confidence_score": 0.0,',
'  "metrics": {"detected_at": "ISO or null", "resolved_at": "ISO or null", "ttd_minutes": 0, "ttr_minutes": 0, "customer_impact": "one sentence or null"}',
"}",
"",
"RULES:",
"- For vuln scans set cvss_score and cve_ids verbatim when present.",
"- SEV1 = active compromise, critical vuln (CVSS >= 9), or major data exposure; when unsure pick LOWER severity.",
"- Use null (not empty string) for unknown values.",
"- Do not invent systems or people not in the document.",
""
].join("\\n");

const items = $input.all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const item = items[idx];
  const bin = item.binary || {};
  const keys = Object.keys(bin);
  if (keys.length === 0) {
    throw new Error("No file was uploaded. Please attach a cyber incident log (.pdf, .md, or .txt).");
  }
  const key = keys[0];
  const meta = bin[key] || {};
  const fileName = meta.fileName || "incident-log";
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
  if (isPdf) {
    const b64 = buf.toString("base64");
    const promptText = PROMPT_HEAD
      + "VISION NOTES: The source PDF is attached. Read any embedded SIEM or scan charts and fold metrics into summary.\n"
      + "DOCUMENT: (see attached PDF)";
    parts = [{ text: promptText }, { inline_data: { mime_type: "application/pdf", data: b64 } }];
  } else {
    const documentText = buf.toString("utf-8");
    const promptText = PROMPT_HEAD
      + "VISION NOTES: (none)\n"
      + "DOCUMENT TEXT:\n" + documentText;
    parts = [{ text: promptText }];
  }

  let correlationId;
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    correlationId = globalThis.crypto.randomUUID();
  } else {
    correlationId = "hs-" + Date.now() + "-" + Math.floor(Math.random() * 1e6);
  }

  const geminiBody = {
    contents: [{ role: "user", parts: parts }],
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
