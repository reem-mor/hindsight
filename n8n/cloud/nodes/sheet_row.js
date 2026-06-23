// Strip Compose output to assignment §7.2 columns only (Sheets auto-map).
const KEYS = [
  "document_id", "filename", "file_type", "processed_at", "classification",
  "department", "sentiment", "confidence_score", "summary", "routing_tag",
  "sensitivity", "action_items", "cvss_score", "cve_ids",
];
const items = $input.all();
const out = [];
for (let i = 0; i < items.length; i++) {
  const j = items[i].json || {};
  const row = {};
  for (let k = 0; k < KEYS.length; k++) {
    row[KEYS[k]] = j[KEYS[k]];
  }
  out.push({ json: row });
}
return out;
