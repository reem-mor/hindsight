/**
 * Bonus node tests: digest_aggregate, compare_models, unzip_batch (BON-2/6/7).
 */
import { readFileSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const NODES = join(__dirname, '..', 'nodes');

const mk = (src) => new Function('$input', '$', `return (async () => { ${src} })();`);

let pass = 0;
const failures = [];
const ok = (name, cond, detail = '') => cond ? pass++ : failures.push(name + (detail ? ' :: ' + detail : ''));
const eq = (name, a, b) => ok(name, JSON.stringify(a) === JSON.stringify(b), `got ${JSON.stringify(a)}`);

// ---- digest_aggregate (BON-2) ------------------------------------------------
const digestSrc = readFileSync(join(NODES, 'digest_aggregate.js'), 'utf8');
async function runDigest(rows) {
  const $input = { all: () => rows.map((r) => ({ json: r })) };
  const $ = () => ({ all: () => [] });
  return (await mk(digestSrc)($input, $))[0].json;
}

const now = Date.now();
const recentTs = new Date(now - 3600_000).toISOString();
const oldTs = new Date(now - 48 * 3600_000).toISOString();
const digestOut = await runDigest([
  { processed_at: recentTs, classification: 'intrusion', sensitivity: 'confidential', routing_tag: 'escalate', computed_severity: 'SEV1', filename: 'a.md' },
  { processed_at: recentTs, classification: 'phishing', sensitivity: 'internal', routing_tag: 'auto-approved', computed_severity: 'SEV3', filename: 'b.md' },
  { processed_at: oldTs, classification: 'other', sensitivity: 'internal', routing_tag: 'auto-approved', computed_severity: 'SEV4', filename: 'old.md' },
]);
ok('digest.total_24h', digestOut.digestAggregate.total === 2, String(digestOut.digestAggregate?.total));
ok('digest.html', digestOut.digestHtml.includes('Daily digest'));
ok('digest.subject', digestOut.digestSubject.includes('2 incident'));

// Realistic registry rows have only the 14 sheet columns (NO computed_severity).
// Severity must be derived from the stored cvss_score / routing_tag.
const sheetDigest = await runDigest([
  { processed_at: recentTs, classification: 'vulnerability-scan', sensitivity: 'confidential', routing_tag: 'escalate', cvss_score: 9.8, filename: 'crit.md' },
  { processed_at: recentTs, classification: 'intrusion', sensitivity: 'internal', routing_tag: 'needs-review', cvss_score: 5.0, filename: 'mid.md' },
  { processed_at: recentTs, classification: 'phishing', sensitivity: 'confidential', routing_tag: 'escalate', cvss_score: '', filename: 'esc.md' },
]);
eq('digest.sheet_sev_from_cvss', sheetDigest.digestAggregate.by_severity, { SEV1: 2, SEV3: 1 });

// ---- compare_models (BON-6) --------------------------------------------------
const compareSrc = readFileSync(join(NODES, 'compare_models.js'), 'utf8');
async function runCompare(flash, pro) {
  const $input = { all: () => [{ json: {} }] };
  const $ = (name) => ({
    all: () => {
      if (name === 'Parse Gemini JSON') return [{ json: flash }];
      if (name === 'Parse Gemini Pro') return [{ json: pro }];
      return [];
    },
  });
  return (await mk(compareSrc)($input, $))[0].json;
}
const cmp = await runCompare(
  { incident_type: 'phishing', confidence_score: 0.8, summary: 'a', entities: { systems: ['mail'] } },
  { incident_type: 'phishing', confidence_score: 0.9, summary: 'b', entities: { systems: ['mail'] } },
);
ok('compare.agreement', cmp.classification_agreement === true);
ok('compare.delta', Math.abs(cmp.confidence_delta - 0.1) < 0.001);

// A differing falsy value (0) must produce exactly ONE diff, not a duplicate.
const cmpDup = await runCompare({ confidence_score: 0, summary: 'a' }, { confidence_score: 5, summary: 'a' });
const confDiffs = cmpDup.field_diffs.filter((d) => d.field === 'confidence_score');
ok('compare.no_duplicate_diff', confDiffs.length === 1, 'count=' + confDiffs.length);

// unzip fan-out covered by services/enrichment-api/tests/test_batch.py + prepare.js zip path

const total = pass + failures.length;
console.log(`\nHINDSIGHT bonus node tests: ${pass}/${total} passed`);
if (failures.length) {
  console.log('FAILURES:');
  failures.forEach((f) => console.log('  ✗ ' + f));
  process.exit(1);
}
console.log('All bonus node tests passed ✔');
