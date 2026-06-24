function esc(s) {

  return String(s == null ? "" : s)

    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

}

function joinList(a) { return (a && a.length) ? a.join(", ") : ""; }

function fileType(name) {

  const m = String(name || "").match(/\.([^.]+)$/);

  return m ? m[1].toLowerCase() : "txt";

}

function actionsHtml(actions) {

  if (!actions || !actions.length) {

    return "<p style=\"margin:0;color:#64748b;font-size:14px;\">No follow-up actions identified.</p>";

  }

  let html = "<ul style=\"margin:8px 0 0;padding-left:20px;\">";

  for (let i = 0; i < actions.length; i++) {

    const a = actions[i] || {};

    const owner = (a.owner && String(a.owner).trim()) ? esc(String(a.owner)) : "Unassigned";

    const prio = a.priority ? esc(String(a.priority)) : "—";

    html += "<li style=\"margin:6px 0;font-size:14px;line-height:1.5;\">"

      + "<strong>" + prio + "</strong> · " + esc(String(a.action || ""))

      + " <span style=\"color:#64748b;\">(" + owner + ")</span></li>";

  }

  return html + "</ul>";

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



const SHEET_ID = "1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk";

const SHEET_URL = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/edit";

const FORM_URL = "https://reemmor.app.n8n.cloud/form/21593841-f8b8-43a2-88a8-8595ad3e2f39";



function emailShell(opts) {

  const accent = opts.accent || "#4DD0A7";

  const bannerHtml = opts.banner || "";

  const title = esc(opts.title || "Incident processed");

  const subtitle = esc(opts.subtitle || "HINDSIGHT · Cyber incident intelligence");

  const bodyHtml = opts.body || "";

  const footer = esc(opts.footer || "Automated by HINDSIGHT · n8n + Gemini 3 Flash");

  return ""

    + "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"

    + "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"

    + "<title>" + title + "</title></head>"

    + "<body style=\"margin:0;padding:0;background:#f1f5f9;font-family:Inter,Arial,sans-serif;color:#0f172a;\">"

    + "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f1f5f9;padding:24px 12px;\">"

    + "<tr><td align=\"center\">"

    + "<table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;width:100%;background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;\">"

    + bannerHtml

    + "<tr><td style=\"padding:22px 24px 8px;\">"

    + "<p style=\"margin:0;font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#64748b;\">" + subtitle + "</p>"

    + "<h1 style=\"margin:8px 0 0;font-size:22px;font-weight:700;line-height:1.3;\">" + title + "</h1>"

    + "</td></tr>"

    + "<tr><td style=\"padding:8px 24px 20px;\">" + bodyHtml + "</td></tr>"

    + "<tr><td style=\"padding:14px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;line-height:1.5;\">"

    + footer + "<br>"

    + "<a href=\"" + FORM_URL + "\" style=\"color:" + accent + ";\">Submit another document</a> · "

    + "<a href=\"" + SHEET_URL + "\" style=\"color:" + accent + ";\">Open registry</a>"

    + "</td></tr></table></td></tr></table></body></html>";

}



function metaTable(rows) {

  let html = "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"border-collapse:collapse;font-size:14px;\">";

  for (let i = 0; i < rows.length; i++) {

    html += "<tr>"

      + "<td style=\"padding:8px 0;width:38%;color:#64748b;vertical-align:top;\">" + esc(rows[i][0]) + "</td>"

      + "<td style=\"padding:8px 0;font-weight:500;vertical-align:top;\">" + rows[i][1] + "</td></tr>";

    if (i < rows.length - 1) {

      html += "<tr><td colspan=\"2\" style=\"border-bottom:1px solid #e2e8f0;\"></td></tr>";

    }

  }

  return html + "</table>";

}



function buildIncidentEmail(ctx) {

  const sevBadge = "<span style=\"display:inline-block;padding:2px 8px;border-radius:6px;background:"

    + ctx.color + "22;color:" + ctx.color + ";font-weight:700;font-size:12px;\">"

    + esc(ctx.sev) + "</span>";

  const sheetRow = ctx.documentId

    ? "document_id: <code style=\"background:#f1f5f9;padding:2px 6px;border-radius:4px;font-size:12px;\">"

      + esc(ctx.documentId) + "</code>"

    : "see Incidents tab";

  const body = ""

    + metaTable([

      ["Document", esc(ctx.filename)],

      ["Classification", esc(ctx.classification)],

      ["Severity", sevBadge],

      ["Department", esc(ctx.department)],

      ["Sensitivity", esc(ctx.sensitivity)],

      ["Routing", esc(ctx.routingTag)],

      ["Sentiment", esc(ctx.sentiment)],

      ["CVSS", ctx.cvss != null ? esc(String(ctx.cvss)) : "n/a"],

      ["CVE IDs", esc(ctx.cveIds || "n/a")],

      ["Registry row", sheetRow],

    ])

    + "<h2 style=\"margin:22px 0 8px;font-size:15px;font-weight:700;\">Executive summary</h2>"

    + "<p style=\"margin:0;font-size:14px;line-height:1.6;color:#334155;\">" + esc(ctx.summary) + "</p>"

    + "<h2 style=\"margin:22px 0 8px;font-size:15px;font-weight:700;\">Recommended actions</h2>"

    + actionsHtml(ctx.actions)

    + "<p style=\"margin:20px 0 0;font-size:13px;\">"

    + "<a href=\"" + SHEET_URL + "\" style=\"color:#4DD0A7;font-weight:600;\">Open Incidents registry</a>"

    + "</p>";

  return emailShell({

    accent: ctx.color,

    title: ctx.sev + " · " + ctx.classification.replace(/-/g, " "),

    subtitle: "Document processed · " + esc(ctx.filename),

    body: body,

  });

}



function buildAlertEmail(ctx) {

  const banner = ""

    + "<tr><td style=\"background:" + ctx.color + ";color:#1a0408;padding:12px 24px;font-weight:800;font-size:13px;letter-spacing:.04em;\">"

    + "&#128680; HIGH PRIORITY ALERT · " + esc(ctx.sensitivity.toUpperCase()) + " · " + esc(ctx.routingTag.toUpperCase())

    + "</td></tr>";

  const inner = buildIncidentEmail(ctx);

  return inner.replace("<table role=\"presentation\" width=\"600\"", banner + "<table role=\"presentation\" width=\"600\"");

}



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

  const documentId = String(e.document_id || "");



  const ctx = {

    filename: filename,

    classification: classification,

    sev: sev,

    color: color,

    department: department,

    sensitivity: sensitivity,

    routingTag: routingTag,

    sentiment: sentiment,

    cvss: cvss,

    cveIds: cveIds,

    documentId: documentId,

    summary: summary,

    actions: actions,

  };



  const emailHtmlDigest = buildIncidentEmail(ctx);

  const emailHtmlSev1 = buildAlertEmail(ctx);



  const subjDigest = "[HINDSIGHT] " + sev + " · " + classification + " — " + filename;

  const subjSev1 = "[HINDSIGHT ALERT] " + sev + " · " + sensitivity.toUpperCase() + " — " + filename;



  const md = ""

    + "# " + sev + " — " + String(e.incident_title || classification) + "\n\n"

    + "| Field | Value |\n|---|---|\n"

    + "| Classification | " + classification + " |\n"

    + "| Department | " + department + " |\n"

    + "| Sensitivity | " + sensitivity + " |\n"

    + "| Routing tag | " + routingTag + " |\n"

    + "| CVSS | " + (cvss != null ? String(cvss) : "n/a") + " |\n"

    + "| CVEs | " + (cveIds || "n/a") + " |\n\n"

    + "## Summary\n" + summary + "\n\n"

    + "## Action items\n" + (actionItems || "(none)") + "\n";



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

    emailHtmlDigest: emailHtmlDigest,

  } });

}

return out;

