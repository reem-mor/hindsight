/** Render docs/architecture.mmd to docs/architecture.png via Playwright + mermaid CDN. */
import { chromium } from "playwright";
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const MMD = readFileSync(join(ROOT, "docs", "architecture.mmd"), "utf8");
const OUT = join(ROOT, "docs", "architecture.png");

const html = `<!DOCTYPE html><html><head>
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<style>body{margin:0;background:#fff;padding:24px}#d{display:inline-block}</style></head>
<body><pre id="d" class="mermaid">${MMD}</pre>
<script>mermaid.initialize({startOnLoad:true,theme:"default"});</script></body></html>`;

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1400, height: 900 } });
await page.setContent(html);
await page.waitForSelector("svg", { timeout: 30000 });
const el = page.locator("#d");
await el.screenshot({ path: OUT, type: "png" });
await browser.close();
console.log("wrote", OUT);
