function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function joinList(a) { return (a && a.length) ? a.join(", ") : ""; }
function fileType(name) {
  const m = String(name || "").match(/\.([^.]+)$/);
  return m ? m[1].toLowerCase() : "txt";
}
function actionsCsv(actions) {
  if (!actions || !actions.length) return "";
  return actions.map(function (a) {
    const owner = (a && a.owner && String(a.owner).trim()) ? String(a.owner) : "UNOWNED";
    const prio = (a && a.priority) ? String(a.priority) : "-";
    return prio + ": " + String(a.action || "") + " (" + owner + ")";
  }).join("; ");
}
function trunc(s, n) {
  const t = String(s || "");
  return t.length <= n ? t : t.slice(0, n - 1) + "…";
}

const SEV_COLOR = { SEV1: "#FF4D5E", SEV2: "#FF9F43", SEV3: "#FFD23F", SEV4: "#4DD0A7" };

const enriched = $input.all();
const parsed = $("Parse Gemini JSON").all();
const out = [];

for (let idx = 0; idx < enriched.length; idx++) {
  const e = enriched[idx].json || {};
  const g = (parsed[idx] && parsed[idx].json) ? parsed[idx].json : {};
  const actions = g.action_items || [];
  const classification = String(e.incident_type || g.incident_type || "other");
  const filename = String(e.source_filename || g.filename || "unknown");
  const sentiment = String(g.sentiment || "neutral");
  const routingTag = String(e.routing_tag || "auto-approved");
  const sensitivity = String(e.sensitivity || "internal");
  const department = String(e.department || "SecOps");
  const summary = trunc(g.summary || e.incident_title || "", 500);
  const sev = e.computed_severity || "SEV3";
  const color = SEV_COLOR[sev] || "#FF9F43";
  const actionItems = actionsCsv(actions);
  const cvss = e.cvss_score != null ? e.cvss_score : (g.cvss_score != null ? g.cvss_score : null);
  const cveIds = joinList(e.cve_ids || g.cve_ids || []);

  // Assignment §8.2 email HTML
  const emailHtmlAssignment = ""
    + "<h2>Document Processed</h2>"
    + "<p><b>File:</b> " + esc(filename) + "</p>"
    + "<p><b>Classification:</b> " + esc(classification) + "</p>"
    + "<p><b>Sentiment:</b> " + esc(sentiment) + "</p>"
    + "<p><b>Department:</b> " + esc(department) + "</p>"
    + "<p><b>Sensitivity:</b> " + esc(sensitivity) + "</p>"
    + "<p><b>Routing tag:</b> " + esc(routingTag) + "</p>"
    + "<h3>Summary</h3><p>" + esc(summary) + "</p>"
    + "<h3>Action items</h3><p>" + esc(actionItems || "(none)") + "</p>"
    + "<hr><p><i>Sent automatically by n8n + Gemini 3 Document Analyst (HINDSIGHT)</i></p>";

  const emailHtmlSev1 = ""
    + '<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:auto">'
    + '<div style="background:' + color + ';color:#1a0408;font-weight:800;padding:10px 16px;border-radius:10px 10px 0 0">'
    + "&#128680; HIGH PRIORITY &middot; " + esc(sensitivity.toUpperCase()) + " / " + esc(routingTag)
    + "</div></div>" + emailHtmlAssignment;

  const subjDigest = "[" + classification + "] New document processed: " + filename;
  const subjSev1 = "[CONFIDENTIAL ESCALATE] " + filename + " - " + department;

  const md = ""
    + "# " + sev + " - " + String(e.incident_title || classification) + "\n\n"
    + "| Classification | " + classification + " |\n"
    + "| Department | " + department + " |\n"
    + "| Sensitivity | " + sensitivity + " |\n"
    + "| Routing tag | " + routingTag + " |\n"
    + "| CVSS | " + (cvss != null ? String(cvss) : "n/a") + " |\n"
    + "| CVEs | " + (cveIds || "n/a") + " |\n\n"
    + "## Summary\n" + summary + "\n\n"
    + "## Action items\n" + (actionItems || "(none)") + "\n";

  // Google Sheets row — assignment §7.2 + cyber bonus columns
  out.push({ json: {
    document_id: e.document_id,
    filename: filename,
    file_type: fileType(filename),
    processed_at: e.processed_at,
    classification: classification,
    department: department,
    sentiment: sentiment,
    confidence_score: e.confidence_score,
    summary: summary,
    routing_tag: routingTag,
    sensitivity: sensitivity,
    action_items: actionItems,
    cvss_score: cvss,
    cve_ids: cveIds,
    computed_severity: sev,
    incident_title: e.incident_title,
    postmortem_markdown: md,
    emailSubjectSev1: subjSev1,
    emailHtmlSev1: emailHtmlSev1,
    emailSubjectDigest: subjDigest,
    emailHtmlDigest: emailHtmlAssignment
  } });
}
return out;
