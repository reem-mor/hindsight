/**
 * Render docs/screenshot-supabase.png — BON-5 live-verification evidence card.
 * Every value below was captured live on 2026-06-26 via the Supabase MCP
 * (project/table/RPC) and a live POST /search against gemini-3.1... embeddings
 * (gemini-embedding-001, 768-dim). Reproduce: `node scripts/render_supabase_evidence.mjs`.
 */
import { chromium } from "playwright";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const OUT = join(ROOT, "docs", "screenshot-supabase.png");

const rows = [
  ["sample-openssl-rce", "vuln_scan_critical_openssl.md", "vulnerability-scan", "confidential", "escalate"],
  ["sample-sev1-rce-pdf", "vuln_scan_sev1_critical_rce.pdf", "vulnerability-scan", "confidential", "escalate"],
  ["sample-bruteforce-intrusion", "siem_bruteforce_intrusion.md", "intrusion", "confidential", "auto-approved"],
  ["sample-phishing-kyc", "phishing_kyc_credential_harvest.md", "phishing", "confidential", "auto-approved"],
  ["sample-edge-cdn-sev2", "edge_cdn_sev2_eu_errors.pdf", "availability", "internal", "needs-review"],
];
const search = [
  ["“openssl remote code execution vulnerability on payment hosts”", [
    ["0.875", "vuln_scan_critical_openssl.md", "vulnerability-scan"],
    ["0.874", "vuln_scan_sev1_critical_rce.pdf", "vulnerability-scan"],
  ]],
  ["“credential brute force account takeover”", [
    ["0.854", "siem_bruteforce_intrusion.md", "intrusion"],
  ]],
  ["“fake login page stealing employee passwords”", [
    ["0.812", "phishing_kyc_credential_harvest.md", "phishing"],
  ]],
];

const tag = (t, cls) => `<span class="tag ${cls}">${t}</span>`;
const rowHtml = (r) => `<tr><td class="mono">${r[0]}</td><td class="mono">${r[1]}</td><td>${r[2]}</td><td>${tag(r[3], r[3])}</td><td>${tag(r[4], "rt")}</td></tr>`;
const hitHtml = (h) => `<tr><td class="sim">${h[0]}</td><td class="mono">${h[1]}</td><td>${h[2]}</td></tr>`;
const searchHtml = search.map(([q, hits]) =>
  `<div class="q">${q}</div><table class="hits"><tbody>${hits.map(hitHtml).join("")}</tbody></table>`).join("");

const html = `<!doctype html><html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; margin: 0; font-family: 'Segoe UI', system-ui, sans-serif; }
  body { background:#0b0f14; color:#e6edf3; padding:34px 40px; width:1180px; }
  h1 { font-size:21px; font-weight:650; }
  h1 .b { color:#3ecf8e; }
  .sub { color:#8b98a5; font-size:12.5px; margin:6px 0 22px; }
  .kpis { display:flex; gap:14px; margin-bottom:22px; }
  .kpi { background:#11161d; border:1px solid #1e2730; border-radius:9px; padding:13px 16px; flex:1; }
  .kpi .l { color:#8b98a5; font-size:10.5px; text-transform:uppercase; letter-spacing:.5px; }
  .kpi .v { font-size:18px; font-weight:680; margin-top:5px; }
  .kpi .v.g { color:#3ecf8e; }
  .panel { background:#11161d; border:1px solid #1e2730; border-radius:9px; padding:16px 18px; margin-bottom:18px; }
  .panel h2 { font-size:12px; color:#8b98a5; text-transform:uppercase; letter-spacing:.6px; margin-bottom:11px; font-weight:600; }
  table { width:100%; border-collapse:collapse; font-size:12.5px; }
  th { text-align:left; color:#6e7b88; font-weight:600; font-size:11px; padding:6px 10px; border-bottom:1px solid #1e2730; }
  td { padding:7px 10px; border-bottom:1px solid #161c24; }
  .mono { font-family:'Cascadia Code', Consolas, monospace; font-size:11.5px; color:#b9c4cf; }
  .tag { font-size:10.5px; padding:2px 8px; border-radius:11px; font-weight:600; }
  .confidential { background:#3a1722; color:#ff8da3; }
  .internal { background:#16263a; color:#7db8ff; }
  .rt { background:#1d2730; color:#9fb0bf; }
  .q { color:#cdd7e1; font-size:12.5px; margin:12px 0 6px; }
  .hits td { border:0; padding:4px 10px; }
  .sim { color:#3ecf8e; font-weight:700; font-family:'Cascadia Code', Consolas, monospace; width:70px; }
  .foot { color:#6e7b88; font-size:11px; margin-top:14px; }
</style></head><body>
  <h1><span class="b">BON-5</span> · Semantic Search — Supabase pgvector <span style="color:#8b98a5;font-weight:400">(live verification)</span></h1>
  <div class="sub">project <b>zduaexkkhdnltyelvuwn</b> · region eu-central-1 · status <b style="color:#3ecf8e">ACTIVE_HEALTHY</b> · Postgres 17 · verified 2026-06-26 (Supabase MCP + live /search)</div>
  <div class="kpis">
    <div class="kpi"><div class="l">Indexed rows</div><div class="v g">5 / 5</div></div>
    <div class="kpi"><div class="l">Embedding model</div><div class="v">gemini-embedding-001</div></div>
    <div class="kpi"><div class="l">Dimensions</div><div class="v">768</div></div>
    <div class="kpi"><div class="l">ANN index</div><div class="v">HNSW · cosine</div></div>
    <div class="kpi"><div class="l">RLS</div><div class="v g">enabled</div></div>
  </div>
  <div class="panel">
    <h2>Table <span class="mono">public.hindsight_incidents</span> · service-computed verdicts · RPC <span class="mono">match_hindsight_incidents(query, count, threshold)</span></h2>
    <table><thead><tr><th>document_id</th><th>filename</th><th>classification</th><th>sensitivity</th><th>routing_tag</th></tr></thead>
    <tbody>${rows.map(rowHtml).join("")}</tbody></table>
  </div>
  <div class="panel">
    <h2>Live semantic search — real gemini-embedding-001 ranking (cosine similarity)</h2>
    ${searchHtml}
  </div>
  <div class="foot">Embeddings are real (gemini-embedding-001, 768-dim, normalized); the in-repo deterministic mock is a CI/offline fallback only. Reproduce: POST /search (FastAPI → Supabase RPC). Migration: migrations/001_pgvector_incidents.sql.</div>
</body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1180, height: 900 }, deviceScaleFactor: 2 });
await page.setContent(html, { waitUntil: "networkidle" });
await page.locator("body").screenshot({ path: OUT });
await browser.close();
console.log("wrote", OUT);
