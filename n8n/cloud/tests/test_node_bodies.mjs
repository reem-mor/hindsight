/**
 * HINDSIGHT — Cloud Code-node test harness
 * Loads the EXACT JavaScript deployed to the n8n Cloud Code nodes
 * (../nodes/*.js) and exercises it against edge cases + guardrails.
 * No network, no n8n required: the n8n globals ($input, $) are mocked.
 */
import { readFileSync } from 'fs';
import { createRequire } from 'module';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const require = createRequire(import.meta.url);

const __dirname = dirname(fileURLToPath(import.meta.url));
const NODES = join(__dirname, '..', 'nodes');
const enrichSrc = readFileSync(join(NODES, 'enrich.js'), 'utf8');
const parseSrc  = readFileSync(join(NODES, 'parse.js'), 'utf8');
const sheetRowSrc = readFileSync(join(NODES, 'sheet_row.js'), 'utf8');
const FENCE = String.fromCharCode(96, 96, 96); // ```

// Wrap a node body (which ends in `return out;`) into a callable async fn.
const mkEnrich = () => new Function('require', '$input', '$', `return (async () => { ${enrichSrc} })();`);
const mkParse  = () => new Function('$input', '$', `return (async () => { ${parseSrc} })();`);
const mkSheetRow = () => new Function('$input', '$', `return (async () => { ${sheetRowSrc} })();`);
async function sheetRow(obj) {
  const $input = { all: () => [{ json: obj }] };
  return (await mkSheetRow()($input, () => ({ all: () => [] })))[0].json;
}

async function enrich(g, prep = []) {
  const $input = { all: () => [{ json: g }] };
  const $ = () => ({ all: () => prep });
  return (await mkEnrich()(require, $input, $))[0].json;
}
async function parseNode(geminiJson, prep) {
  const $input = { all: () => [{ json: geminiJson }] };
  const $ = () => ({ all: () => [{ json: prep || {} }] });
  return (await mkParse()($input, $))[0].json;
}

// ---- tiny assertion framework ---------------------------------------------
let pass = 0; const failures = [];
const ok = (name, cond, detail = '') => cond ? pass++ : failures.push(name + (detail ? ' :: ' + detail : ''));
const eq = (name, a, b) => ok(name, JSON.stringify(a) === JSON.stringify(b), `got ${JSON.stringify(a)} expected ${JSON.stringify(b)}`);
async function throws(name, fn) {
  try { await fn(); failures.push(name + ' :: expected an error, none thrown'); }
  catch (_) { pass++; }
}

const VULN_CRITICAL = {
  incident_title: 'Critical OpenSSL RCE on perimeter', severity: 'SEV3', incident_type: 'vulnerability-scan',
  affected_services: ['nessus', 'network'], affected_jurisdictions: ['GLOBAL'],
  summary: 'Nessus flagged CVE-2026-21841 CVSS 9.8 remote code execution on edge TLS endpoints.',
  root_cause: 'unpatched OpenSSL in gateway image', cvss_score: 9.8, cve_ids: ['CVE-2026-21841'],
  metrics: { detected_at: '2026-06-20T08:00:00Z', ttr_minutes: 0 },
  action_items: [{ action: 'patch gateways', owner: 'NetSec', priority: 'P0' }, { action: 'validate scan', owner: null, priority: 'P1' }],
  confidence_score: 0.92, blameless_quality: 'good',
};

