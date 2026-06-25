/**
 * Complete local Docker n8n setup after owner account exists.
 * Reads GEMINI_API_KEY from repo .env — never logs the key.
 */
import { chromium } from "playwright";
import { readFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, "..");
const ENV_PATH = join(ROOT, ".env");
const N8N = process.env.N8N_LOCAL_URL || "http://127.0.0.1:5678";
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

loadDotenv();
const EMAIL = process.env.N8N_LOCAL_EMAIL || "hindsight@local.dev";
const PASSWORD = process.env.N8N_LOCAL_PASSWORD || "";
if (!PASSWORD) {
  console.error("N8N_LOCAL_PASSWORD is not set in .env — set it before running (no hardcoded default).");
  process.exit(1);
}

async function login(page) {
  await page.goto(`${N8N}/signin`, { waitUntil: "networkidle" });
  if (page.url().includes("/home")) return;
  await page.getByRole("textbox", { name: /Email/i }).fill(EMAIL);
  await page.getByRole("textbox", { name: /Password/i }).fill(PASSWORD);
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.waitForURL(/\/home/, { timeout: 30000 });
}

async function ensureGeminiCredential(page, apiKey) {
  await page.goto(`${N8N}/home/credentials`, { waitUntil: "networkidle" });
  const existing = page.getByText("Gemini API", { exact: false });
  if (await existing.count()) {
    console.log("Gemini Header Auth credential already exists");
    return;
  }

  await page.locator('[data-test-id="add-resource-credential"], button:has-text("Add first credential")').first().click();
  await page.getByRole("combobox", { name: /Search for app/i }).fill("Header Auth");
  await page.getByRole("option", { name: "Header Auth" }).click();
  await page.locator('[data-test-id="new-credential-type-button"]').click();

  await page.getByRole("textbox", { name: /Parameter/i }).first().fill("x-goog-api-key");
  await page.getByRole("textbox", { name: /Parameter/i }).nth(1).fill(apiKey);
  await page.getByRole("button", { name: "Save" }).click();
  await page.waitForTimeout(1500);

  // Rename credential for clarity
  const nameField = page.locator('[data-test-id="credential-name"] input, input[type="text"]').first();
  if (await nameField.count()) {
    await nameField.fill("Gemini API");
    await page.getByRole("button", { name: "Save" }).click();
    await page.waitForTimeout(1000);
  }
  console.log("Created Gemini Header Auth credential");
}

async function activateWorkflow(page) {
  await page.goto(`${N8N}/home/workflows`, { waitUntil: "networkidle" });
  await page.getByText("HINDSIGHT", { exact: false }).first().click();
  await page.waitForURL(/\/workflow\//, { timeout: 20000 });

  const toggle = page.locator('[data-test-id="workflow-activate-switch"]').first();
  await toggle.waitFor({ state: "visible", timeout: 15000 });
  const checked = await toggle.getAttribute("class");
  if (!checked?.includes("is-checked")) {
    await toggle.click();
    await page.waitForTimeout(1500);
  }
  console.log("Workflow activated");
}

async function main() {
  loadDotenv();
  const apiKey = process.env.GEMINI_API_KEY?.trim();
  if (!apiKey) {
    console.error("GEMINI_API_KEY missing in .env");
    process.exit(1);
  }

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  try {
    await login(page);
    await activateWorkflow(page);
    await page.screenshot({
      path: join(ROOT, "docs", "screenshot-n8n-local-setup.png"),
      fullPage: true,
    });
    console.log("Saved docs/screenshot-n8n-local-setup.png");
    console.log("\nLocal n8n ready:");
    console.log(`  URL:      ${N8N}`);
    console.log(`  Email:    ${EMAIL}`);
    console.log("  Password: (from N8N_LOCAL_PASSWORD in .env)");
    console.log("\nStill manual: Google Sheets + Gmail OAuth (Sign in with Google in credential UI).");
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
