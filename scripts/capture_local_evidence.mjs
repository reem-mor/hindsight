/**
 * Capture local/Docker evidence screenshots with Playwright.
 * Docker-aware: uses the already-running enrichment API on :8000 and n8n on
 * :5678 (does NOT spawn its own API). Also screenshots the rendered email
 * samples and the live dashboard. Output: docs/*.png
 *
 * Prereq:  node scripts/render_email_samples.mjs   (writes docs/email-samples/)
 *          docker compose up -d                     (n8n :5678, API :8000)
 */
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const DOCS = join(ROOT, 'docs');

function serveDashboard(port = 8765) {
  return new Promise((resolve) => {
    const server = createServer((req, res) => {
      const path = req.url?.split('?')[0] ?? '/';
      const rel = path === '/' ? '/index.html' : path;
      const file = join(ROOT, 'dashboard', rel.replace(/^\//, ''));
      if (!existsSync(file)) { res.writeHead(404); res.end('not found'); return; }
      const ext = file.split('.').pop();
      const type = ext === 'html' ? 'text/html' : ext === 'csv' ? 'text/csv' : 'text/plain';
      res.writeHead(200, { 'Content-Type': type });
      res.end(readFileSync(file));
    });
    server.listen(port, () => resolve({ server, url: `http://127.0.0.1:${port}/` }));
  });
}

async function shot(page, name, url, { waitMs = 1200, full = true } = {}) {
  try {
    await page.goto(url, { waitUntil: 'networkidle', timeout: 15000 });
  } catch {
    await page.goto(url, { waitUntil: 'load', timeout: 15000 });
  }
  await page.waitForTimeout(waitMs);
  const path = join(DOCS, name);
  await page.screenshot({ path, fullPage: full });
  console.log('saved', name);
}

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 980 }, deviceScaleFactor: 2 });
const dash = await serveDashboard();
try {
  // Email samples (rendered from the real node code)
  const emails = join(ROOT, 'docs', 'email-samples');
  await page.setViewportSize({ width: 720, height: 980 });
  await shot(page, 'screenshot-email-incident.png', pathToFileURL(join(emails, 'incident-email.html')).href, { waitMs: 500 });
  await shot(page, 'screenshot-email-alert.png', pathToFileURL(join(emails, 'alert-email.html')).href, { waitMs: 500 });
  await shot(page, 'screenshot-email-digest.png', pathToFileURL(join(emails, 'digest-email.html')).href, { waitMs: 500 });

  await page.setViewportSize({ width: 1440, height: 980 });
  // Live dashboard (BON-3) reading the fixture CSV
  await shot(page, 'screenshot-dashboard.png', `${dash.url}?csv=${encodeURIComponent(`${dash.url}fixtures/incidents.csv`)}`, { waitMs: 2500 });
  // Docker FastAPI OpenAPI
  await shot(page, 'screenshot-fastapi.png', 'http://127.0.0.1:8000/docs', { waitMs: 1500, full: true });
  // Local n8n (Docker)
  await shot(page, 'screenshot-n8n-local.png', 'http://127.0.0.1:5678/', { waitMs: 2500, full: false });
} finally {
  dash.server.close();
  await browser.close();
}
console.log('Local/Docker evidence screenshots complete.');
