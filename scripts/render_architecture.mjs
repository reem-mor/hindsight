/**
 * Render docs/architecture.svg -> docs/architecture.png at 2x (crisp on GitHub).
 * The hand-built SVG is the source of truth for the static diagram; the README also
 * embeds an interactive mermaid version (docs/architecture.mmd). Reproduce:
 *   node scripts/render_architecture.mjs
 */
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const SVG = readFileSync(join(ROOT, "docs", "architecture.svg"), "utf8");
const OUT = join(ROOT, "docs", "architecture.png");

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1300, height: 1060 }, deviceScaleFactor: 2 });
await page.setContent(
  `<!doctype html><html><body style="margin:0;background:#0a0e14">${SVG}</body></html>`,
  { waitUntil: "networkidle" },
);
await page.waitForTimeout(300);
await page.locator("svg").screenshot({ path: OUT });
await browser.close();
console.log("wrote", OUT);
