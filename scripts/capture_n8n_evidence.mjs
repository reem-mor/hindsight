/**
 * Render n8n workflow + execution evidence as PNG screenshots (API-based, no UI login).
 * Produces docs/screenshot-workflow.png and docs/screenshot-execution.png
 */
import { chromium } from "playwright";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DOCS = join(ROOT, "docs");

function loadEnv() {
  const envPath = join(ROOT, ".env");
  const env = { N8N_API_URL: "https://reemmor.app.n8n.cloud" };
  if (!existsSync(envPath)) return env;
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const [k, ...rest] = t.split("=");
    env[k.trim()] = rest.join("=").trim().replace(/^["']|["']$/g, "");
  }
  env.N8N_API_KEY = process.env.N8N_API_KEY || env.N8N_API_KEY;
  env.N8N_API_URL = process.env.N8N_API_URL || env.N8N_API_URL;
  return env;
}

async function n8nGet(env, path) {
  const base = env.N8N_API_URL.replace(/\/$/, "");
  const res = await fetch(`${base}${path}`, {
    headers: { "X-N8N-API-KEY": env.N8N_API_KEY, Accept: "application/json" },
  });
  if (!res.ok) throw new Error(`n8n API ${path} → ${res.status}`);
  return res.json();
}

function workflowHtml(workflow) {
  const nodes = workflow.nodes || [];
  const items = nodes
    .map(
      (n) =>
        `<div class="node"><strong>${n.name}</strong><br/><span>${n.type.replace("n8n-nodes-base.", "")}</span></div>`,
    )
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"/>
<style>
body{font-family:Segoe UI,system-ui,sans-serif;background:#1a1d21;color:#e8eaed;padding:24px}
h1{font-size:20px;margin:0 0 8px}
.meta{color:#9aa0a6;font-size:13px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.node{background:#2d3136;border:1px solid #5f6368;border-radius:8px;padding:12px;font-size:13px}
.node span{color:#8ab4f8;font-size:11px}
.badge{display:inline-block;background:#188038;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px}
</style></head><body>
<h1>${workflow.name}</h1>
<div class="meta">id ${workflow.id} · <span class="badge">${workflow.active ? "active" : "draft"}</span> · ${nodes.length} nodes · n8n Cloud API snapshot</div>
<div class="grid">${items}</div>
</body></html>`;
}

function executionHtml(workflow, execution) {
  const runData = execution.data?.resultData?.runData || {};
  const nodes = (workflow.nodes || []).map((n) => {
    const runs = runData[n.name];
    const ok = runs?.[0]?.executionStatus === "success";
    const color = ok ? "#188038" : runs ? "#d93025" : "#5f6368";
    return `<div class="node" style="border-color:${color}"><strong>${n.name}</strong><br/><span style="color:${color}">${runs ? runs[0].executionStatus : "not run"}</span></div>`;
  }).join("");
  return `<!doctype html><html><head><meta charset="utf-8"/>
<style>
body{font-family:Segoe UI,system-ui,sans-serif;background:#1a1d21;color:#e8eaed;padding:24px}
h1{font-size:20px;margin:0 0 8px}
.meta{color:#9aa0a6;font-size:13px;margin-bottom:20px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.node{background:#2d3136;border:2px solid #5f6368;border-radius:8px;padding:12px;font-size:13px}
.badge{display:inline-block;background:#188038;color:#fff;padding:2px 8px;border-radius:4px;font-size:11px}
</style></head><body>
<h1>Execution ${execution.id} — ${execution.status}</h1>
<div class="meta">workflow ${workflow.id} · mode ${execution.mode} · ${execution.startedAt} · pinned dry-run evidence</div>
<div class="grid">${nodes}</div>
</body></html>`;
}

async function screenshotHtml(html, outPath) {
  const tmp = join(DOCS, "_tmp_evidence.html");
  writeFileSync(tmp, html, "utf8");
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(`file:///${tmp.replace(/\\/g, "/")}`, { waitUntil: "networkidle" });
  await page.screenshot({ path: outPath, fullPage: true });
  await browser.close();
  console.log(`saved ${outPath}`);
}

async function main() {
  const env = loadEnv();
  if (!env.N8N_API_KEY) {
    console.log("SKIP: N8N_API_KEY not set");
    return;
  }
  const wfId = "aYEv22StywIPL3Rq";
  const workflow = await n8nGet(env, `/api/v1/workflows/${wfId}`);
  await screenshotHtml(workflowHtml(workflow), join(DOCS, "screenshot-workflow.png"));

  const execList = await n8nGet(env, `/api/v1/executions?workflowId=${wfId}&limit=1`);
  const latest = execList.data?.[0];
  if (latest) {
    const execution = await n8nGet(env, `/api/v1/executions/${latest.id}?includeData=true`);
    await screenshotHtml(
      executionHtml(workflow, execution),
      join(DOCS, "screenshot-execution.png"),
    );
  }
  console.log("n8n API evidence screenshots complete.");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
