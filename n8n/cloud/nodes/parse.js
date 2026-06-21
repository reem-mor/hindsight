const FENCE = String.fromCharCode(96, 96, 96);
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
  const p = (prep[idx] && prep[idx].json) ? prep[idx].json : {};
  g.correlation_id = p.correlationId || null;
  g.source_filename = p.sourceFilename || null;
  out.push({ json: g });
}
return out;