(async () => {
  // 1) Canonical SEV1 CVSS upgrade -------------------------------------------------
  let e = await enrich(VULN_CRITICAL);
  eq('sev1.computed', e.computed_severity, 'SEV1');
  ok('sev1.score_floor', e.severity_score >= 8, 'score=' + e.severity_score);
  ok('sev1.review', e.severity_review_needed === true);
  ok('sev1.dept', ['SecOps', 'NetSec'].includes(e.department), e.department);
  eq('sev1.jurisdictions', e.affected_jurisdictions, ['GLOBAL']);
  eq('sev1.sensitivity', e.sensitivity, 'confidential');
  eq('sev1.routing_tag', e.routing_tag, 'escalate');
  ok('sev1.tag.page', e.routing_tags.includes('page-oncall'));
  ok('sev1.tag.review', e.routing_tags.includes('severity-review'));
  eq('sev1.actions', [e.action_item_total, e.action_items_without_owner, e.open_p0_actions], [2, 1, 1]);

  // 2) Minor internal: no upgrade, no paging, internal ---------------------------
  e = await enrich({ affected_services: ['email-gateway'], affected_jurisdictions: [], severity: 'SEV4', incident_type: 'other', summary: 'minor phishing filter delay' });
  eq('minor.computed', e.computed_severity, 'SEV4');
  ok('minor.noreview', e.severity_review_needed === false);
  eq('minor.sensitivity', e.sensitivity, 'public');
  eq('minor.department', e.department, 'SecOps');
  ok('minor.no_page', !e.routing_tags.includes('page-oncall'));

  // 3) GLOBAL-only jurisdiction is kept but earns no regulatory weight --------
  e = await enrich({ affected_services: ['auth'], affected_jurisdictions: [] });
  eq('global.jx', e.affected_jurisdictions, ['GLOBAL']);
  ok('global.no_reg', !e.routing_tags.includes('regulatory-review'));

  // 4) GLOBAL discarded once a real jurisdiction is present -------------------
  e = await enrich({ affected_services: ['auth'], affected_jurisdictions: ['UKGC'] });
  eq('globaldrop.jx', e.affected_jurisdictions, ['UKGC']);

  // 5) Security floor + type-routing fallback for an unknown service ----------
  e = await enrich({ incident_type: 'security', affected_services: ['mystery-svc-xyz'], severity: 'SEV4', summary: 'login anomaly observed' });
  eq('sec.department', e.department, 'Security-IR');
  eq('sec.sensitivity', e.sensitivity, 'confidential');
  ok('sec.review', e.routing_tags.includes('severity-review'));

  // 5b) Sensitivity regex must not false-positive on 'edge'/'budget'/'discharged' (parity with Python)
  e = await enrich({ incident_type: 'degradation', affected_services: ['network'], affected_jurisdictions: [], severity: 'SEV4', summary: 'Edge CDN cache nodes degraded on staging; cache-refresh budget exhausted.' });
  eq('edge.sensitivity', e.sensitivity, 'public');
  e = await enrich({ incident_type: 'degradation', affected_services: ['internal-tooling'], affected_jurisdictions: [], severity: 'SEV4', summary: 'UPS battery discharged during a scheduled maintenance window; failover engaged.' });
  eq('discharged.sensitivity', e.sensitivity, 'public');
  e = await enrich({ incident_type: 'degradation', affected_services: ['internal-tooling'], affected_jurisdictions: [], severity: 'SEV4', summary: 'Regulator notified; potential fines pending after the customer data exposure.' });
  eq('regulator.sensitivity', e.sensitivity, 'confidential');

  // 6) Severity DOWNGRADE also flags review (disagreement both directions) ----
  e = await enrich({ affected_services: ['email-gateway'], severity: 'SEV1', incident_type: 'other', summary: 'tiny blip' });
  ok('downgrade.lower', ['SEV3', 'SEV4'].includes(e.computed_severity), e.computed_severity);
  ok('downgrade.review', e.severity_review_needed === true);

  // 7) Error-budget breach boundary (>= 50% of budget) -----------------------
  //    vulnerability-scanner SLO 99.0% -> 432 min monthly budget; 50% = 216 min.
  let bAt  = await enrich({ affected_services: ['nessus'], incident_type: 'degradation', metrics: { ttr_minutes: 216 }, summary: 's' });
  let bBel = await enrich({ affected_services: ['nessus'], incident_type: 'degradation', metrics: { ttr_minutes: 215 }, summary: 's' });
  eq('slo.budget', bAt.slo_impact.monthly_budget_minutes, 432);
  ok('slo.breach_at_50', bAt.slo_impact.budget_breach === true);
  ok('slo.no_breach_below', bBel.slo_impact.budget_breach === false);

  // 8) No catalogued service -> SLO null, but fingerprint still produced ------
  e = await enrich({ affected_services: ['nope-unknown'], incident_type: 'other', summary: 's', root_cause: 'x' });
  eq('noslo.target', e.slo_impact.slo_target, null);
  ok('noslo.no_breach', e.slo_impact.budget_breach === false);
  ok('noslo.fingerprint', typeof e.recurrence_fingerprint === 'string' && e.recurrence_fingerprint.length === 12);

  // 9) Fingerprint determinism + word-order independence + sensitivity --------
  const fA = (await enrich({ incident_type: 'intrusion', affected_services: ['siem'], root_cause: 'connection pool exhaustion timeout cascade' })).recurrence_fingerprint;
  const fB = (await enrich({ incident_type: 'intrusion', affected_services: ['siem'], root_cause: 'cascade timeout exhaustion connection pool' })).recurrence_fingerprint;
  const fC = (await enrich({ incident_type: 'intrusion', affected_services: ['siem'], root_cause: 'disk full on the primary database node' })).recurrence_fingerprint;
  ok('fp.stable_order_independent', fA === fB, fA + ' vs ' + fB);
  ok('fp.distinct_for_diff_cause', fA !== fC);
  eq('fp.sha1_parity', fA, '143e0b2a3e2c');

  // 10) Confidence penalties floor at 0 with full notes ----------------------
  e = await enrich({ confidence_score: 0.3, root_cause: '', action_items: [], affected_services: [], metrics: {}, incident_type: 'other', summary: 's' });
  eq('conf.floor', e.confidence_score, 0);
  ok('conf.notes', e.confidence_notes.length >= 4, 'notes=' + e.confidence_notes.length);
  ok('conf.needs_review', e.routing_tags.includes('needs-review'));

  // 11) Action accounting: whitespace owner = unowned; priority case-insens. --
  e = await enrich({ affected_services: ['siem'], incident_type: 'configuration', action_items: [
    { action: 'a', owner: '   ', priority: 'p0' }, { action: 'b', owner: 'Dana', priority: 'P0' }, { action: 'c', owner: null, priority: 'p1' },
  ], summary: 's', metrics: { ttr_minutes: 10 } });
  eq('actions.count', [e.action_item_total, e.action_items_without_owner, e.open_p0_actions], [3, 2, 2]);

  // 12) Robust to long / unicode input (no crash) ----------------------------
  e = await enrich({ affected_services: ['siem'], incident_type: 'intrusion', summary: '🔥 '.repeat(5000) + 'múlti-byte ünïcödé', root_cause: 'x' });
  ok('robust.unicode', e && e.computed_severity);

  // 13) CVSS critical floors to SEV1, escalates, confidential, SecOps --------
  e = await enrich({ incident_type: 'vulnerability-scan', severity: 'SEV3', affected_services: ['nessus'], cvss_score: 9.8, cve_ids: ['CVE-2026-21841'], summary: 'remote code execution finding', root_cause: 'unpatched lib', metrics: { ttr_minutes: 5 } });
  eq('cvss.sev1', e.computed_severity, 'SEV1');
  eq('cvss.routing_tag', e.routing_tag, 'escalate');
  eq('cvss.sensitivity', e.sensitivity, 'confidential');
  eq('cvss.department', e.department, 'SecOps');
  eq('cvss.echo', [e.cvss_score, e.cve_ids], [9.8, ['CVE-2026-21841']]);
  ok('cvss.page', e.routing_tags.includes('page-oncall'));

  // 14) Medium CVSS floors to >= SEV3 even with no other signal ---------------
  e = await enrich({ incident_type: 'vulnerability-scan', severity: 'SEV4', affected_services: ['nessus'], cvss_score: 4.5, summary: 'medium finding' });
  ok('cvss.med_floor', ['SEV1', 'SEV2', 'SEV3'].includes(e.computed_severity), e.computed_severity);

  // 15) Low CVSS does not floor and is not confidential by CVSS --------------
  e = await enrich({ incident_type: 'vulnerability-scan', severity: 'SEV4', affected_services: ['nessus'], cvss_score: 2.0, summary: 'informational', root_cause: 'x', action_items: [{ action: 'note', owner: 'SecOps', priority: 'P2' }], metrics: { ttr_minutes: 0 } });
  ok('cvss.low_nofloor', ['SEV3', 'SEV4'].includes(e.computed_severity), e.computed_severity);

  // 16) routing_tag auto-approved on a clean minor incident ------------------
  e = await enrich({ incident_type: 'degradation', severity: 'SEV4', affected_services: ['email-gateway'], affected_jurisdictions: [], summary: 'minor internal email delay', root_cause: 'queue backlog', action_items: [{ action: 'tune', owner: 'Dana', priority: 'P2' }], confidence_score: 0.9, metrics: { ttr_minutes: 0 } });
  eq('routing.auto', e.routing_tag, 'auto-approved');

  // 17) routing_tag needs-review on low confidence ---------------------------
  e = await enrich({ incident_type: 'other', severity: 'SEV3', confidence_score: 0.3, root_cause: '', action_items: [], affected_services: [], metrics: {}, summary: 's' });
  eq('routing.needs_review', e.routing_tag, 'needs-review');

  // 18) intrusion -> Security-IR, ddos -> NetSec ---------------------------
  e = await enrich({ incident_type: 'intrusion', affected_services: ['nope-xyz'], summary: 'active intrusion' });
  eq('intrusion.dept', e.department, 'Security-IR');
  e = await enrich({ incident_type: 'ddos', affected_services: ['nope-xyz'], summary: 'volumetric flood' });
  eq('ddos.dept', e.department, 'NetSec');

  // 19) CVSS clamp parity with the FastAPI brain (0-10) ----------------------
  e = await enrich({ incident_type: 'vulnerability-scan', affected_services: ['nessus'], cvss_score: 15.0, summary: 'x' });
  eq('cvss.clamp', e.cvss_score, 10);

  // 20) Non-numeric CVSS -> null (parity: Pydantic rejects bad floats) --------
  e = await enrich({ incident_type: 'vulnerability-scan', affected_services: ['nessus'], cvss_score: 'oops', summary: 'x', root_cause: 'y', action_items: [{ action: 'a', owner: 'SecOps' }], metrics: { ttr_minutes: 0 } });
  eq('cvss.nan_null', e.cvss_score, null);
  ok('cvss.nan_nofloor', ['SEV3', 'SEV4'].includes(e.computed_severity), e.computed_severity);

  // ---- Parse-node guardrails ------------------------------------------------
  const VALID_PARSE = {
    incident_title: 'X', severity: 'SEV3', incident_type: 'other',
    summary: 'test summary', sentiment: 'neutral',
    entities: { people: [], teams: [], systems: [], dates: [], error_codes: [] },
    action_items: [{ action: 'review', owner: 'SecOps', priority: 'P2' }],
    confidence_score: 0.85,
  };
  let p = await parseNode({ candidates: [{ content: { parts: [{ text: JSON.stringify(VALID_PARSE) }] } }] }, { correlationId: 'c1', sourceFilename: 'f.md' });
  eq('parse.clean.title', p.incident_title, 'X');
  eq('parse.clean.corr', p.correlation_id, 'c1');
  eq('parse.clean.file', p.source_filename, 'f.md');

  p = await parseNode({ candidates: [{ content: { parts: [{ text: FENCE + 'json\n' + JSON.stringify({ ...VALID_PARSE, incident_title: 'Fenced' }) + '\n' + FENCE }] } }] }, {});
  eq('parse.fenced_json', p.incident_title, 'Fenced');

  p = await parseNode({ candidates: [{ content: { parts: [{ text: FENCE + '\n' + JSON.stringify({ ...VALID_PARSE, classification: 'phishing' }) + '\n' + FENCE }] } }] }, {});
  eq('parse.fenced_plain', p.classification, 'phishing');

  await throws('parse.malformed_throws', () => parseNode({ candidates: [{ content: { parts: [{ text: 'definitely not json {' }] } }] }, {}));
  await throws('parse.missing_candidates_throws', () => parseNode({}, {}));
  await throws('parse.missing_fields_throws', () => parseNode({ candidates: [{ content: { parts: [{ text: '{"incident_title":"X","severity":"SEV3"}' }] } }] }, {}));
  await throws('parse.missing_entities_throws', () => parseNode({ candidates: [{ content: { parts: [{ text: JSON.stringify({ ...VALID_PARSE, entities: undefined }) }] } }] }, {}));
  await throws('parse.bad_confidence_throws', () => parseNode({ candidates: [{ content: { parts: [{ text: JSON.stringify({ ...VALID_PARSE, confidence_score: 1.5 }) }] } }] }, {}));

  p = await parseNode({ candidates: [{ content: { parts: [{ text: JSON.stringify({ ...VALID_PARSE, sentiment: 'INVALID' }) }] } }] }, {});
  eq('parse.sentiment_default', p.sentiment, 'neutral');
  p = await parseNode({ candidates: [{ content: { parts: [{ text: JSON.stringify({ ...VALID_PARSE, sentiment: 'negative' }) }] } }] }, {});
  eq('parse.sentiment_valid', p.sentiment, 'negative');

  // ---- sheet_row (Flatten for Sheets): strict 14-col contract + safe defaults
  const SHEET_KEYS = ["document_id","filename","file_type","processed_at","classification","department","sentiment","confidence_score","summary","routing_tag","sensitivity","action_items","cvss_score","cve_ids"];
  let sr = await sheetRow({ document_id: 'd1', filename: 'f.md', classification: 'phishing' });
  eq('sheetrow.exact_keys', Object.keys(sr).sort(), SHEET_KEYS.slice().sort());
  ok('sheetrow.no_undefined_or_null', SHEET_KEYS.every(k => sr[k] !== undefined && sr[k] !== null), JSON.stringify(sr));
  eq('sheetrow.missing_is_empty_string', sr.cvss_score, '');
  eq('sheetrow.present_value_kept', sr.filename, 'f.md');
  // extra keys outside the contract are dropped
  sr = await sheetRow({ filename: 'g.md', computed_severity: 'SEV1', secret: 'x' });
  ok('sheetrow.drops_extra_keys', sr.computed_severity === undefined && sr.secret === undefined);

  // ---- report ---------------------------------------------------------------
  const total = pass + failures.length;
  console.log(`\nHINDSIGHT Cloud node tests: ${pass}/${total} passed`);
  if (failures.length) { console.log('FAILURES:'); failures.forEach(f => console.log('  ✗ ' + f)); process.exit(1); }
  console.log('All Cloud Code-node edge-case + guardrail tests passed ✔');
})();
