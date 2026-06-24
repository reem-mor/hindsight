/**
 * E2E: submit Cloud form with sample incident, screenshot success, poll execution.
 */
import { chromium } from "playwright";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DOCS = join(ROOT, "docs");
const ENV_PATH = join(ROOT, ".env");

function loadDotenv() {
  if (!existsSync(ENV_PATH)) return;
  for (const line of readFileSync(ENV_PATH, "utf8").split(/\r?\n/)) {
    const t = line.trim();
    if (!t || t.startsWith("#") || !t.includes("=")) continue;
    const i = t.indexOf("=");
    const k = t.slice(0, i).trim();
    const v = t.slice(i + 1).trim().replace(/^['"]|['"]$/g, "");
    if (!process.env[k]) process.env[k] = v;
  }
}
const FORM_URL = "https://reemmor.app.n8n.cloud/form/21593841-f8b8-43a2-88a8-8595ad3e2f39";
const SAMPLE = join(ROOT, "samples", "vuln_scan_critical_openssl.md");

async function latestExecution(apiBase, apiKey) {
  const res = await fetch(`${apiBase}/api/v1/executions?workflowId=aYEv22StywIPL3Rq&limit=1`, {
    headers: { "X-N8N-API-KEY": apiKey },
  });
  const data = await res.json();
  return data.data?.[0];
}

async function pollExecution(apiBase, apiKey, execId, timeoutMs = 120000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const res = await fetch(`${apiBase}/api/v1/executions/${execId}`, {
      headers: { "X-N8N-API-KEY": apiKey },
    });
    const data = await res.json();
    const status = data.status;
    process.stdout.write(`poll ${execId}: ${status}\n`);
    if (status && status !== "running" && status !== "waiting") return data;
    await new Promise((r) => setTimeout(r, 5000));
  }
  throw new Error(`Execution ${execId} did not finish in time`);
}

async function main() {
  loadDotenv();
  const apiKey = process.env.N8N_API_KEY;
  const apiBase = (process.env.N8N_API_URL || "https://reemmor.app.n8n.cloud").replace(/\/$/, "");
  if (!apiKey) {
    console.error("N8N_API_KEY required");
    process.exit(1);
  }

  const before = await latestExecution(apiBase, apiKey);
  const beforeId = before?.id;

  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  await page.goto(FORM_URL, { waitUntil: "networkidle" });
  await page.screenshot({ path: join(DOCS, "screenshot-form-cloud.png"), fullPage: true });
  console.log("saved form (pre-submit)");

  const [fileChooser] = await Promise.all([
    page.waitForEvent("filechooser"),
    page.getByRole("button", { name: /Postmortem Document/i }).click(),
  ]);
  await fileChooser.setFiles(SAMPLE);
  await page.getByRole("button", { name: "Submit" }).click();

  await page.waitForSelector("text=Form submitted", { timeout: 60000 }).catch(async () => {
    await page.waitForTimeout(3000);
  });
  await page.screenshot({ path: join(DOCS, "screenshot-form-success.png"), fullPage: true });
  console.log("saved form (post-submit)");

  await browser.close();

  let exec = null;
  for (let i = 0; i < 12; i++) {
    await new Promise((r) => setTimeout(r, 5000));
    exec = await latestExecution(apiBase, apiKey);
    if (exec?.id && String(exec.id) !== String(beforeId)) break;
  }
  if (!exec?.id) throw new Error("No new execution detected after form submit");
  console.log(`new execution: ${exec.id} status=${exec.status}`);

  const final = await pollExecution(apiBase, apiKey, exec.id);
  console.log(`final status: ${final.status}`);
  if (final.status !== "success") process.exit(1);
  console.log("E2E form submit OK — Gmail nodes should have sent notification emails.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
