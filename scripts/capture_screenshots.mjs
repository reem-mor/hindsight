/**
 * Capture local evidence screenshots (dashboard + FastAPI OpenAPI).
 * n8n Cloud / Sheets / Gmail require authenticated sessions — use Playwright MCP in Cursor.
 */
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const DOCS = join(ROOT, "docs");
const DASHBOARD = join(ROOT, "dashboard", "index.html");
const VENV_PY = join(ROOT, ".venv", "Scripts", "python.exe");

function serveDashboard(port = 8765) {
  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      const path = req.url?.split("?")[0] ?? "/";
      if (path === "/fixtures/incidents.csv") {
        const csv = join(ROOT, "dashboard", "fixtures", "incidents.csv");
        if (!existsSync(csv)) {
          res.writeHead(404);
          res.end("fixtures missing");
          return;
        }
        res.writeHead(200, { "Content-Type": "text/csv" });
        res.end(readFileSync(csv));
        return;
      }
      const filePath = path === "/" ? "/index.html" : path;
      const file = join(ROOT, "dashboard", filePath.replace(/^\//, ""));
      if (!existsSync(file)) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      const body = readFileSync(file);
      const ext = file.split(".").pop();
      const type =
        ext === "html"
          ? "text/html"
          : ext === "json"
            ? "application/json"
            : "text/plain";
      res.writeHead(200, { "Content-Type": type });
      res.end(body);
    });
    server.listen(port, () => resolve({ server, url: `http://127.0.0.1:${port}/` }));
  });
}

async function startApi(port = 8000) {
  const proc = spawn(VENV_PY, ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: join(ROOT, "services", "enrichment-api"),
    stdio: "pipe",
  });
  const deadline = Date.now() + 15000;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/health`);
      if (res.ok) return proc;
    } catch {
      /* retry */
    }
    await new Promise((r) => setTimeout(r, 300));
  }
  proc.kill();
  throw new Error("FastAPI did not become healthy within 15s");
}

async function shot(page, path, url, waitMs = 1200) {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(waitMs);
  await page.screenshot({ path, fullPage: true });
  console.log(`saved ${path}`);
}

async function main() {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const dash = await serveDashboard();
  let apiProc = null;
  try {
    apiProc = await startApi();
    await shot(
      page,
      join(DOCS, "screenshot-dashboard.png"),
      `${dash.url}?csv=${encodeURIComponent(`${dash.url}fixtures/incidents.csv`)}`,
      2500,
    );
    await shot(page, join(DOCS, "screenshot-fastapi.png"), "http://127.0.0.1:8000/docs", 1500);
  } finally {
    dash.server.close();
    if (apiProc) apiProc.kill();
    await browser.close();
  }
  console.log("Local screenshots complete (dashboard + FastAPI).");
  console.log("For n8n / Sheets / Gmail / email: use Playwright MCP against your Cloud instance.");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
