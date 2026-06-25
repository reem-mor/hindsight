/**
 * Render the per-document output artifacts (§4 Step 6 / §3.1) for ONE case per
 * cyber scenario, using the EXACT deployed enrich.js + compose.js. Shows the
 * JSON record + Markdown summary a grader would find in output_docs/.
 * Output: docs/sample-outputs/{case}.json + {case}.md
 */
import { readFileSync, mkdirSync, writeFileSync } from 'fs';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const require = createRequire(import.meta.url);
const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const NODES = join(ROOT, 'n8n', 'cloud', 'nodes');
const OUT = join(ROOT, 'docs', 'sample-outputs');
mkdirSync(OUT, { recursive: true });

const enrichSrc = readFileSync(join(NODES, 'enrich.js'), 'utf8');
const composeSrc = readFileSync(join(NODES, 'compose.js'), 'utf8');
const mkEnrich = () => new Function('require', '$input', '$', `return (async () => { ${enrichSrc} })();`);
const mkCompose = () => new Function('$input', '$', `return (async () => { ${composeSrc} })();`);

async function run(parsed) {
  const enriched = (await mkEnrich()(require, { all: () => [{ json: parsed }] }, () => ({ all: () => [] })))[0].json;
  const $ = (n) => (n === 'Parse Gemini JSON' ? { all: () => [{ json: parsed }] } : { all: () => [] });
  const composed = (await mkCompose()({ all: () => [{ json: enriched }] }, $))[0].json;
  return { enriched, composed };
}

// One representative case per cyber scenario type (what Gemini would extract).
const CASES = {
  'vulnerability-scan': {
    incident_title: 'Critical OpenSSL RCE on perimeter hosts', source_filename: 'vuln_scan_critical_openssl.md',
    summary: 'Nessus flagged CVE-2026-21841 (CVSS 9.8) on 23 internet-facing TLS hosts; unauthenticated RCE possible.',
    severity: 'SEV3', incident_type: 'vulnerability-scan', affected_services: ['nessus', 'network'],
    cvss_score: 9.8, cve_ids: ['CVE-2026-21841'], sentiment: 'negative', confidence_score: 0.92,
    action_items: [{ action: 'Emergency-patch perimeter gateways', owner: 'NetSec', priority: 'P0' }],
  },
  phishing: {
    incident_title: 'KYC credential-harvest phishing campaign', source_filename: 'phishing_kyc_credential_harvest.md',
    summary: 'Look-alike domain harvested staff credentials via a fake KYC portal; 3 sessions compromised.',
    severity: 'SEV2', incident_type: 'phishing', affected_services: ['email-gateway', 'auth'],
    sentiment: 'negative', confidence_score: 0.88,
    action_items: [{ action: 'Revoke affected sessions + rotate creds', owner: 'IAM', priority: 'P0' }],
  },
  intrusion: {
    incident_title: 'Brute-force SSH intrusion against bastion', source_filename: 'siem_bruteforce_intrusion.md',
    summary: 'SIEM detected 412 failed SSH logins then a successful auth from a new ASN on the bastion host.',
    severity: 'SEV2', incident_type: 'intrusion', affected_services: ['siem', 'auth'],
    cvss_score: 7.2, sentiment: 'negative', confidence_score: 0.9,
    action_items: [{ action: 'Block source ASN + enforce MFA', owner: 'SecOps', priority: 'P0' }],
  },
};

const index = [];
for (const [key, parsed] of Object.entries(CASES)) {
  const { enriched, composed } = await run(parsed);
  const record = {
    document_id: composed.document_id, filename: composed.filename, file_type: composed.file_type,
    classification: composed.classification, department: composed.department, sensitivity: composed.sensitivity,
    computed_severity: composed.computed_severity, routing_tag: composed.routing_tag,
    cvss_score: composed.cvss_score, cve_ids: composed.cve_ids, confidence_score: composed.confidence_score,
    severity_rationale: enriched.severity_rationale, routing_tags: enriched.routing_tags,
    action_items: composed.action_items,
  };
  writeFileSync(join(OUT, `${key}.json`), JSON.stringify(record, null, 2));
  writeFileSync(join(OUT, `${key}.md`), composed.postmortem_markdown);
  index.push(`${key.padEnd(20)} -> ${composed.computed_severity}  ${composed.sensitivity}  ${composed.routing_tag}`);
}
console.log('Wrote per-case output docs to docs/sample-outputs/:\n' + index.join('\n'));
