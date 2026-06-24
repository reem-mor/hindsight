// Filter registry rows to last 24h and build daily digest HTML for Gmail.

const WINDOW_HOURS = 24;

const SHEET_ID = "1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk";

const SHEET_URL = "https://docs.google.com/spreadsheets/d/" + SHEET_ID + "/edit";

const FORM_URL = "https://reemmor.app.n8n.cloud/form/21593841-f8b8-43a2-88a8-8595ad3e2f39";



function esc(s) {

  return String(s == null ? "" : s)

    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

}



function statCards(agg) {

  const cards = [

    ["Processed", agg.total, "#4DD0A7"],

    ["SEV1", (agg.by_severity && agg.by_severity.SEV1) || 0, "#FF4D5E"],

    ["Confidential", (agg.by_sensitivity && agg.by_sensitivity.confidential) || 0, "#FF9F43"],

    ["Escalated", (agg.by_routing_tag && agg.by_routing_tag.escalate) || 0, "#FF4D5E"],

  ];

  let html = "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\"><tr>";

  for (let i = 0; i < cards.length; i++) {

    html += "<td style=\"width:25%;padding:6px;\">"

      + "<div style=\"border:1px solid #e2e8f0;border-radius:10px;padding:12px;text-align:center;\">"

      + "<div style=\"font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.08em;\">"

      + esc(cards[i][0]) + "</div>"

      + "<div style=\"font-size:28px;font-weight:700;color:" + cards[i][2] + ";margin-top:4px;\">"

      + esc(String(cards[i][1])) + "</div></div></td>";

  }

  return html + "</tr></table>";

}



function listHtml(counter) {

  const keys = Object.keys(counter || {});

  if (!keys.length) return "<li style=\"color:#64748b;\">None in window</li>";

  return keys.sort().map(function (k) {

    return "<li style=\"margin:4px 0;\"><strong>" + esc(k) + "</strong> · " + esc(String(counter[k])) + "</li>";

  }).join("");

}



const items = $input.all();

const rows = [];

for (let i = 0; i < items.length; i++) {

  const j = items[i].json || {};

  if (j.document_id || j.filename) rows.push(j);

}

const now = Date.now();

const cutoff = now - WINDOW_HOURS * 60 * 60 * 1000;



function parseTs(v) {

  if (!v) return null;

  const d = new Date(String(v));

  return isNaN(d.getTime()) ? null : d.getTime();

}



const recent = [];

for (let i = 0; i < rows.length; i++) {

  const ts = parseTs(rows[i].processed_at);

  if (ts !== null && ts >= cutoff) recent.push(rows[i]);

}



function countBy(key) {

  const m = {};

  for (let i = 0; i < recent.length; i++) {

    const k = String(recent[i][key] || "unknown");

    m[k] = (m[k] || 0) + 1;

  }

  return m;

}



const agg = {

  total: recent.length,

  by_classification: countBy("classification"),

  by_sensitivity: countBy("sensitivity"),

  by_routing_tag: countBy("routing_tag"),

  by_severity: countBy("computed_severity"),

  filenames: recent.slice(0, 20).map(function (r) { return String(r.filename || ""); }),

};



const fileList = agg.filenames.length

  ? agg.filenames.map(function (f) { return "<li style=\"margin:4px 0;\">" + esc(f) + "</li>"; }).join("")

  : "<li style=\"color:#64748b;\">None in window</li>";



const html = ""

  + "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"utf-8\">"

  + "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"

  + "<title>HINDSIGHT Daily Digest</title></head>"

  + "<body style=\"margin:0;padding:0;background:#f1f5f9;font-family:Inter,Arial,sans-serif;color:#0f172a;\">"

  + "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" cellspacing=\"0\" style=\"background:#f1f5f9;padding:24px 12px;\">"

  + "<tr><td align=\"center\">"

  + "<table role=\"presentation\" width=\"600\" cellpadding=\"0\" cellspacing=\"0\" style=\"max-width:600px;width:100%;background:#fff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;\">"

  + "<tr><td style=\"background:#0B0F14;color:#E6EDF3;padding:18px 24px;\">"

  + "<p style=\"margin:0;font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:#8696A7;\">HINDSIGHT · Daily digest</p>"

  + "<h1 style=\"margin:6px 0 0;font-size:22px;font-weight:700;\">Last " + WINDOW_HOURS + " hours</h1>"

  + "</td></tr>"

  + "<tr><td style=\"padding:20px 24px;\">" + statCards(agg) + "</td></tr>"

  + "<tr><td style=\"padding:0 24px 20px;\">"

  + "<h2 style=\"margin:0 0 8px;font-size:14px;font-weight:700;\">By classification</h2><ul style=\"margin:0;padding-left:18px;font-size:14px;\">"

  + listHtml(agg.by_classification) + "</ul>"

  + "<h2 style=\"margin:18px 0 8px;font-size:14px;font-weight:700;\">By severity</h2><ul style=\"margin:0;padding-left:18px;font-size:14px;\">"

  + listHtml(agg.by_severity) + "</ul>"

  + "<h2 style=\"margin:18px 0 8px;font-size:14px;font-weight:700;\">By sensitivity</h2><ul style=\"margin:0;padding-left:18px;font-size:14px;\">"

  + listHtml(agg.by_sensitivity) + "</ul>"

  + "<h2 style=\"margin:18px 0 8px;font-size:14px;font-weight:700;\">By routing tag</h2><ul style=\"margin:0;padding-left:18px;font-size:14px;\">"

  + listHtml(agg.by_routing_tag) + "</ul>"

  + "<h2 style=\"margin:18px 0 8px;font-size:14px;font-weight:700;\">Recent files</h2><ul style=\"margin:0;padding-left:18px;font-size:14px;\">"

  + fileList + "</ul>"

  + "</td></tr>"

  + "<tr><td style=\"padding:14px 24px;background:#f8fafc;border-top:1px solid #e2e8f0;font-size:11px;color:#64748b;line-height:1.5;\">"

  + "Automated by HINDSIGHT daily digest workflow<br>"

  + "<a href=\"" + SHEET_URL + "\" style=\"color:#4DD0A7;\">Open registry</a> · "

  + "<a href=\"" + FORM_URL + "\" style=\"color:#4DD0A7;\">Submit document</a>"

  + "</td></tr></table></td></tr></table></body></html>";



const subject = "[HINDSIGHT] Daily digest — " + agg.total + " incident(s) in last " + WINDOW_HOURS + "h";



return [{ json: { digestHtml: html, digestSubject: subject, digestAggregate: agg } }];

