// Field-by-field diff of Flash vs Pro structured extractions (BON-6).
const flashItems = $("Parse Gemini JSON").all();
const proItems = $("Parse Gemini Pro").all();
const out = [];

for (let idx = 0; idx < flashItems.length; idx++) {
  const flash = flashItems[idx].json || {};
  const pro = (proItems[idx] && proItems[idx].json) ? proItems[idx].json : {};

  function diffField(a, b, path, diffs) {
    // typeof [] === typeof {} === "object", so also compare array-ness, else a
    // dict-vs-list disagreement yields spurious per-key diffs instead of 1 mismatch.
    if (typeof a !== typeof b || Array.isArray(a) !== Array.isArray(b)) {
      diffs.push({ field: path || "root", flash: a, pro: b, kind: "type_mismatch" });
      return;
    }
    if (a && typeof a === "object" && !Array.isArray(a)) {
      // Walk the UNION of keys exactly once (mirrors Python compare.py); using
      // `if (!a[k])` would re-diff falsy-but-present values and double-count.
      const union = {};
      Object.keys(a).forEach(function (k) { union[k] = 1; });
      if (b && typeof b === "object") Object.keys(b).forEach(function (k) { union[k] = 1; });
      Object.keys(union).sort().forEach(function (k) {
        diffField(a[k], b[k], path ? path + "." + k : k, diffs);
      });
    } else if (Array.isArray(a)) {
      if (JSON.stringify(a) !== JSON.stringify(b)) {
        diffs.push({ field: path, flash: a, pro: b, kind: "list_diff" });
      }
    } else if (a !== b) {
      diffs.push({ field: path, flash: a, pro: b, kind: "value_diff" });
    }
  }

  const fieldDiffs = [];
  diffField(flash, pro, "", fieldDiffs);

  const flashClass = String(flash.incident_type || flash.classification || "");
  const proClass = String(pro.incident_type || pro.classification || "");
  const flashConf = Number(flash.confidence_score || 0);
  const proConf = Number(pro.confidence_score || 0);

  // Jaccard overlap of entity values (parity with compare.py).
  function entitySet(e) {
    const s = new Set();
    if (e && typeof e === "object") {
      Object.keys(e).forEach(function (k) {
        if (Array.isArray(e[k])) e[k].forEach(function (v) { s.add(String(v)); });
      });
    }
    return s;
  }
  const fSet = entitySet(flash.entities);
  const pSet = entitySet(pro.entities);
  const union = new Set([...fSet, ...pSet]);
  let inter = 0;
  fSet.forEach(function (v) { if (pSet.has(v)) inter++; });
  const entityOverlap = union.size ? Math.round((inter / union.size) * 10000) / 10000 : 1.0;

  const report = {
    classification_agreement: flashClass === proClass,
    confidence_delta: Math.round((proConf - flashConf) * 10000) / 10000,
    entity_overlap_ratio: entityOverlap,
    field_diff_count: fieldDiffs.length,
    field_diffs: fieldDiffs.slice(0, 50),
    flash_summary: String(flash.summary || "").slice(0, 300),
    pro_summary: String(pro.summary || "").slice(0, 300),
    compare_markdown: "# Model compare (Flash vs Pro)\n\n"
      + "| Metric | Value |\n|---|---|\n"
      + "| Classification agreement | " + (flashClass === proClass ? "yes" : "no") + " |\n"
      + "| Confidence delta (Pro - Flash) | " + (proConf - flashConf).toFixed(3) + " |\n"
      + "| Field diffs | " + fieldDiffs.length + " |\n",
  };

  out.push({ json: report });
}
return out;
