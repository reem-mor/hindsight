/**
 * Render the three real Gmail bodies (per-document, SEV1 alert, 24h digest) to
 * static HTML using the EXACT deployed node code, so the email format can be
 * reviewed/screenshotted. Output: docs/email-samples/*.html
 */
import { readFileSync, mkdirSync, writeFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const NODES = join(ROOT, 'n8n', 'cloud', 'nodes');
const OUT = join(ROOT, 'docs', 'email-samples');
mkdirSync(OUT, { recursive: true });

const composeSrc = readFileSync(join(NODES, 'compose.js'), 'utf8');
const digestSrc = readFileSync(join(NODES, 'digest_aggregate.js'), 'utf8');
const mk = (src) => new Function('$input', '$', `return (async () => { ${src} })();`);

// --- realistic SEV1 incident (CVSS 9.8 RCE) -------------------------------- //
const enriched = [{
  document_id: 'hs-vuln-2026-0042',
  source_filename: 'vuln_scan_critical_openssl.md',
  processed_at: '2026-06-25T12:30:00.000Z',
  incident_type: 'vulnerability-scan',
  department: 'SecOps',
  confidence_score: 0.92,
  routing_tag: 'escalate',
  sensitivity: 'confidential',
  computed_severity: 'SEV1',
  incident_title: 'Critical OpenSSL RCE on perimeter hosts',
  cvss_score: 9.8,
  cve_ids: ['CVE-2026-21841'],
}];
const parsed = [{
  summary: 'A Nessus scan flagged CVE-2026-21841 (CVSS 9.8) on 23 internet-facing TLS hosts. Remote code execution is possible without authentication. No exploitation observed yet; emergency patching is in progress.',
  sentiment: 'negative',
  action_items: [
    { action: 'Emergency-patch perimeter gateway images', owner: 'NetSec', priority: 'P0' },
    { action: 'Apply WAF virtual-patch as interim mitigation', owner: 'SecOps', priority: 'P0' },
    { action: 'Confirm no exploitation in SIEM handshake logs', owner: 'SecOps', priority: 'P1' },
  ],
}];

const $ = (name) => (name === 'Parse Gemini JSON' ? { all: () => parsed.map((j) => ({ json: j })) } : { all: () => [] });
const rows = await mk(composeSrc)({ all: () => enriched.map((j) => ({ json: j })) }, $);
const r = rows[0].json;
writeFileSync(join(OUT, 'incident-email.html'), r.emailHtmlDigest);
writeFileSync(join(OUT, 'alert-email.html'), r.emailHtmlSev1);
console.log('per-document subject :', r.emailSubjectDigest);
console.log('SEV1 alert subject   :', r.emailSubjectSev1);

// --- 24h daily digest ------------------------------------------------------ //
const today = '2026-06-25T09:00:00.000Z';
const digestRows = [
  { processed_at: today, classification: 'vulnerability-scan', sensitivity: 'confidential', routing_tag: 'escalate', cvss_score: 9.8, filename: 'vuln_scan_critical_openssl.md' },
  { processed_at: today, classification: 'phishing', sensitivity: 'confidential', routing_tag: 'escalate', cvss_score: '', filename: 'phishing_kyc_credential_harvest.md' },
  { processed_at: today, classification: 'intrusion', sensitivity: 'internal', routing_tag: 'needs-review', cvss_score: 7.2, filename: 'siem_bruteforce_intrusion.md' },
  { processed_at: today, classification: 'degradation', sensitivity: 'public', routing_tag: 'auto-approved', cvss_score: 4.5, filename: 'edge_cdn_sev2_eu_errors.pdf' },
];
const dout = await mk(digestSrc)({ all: () => digestRows.map((j) => ({ json: j })) }, () => ({ all: () => [] }));
writeFileSync(join(OUT, 'digest-email.html'), dout[0].json.digestHtml);
console.log('digest subject       :', dout[0].json.digestSubject);
console.log('digest by_severity   :', JSON.stringify(dout[0].json.digestAggregate.by_severity));
console.log('\nWrote 3 email samples to docs/email-samples/');
