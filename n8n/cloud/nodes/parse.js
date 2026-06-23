const FENCE = String.fromCharCode(96, 96, 96);
const REQUIRED = ["summary", "sentiment", "action_items", "confidence_score"];

function validateGeminiShape(g) {
  const missing = [];
  for (let i = 0; i < REQUIRED.length; i++) {
    if (g[REQUIRED[i]] === undefined) missing.push(REQUIRED[i]);
  }
  if (!g.incident_type && !g.classification) missing.push("incident_type|classification");
  if (!Array.isArray(g.action_items)) missing.push("action_items(array)");
  if (missing.length) {
    throw new Error("Gemini JSON missing required fields: " + missing.join(", "));
  }
  if (typeof g.confidence_score === "number" && (g.confidence_score < 0 || g.confidence_score > 1)) {
    throw new Error("confidence_score must be between 0 and 1");
  }
}

const items = $input.all();
const prep = $("Prepare Document").all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const resp = items[idx].json || {};
  let raw = "";
  try {
    raw = resp.candidates[0].content.parts[0].text || "";
  } catch (e) {
    raw = "";
  }
  raw = String(raw).trim();
  if (raw.indexOf(FENCE) !== -1) {
    raw = raw.split(FENCE).join("");
    if (raw.toLowerCase().indexOf("json") === 0) { raw = raw.slice(4); }
    raw = raw.trim();
  }
  let g;
  try {
    g = JSON.parse(raw);
  } catch (e) {
    throw new Error("Gemini did not return valid JSON. First 200 chars: " + raw.slice(0, 200));
  }
  validateGeminiShape(g);
  const p = (prep[idx] && prep[idx].json) ? prep[idx].json : {};
  g.correlation_id = p.correlationId || null;
  g.source_filename = p.sourceFilename || null;
  out.push({ json: g });
}
return out;
