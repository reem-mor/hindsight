const PROMPT_HEAD = [
"ROLE: You are HINDSIGHT, a senior cybersecurity incident-log intelligence analyst.",
"You extract facts from SIEM exports, vulnerability scans (Nessus/Qualys/Tenable),",
"phishing investigations, malware findings, and intrusion writeups.",
"",
"TASK: Read the document and return structured incident intelligence for SecOps triage.",
"",
"OUTPUT FORMAT: Return ONLY a valid JSON object — no markdown, no code fences, no commentary.",
"Use EXACTLY these fields:",
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
"- incident_type maps to downstream classification (e.g. vulnerability-scan, phishing, intrusion).",
"- For vuln scans: set cvss_score and cve_ids verbatim when present; never invent CVEs.",
"- SEV1 = active compromise, critical vuln (CVSS >= 9), or major data exposure; when unsure pick LOWER severity.",
"- Use null (not empty string) for unknown scalar values; use [] for empty arrays.",
"- Do not invent systems, hosts, people, or metrics not stated in the document.",
"- Write summary in clear, professional language suitable for an on-call handoff.",
""
].join("\\n");

const MAX_DOCUMENT_CHARS = 900000;

function truncateDocumentText(text) {
  const raw = String(text || "");
  if (raw.length <= MAX_DOCUMENT_CHARS) return raw;
  return raw.slice(0, MAX_DOCUMENT_CHARS)
    + "\n\n[TRUNCATED: document exceeded " + MAX_DOCUMENT_CHARS + " chars; tail omitted before Gemini]";
}

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
    if (entries.length >= 25) {
      if (offset + 30 < eocd && readU32(buf, offset) === 0x04034b50) {
        throw new Error(
          "ZIP batch exceeds 25 supported .md/.txt files — split the archive or use the self-hosted batch API"
        );
      }
      break;
    }
  }
  return entries;
}

const TEXT_EXTS = { md: 1, txt: 1, markdown: 1 };

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
      + "DOCUMENT TEXT:\n" + truncateDocumentText(documentText);
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

  if (ext === "docx") {
    throw new Error(
      "DOCX is not supported on n8n Cloud (grading path). "
      + "Use the self-hosted stack (docker compose + incoming_docs/) which extracts DOCX via python-docx."
    );
  }

  // Extension is authoritative — avoids MIME/extension mismatch (e.g. .txt labeled application/pdf).
  const isPdf = ext === "pdf";
  const isZip = ext === "zip";
  const isText = !!TEXT_EXTS[ext];

  if (!isPdf && !isZip && !isText) {
    throw new Error(
      "Unsupported file type"
      + (ext ? ` ".${ext}"` : "")
      + ". Allowed on Cloud: .pdf, .md, .txt, .markdown, .zip"
    );
  }

  let buf;
  try {
    buf = await this.helpers.getBinaryDataBuffer(idx, key);
  } catch (e) {
    buf = Buffer.from(meta.data || "", "base64");
  }

  if (!buf || buf.length === 0) {
    throw new Error("Uploaded file is empty (0 bytes). Please attach a non-empty incident log.");
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
  } else if (isText) {
    geminiBody = buildGeminiBody(buf.toString("utf-8"), false, null);
  } else {
    throw new Error("Unsupported file type — expected .pdf, .md, .txt, .markdown, or .zip");
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
