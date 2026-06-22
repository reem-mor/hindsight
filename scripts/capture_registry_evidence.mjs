/**
 * Render registry + SEV1 email evidence from bundled sample data (matches Compose Outputs schema).
 */
import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DOCS = join(ROOT, "docs");
const SAMPLE = join(ROOT, "dashboard", "data", "incidents.sample.json");

const SHEET_COLS = [
  "document_id",
  "incident_title",
  "incident_type",
  "reported_severity",
  "computed_severity",
  "department",
  "sensitivity",
  "cvss_score",
  "routing_tag",
  "recurrence_fingerprint",
];

function sheetHtml(rows) {
  const head = SHEET_COLS.map((c) => `<th>${c}</th>`).join("");
  const body = rows
    .slice(0, 8)
    .map((r) => `<tr>${SHEET_COLS.map((c) => `<td>${r[c] ?? ""}</td>`).join("")}</tr>`)
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"/>
<style>
body{font-family:Segoe UI,system-ui,sans-serif;background:#fff;color:#202124;padding:16px}
h1{font-size:18px}table{border-collapse:collapse;font-size:12px;width:100%}
th,td{border:1px solid #dadce0;padding:6px 8px;text-align:left}
th{background:#f8f9fa;font-weight:600}
.note{color:#5f6368;font-size:12px;margin-bottom:12px}
</style></head><body>
<h1>HINDSIGHT Incident Registry — Incidents tab</h1>
<p class="note">Sample registry rows (schema matches Google Sheets append from Compose Outputs). Live sheet uses the same columns.</p>
<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>
</body></html>`;
}

function sev1EmailHtml(record) {
  const color = "#FF4D5E";
  return `<!doctype html><html><head><meta charset="utf-8"/></head><body style="background:#f5f5f5;padding:24px">
<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:auto">
<div style="background:${color};color:#1a0408;font-weight:800;padding:10px 16px;border-radius:10px 10px 0 0">&#128680; SEV1 PAGE · ACTION REQUIRED</div>
<div style="background:#fff;border:1px solid #e0e0e0;border-radius:0 0 10px 10px;padding:16px">
<p style="margin:0 0 8px"><strong>Subject:</strong> [SEV1 PAGE] ${record.incident_title} - ${record.department}</p>
<p><strong>Computed:</strong> ${record.computed_severity} (reported ${record.reported_severity}) · CVSS ${record.cvss_score} · ${record.routing_tag}</p>
<p>${record.summary}</p>
<p style="color:#5f6368;font-size:12px">CVE: ${(record.cve_ids || []).join(", ")} · Fingerprint ${record.recurrence_fingerprint}</p>
</div></div></body></html>`;
}

async function shot(html, out) {
  const tmp = join(DOCS, "_tmp_registry.html");
  writeFileSync(tmp, html, "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`file:///${tmp.replace(/\\/g, "/")}`, { waitUntil: "networkidle" });
  await page.screenshot({ path: out, fullPage: true });
  await browser.close();
  console.log(`saved ${out}`);
}

async function main() {
  const rows = JSON.parse(readFileSync(SAMPLE, "utf8"));
  const cyber = rows.find((r) => r.cvss_score === 9.8) || rows[0];
  await shot(sheetHtml(rows), join(DOCS, "screenshot-sheet.png"));
  await shot(sev1EmailHtml(cyber), join(DOCS, "screenshot-email.png"));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
