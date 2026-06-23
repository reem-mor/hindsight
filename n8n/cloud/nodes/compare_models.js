// Field-by-field diff of Flash vs Pro structured extractions (BON-6).
const flashItems = $("Parse Gemini JSON").all();
const proItems = $("Parse Gemini Pro").all();
const out = [];

for (let idx = 0; idx < flashItems.length; idx++) {
  const flash = flashItems[idx].json || {};
  const pro = (proItems[idx] && proItems[idx].json) ? proItems[idx].json : {};

  function diffField(a, b, path, diffs) {
    if (typeof a !== typeof b) {
      diffs.push({ field: path || "root", flash: a, pro: b, kind: "type_mismatch" });
      return;
    }
    if (a && typeof a === "object" && !Array.isArray(a)) {
      const keys = Object.keys(a);
      for (let i = 0; i < keys.length; i++) {
        const k = keys[i];
        diffField(a[k], b[k], path ? path + "." + k : k, diffs);
      }
      if (b && typeof b === "object") {
        Object.keys(b).forEach(function (k) {
          if (!a[k]) diffField(a[k], b[k], path ? path + "." + k : k, diffs);
        });
      }
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

  const report = {
    classification_agreement: flashClass === proClass,
    confidence_delta: proConf - flashConf,
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
