/**
 * compose.js — assignment §7.2 row shape + §8.2 email HTML (incl. Sheet link).
 */
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const composeSrc = readFileSync(join(__dirname, '..', 'nodes', 'compose.js'), 'utf8');
const mkCompose = () => new Function('$input', '$', `return (async () => { ${composeSrc} })();`);

async function runCompose(enriched, parsed) {
  const $input = { all: () => enriched.map((j) => ({ json: j })) };
  const $ = (name) =>
    name === 'Parse Gemini JSON' ? { all: () => parsed.map((j) => ({ json: j })) } : { all: () => [] };
  return mkCompose()($input, $);
}

let pass = 0;
const failures = [];
const ok = (name, cond, detail = '') => (cond ? pass++ : failures.push(name + (detail ? ' :: ' + detail : '')));

const enriched = [{
  document_id: 'doc-test-001',
  source_filename: 'vuln.md',
  processed_at: '2026-06-24T12:00:00.000Z',
  incident_type: 'vulnerability-scan',
  department: 'SecOps',
  confidence_score: 0.91,
  routing_tag: 'escalate',
  sensitivity: 'confidential',
  computed_severity: 'SEV1',
  incident_title: 'Critical OpenSSL',
  cvss_score: 9.8,
  cve_ids: ['CVE-2026-21841'],
}];
const parsed = [{
  summary: 'Remote code execution on edge TLS endpoints.',
  sentiment: 'negative',
  action_items: [{ action: 'patch gateways', owner: 'NetSec', priority: 'P0' }],
}];

const rows = await runCompose(enriched, parsed);
ok('compose.one_row', rows.length === 1);
const r = rows[0].json;

ok('compose.sheet_columns', r.filename === 'vuln.md' && r.classification === 'vulnerability-scan');
ok('compose.routing_tag', r.routing_tag === 'escalate');
ok('compose.email_subject', r.emailSubjectDigest.includes('vuln.md'));
ok('compose.sheet_link', r.emailHtmlDigest.includes('docs.google.com/spreadsheets'));
ok('compose.document_id_in_email', r.emailHtmlDigest.includes('doc-test-001'));

const xss = await runCompose(
  [{ ...enriched[0], source_filename: '<img onerror=alert(1)>.md' }],
  parsed,
);
ok('compose.xss_filename', xss[0].json.emailHtmlDigest.includes('&lt;img'));

const total = pass + failures.length;
console.log(`\nHINDSIGHT compose node tests: ${pass}/${total} passed`);
if (failures.length) {
  console.log('FAILURES:');
  failures.forEach((f) => console.log('  ✗ ' + f));
  process.exit(1);
}
console.log('All compose node tests passed ✔');
