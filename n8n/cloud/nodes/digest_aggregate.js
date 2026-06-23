// Filter registry rows to last 24h and build daily digest HTML for Gmail.
const WINDOW_HOURS = 24;
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

function listHtml(counter) {
  const keys = Object.keys(counter || {});
  if (!keys.length) return "<li>none</li>";
  return keys.sort().map(function (k) {
    return "<li>" + k + ": " + counter[k] + "</li>";
  }).join("");
}

const fileList = agg.filenames.length
  ? agg.filenames.map(function (f) { return "<li>" + f + "</li>"; }).join("")
  : "<li>none</li>";

const html = ""
  + "<h2>HINDSIGHT — Daily digest (last " + WINDOW_HOURS + "h)</h2>"
  + "<p><b>Documents processed:</b> " + agg.total + "</p>"
  + "<h3>By classification</h3><ul>" + listHtml(agg.by_classification) + "</ul>"
  + "<h3>By severity</h3><ul>" + listHtml(agg.by_severity) + "</ul>"
  + "<h3>By sensitivity</h3><ul>" + listHtml(agg.by_sensitivity) + "</ul>"
  + "<h3>By routing tag</h3><ul>" + listHtml(agg.by_routing_tag) + "</ul>"
  + "<h3>Recent files</h3><ul>" + fileList + "</ul>"
  + "<hr><p><i>Sent automatically by HINDSIGHT daily digest workflow</i></p>";

const subject = "[HINDSIGHT] Daily digest — " + agg.total + " incident(s) in last " + WINDOW_HOURS + "h";

return [{ json: { digestHtml: html, digestSubject: subject, digestAggregate: agg } }];
