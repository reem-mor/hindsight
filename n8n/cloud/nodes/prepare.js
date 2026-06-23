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

function readU16(buf, off) { return buf[off] | (buf[off + 1] << 8); }
function readU32(buf, off) {
  return (buf[off] | (buf[off + 1] << 8) | (buf[off + 2] << 16) | (buf[off + 3] << 24)) >>> 0;
}
function unzipTextEntries(buf) {
  const entries = [];
  let eocd = buf.length;
  for (let i = buf.length - 22; i >= 0; i--) {
    if (readU32(buf, i) === 0x06054b50) { eocd = i; break; }
  }
  let offset = 0;
  while (offset + 30 < eocd) {
    if (readU32(buf, offset) !== 0x04034b50) break;
    const comp = readU16(buf, offset + 8);
    const compSize = readU32(buf, offset + 18);
    const nameLen = readU16(buf, offset + 26);
    const extraLen = readU16(buf, offset + 28);
    const name = buf.slice(offset + 30, offset + 30 + nameLen).toString("utf8");
    const dataStart = offset + 30 + nameLen + extraLen;
    const data = buf.slice(dataStart, dataStart + compSize);
    offset = dataStart + compSize;
    if (name.endsWith("/")) continue;
    const ext = name.indexOf(".") >= 0 ? name.split(".").pop().toLowerCase() : "";
    if (ext !== "md" && ext !== "txt" && ext !== "markdown") continue;
    let raw;
    if (comp === 0) {
      raw = data;
    } else if (comp === 8) {
      throw new Error("DEFLATE zip entries blocked on n8n Cloud — re-pack with ZIP_STORED (see samples/make_batch_zip.py)");
    } else {
      continue;
    }
    entries.push({ filename: name.split("/").pop(), text: raw.toString("utf8") });
    if (entries.length >= 25) break;
  }
  return entries;
}

function newCorrelationId() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    return globalThis.crypto.randomUUID();
  }
  return "hs-" + Date.now() + "-" + Math.floor(Math.random() * 1e6);
}

function buildGeminiBody(documentText, isPdf, b64) {
  let parts;
  if (isPdf) {
    const promptText = PROMPT_HEAD
      + "VISION NOTES: The source PDF is attached. Read any embedded SIEM or scan charts and fold metrics into summary.\n"
      + "DOCUMENT: (see attached PDF)";
    parts = [{ text: promptText }, { inline_data: { mime_type: "application/pdf", data: b64 } }];
  } else {
    const promptText = PROMPT_HEAD
      + "VISION NOTES: (none)\n"
      + "DOCUMENT TEXT:\n" + documentText;
    parts = [{ text: promptText }];
  }
  return {
    contents: [{ role: "user", parts: parts }],
    generationConfig: { temperature: 0.2, responseMimeType: "application/json" }
  };
}

const items = $input.all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const item = items[idx];
  const pre = item.json || {};

  // Batch fan-out item from Unzip Batch node (BON-7)
  if (pre.isBatchItem && pre.documentText) {
    out.push({ json: {
      correlationId: newCorrelationId(),
      sourceFilename: pre.sourceFilename || "batch-item.md",
      mimeType: "text/plain",
      isPdf: false,
      isBatchItem: true,
      batchIndex: pre.batchIndex,
      batchTotal: pre.batchTotal,
      receivedAt: new Date().toISOString(),
      geminiBody: buildGeminiBody(pre.documentText, false, null),
    } });
    continue;
  }

  const bin = item.binary || {};
  const keys = Object.keys(bin);
  if (keys.length === 0) {
    throw new Error("No file was uploaded. Please attach a cyber incident log (.pdf, .md, .txt, or .zip).");
  }
  const key = keys[0];
  const meta = bin[key] || {};
  const fileName = meta.fileName || "incident-log";
  const mimeType = String(meta.mimeType || "").toLowerCase();
  const ext = String(meta.fileExtension || (fileName.split(".").pop() || "")).toLowerCase();
  const isPdf = mimeType.indexOf("pdf") !== -1 || ext === "pdf";
  const isZip = mimeType.indexOf("zip") !== -1 || ext === "zip";

  let buf;
  try {
    buf = await this.helpers.getBinaryDataBuffer(idx, key);
  } catch (e) {
    buf = Buffer.from(meta.data || "", "base64");
  }

  if (isZip) {
    const entries = unzipTextEntries(buf);
    if (!entries.length) throw new Error("ZIP contained no supported .md/.txt files");
    for (let i = 0; i < entries.length; i++) {
      out.push({ json: {
        correlationId: newCorrelationId(),
        sourceFilename: entries[i].filename,
        mimeType: "text/plain",
        isPdf: false,
        isBatchItem: true,
        batchIndex: i,
        batchTotal: entries.length,
        receivedAt: new Date().toISOString(),
        geminiBody: buildGeminiBody(entries[i].text, false, null),
      } });
    }
    continue;
  }

  let geminiBody;
  if (isPdf) {
    geminiBody = buildGeminiBody("", true, buf.toString("base64"));
  } else {
    geminiBody = buildGeminiBody(buf.toString("utf-8"), false, null);
  }

  out.push({ json: {
    correlationId: newCorrelationId(),
    sourceFilename: fileName,
    mimeType: mimeType,
    isPdf: isPdf,
    receivedAt: new Date().toISOString(),
    geminiBody: geminiBody,
  } });
}
return out;
