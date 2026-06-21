// HINDSIGHT enrichment - faithful port of the FastAPI /enrich brain.
// Pure computation (no network). Mirrors services/enrichment-api in the repo.
const DEFAULTS = { team: "SRE-Platform", tier: "standard", slo: 99.9, jurisdictions: ["GLOBAL"] };
const SERVICES = [
  { name: "payments-gateway", aliases: ["payments","payment gateway","pay-gw","psp","deposits","withdrawals"], team: "Payments-SRE", tier: "critical", slo: 99.95, jurisdictions: ["UKGC","NJ-DGE","MGM"] },
  { name: "wallet", aliases: ["wallet-svc","player wallet","balance service","ledger"], team: "Payments-SRE", tier: "critical", slo: 99.95, jurisdictions: ["UKGC","NJ-DGE","MGM"] },
  { name: "casino-platform", aliases: ["casino","rgs","game server","slots platform","game-platform"], team: "Platform-SRE", tier: "critical", slo: 99.9, jurisdictions: ["UKGC","NJ-DGE"] },
  { name: "sportsbook", aliases: ["betting engine","trading platform","odds-service","sports"], team: "Sportsbook-SRE", tier: "critical", slo: 99.9, jurisdictions: ["UKGC","NJ-DGE","MGM"] },
  { name: "identity", aliases: ["auth","authentication","login","sso","session-service","idp"], team: "Identity-SRE", tier: "critical", slo: 99.95, jurisdictions: ["GLOBAL"] },
  { name: "kyc", aliases: ["know your customer","onboarding","verification","aml-screening"], team: "Compliance-Eng", tier: "high", slo: 99.5, jurisdictions: ["UKGC","NJ-DGE","MGM"] },
  { name: "geo-compliance", aliases: ["geolocation","geo-gate","jurisdiction-check","geo-fencing"], team: "Compliance-Eng", tier: "critical", slo: 99.9, jurisdictions: ["NJ-DGE","MGM"] },
  { name: "promotions", aliases: ["bonus engine","promo","rewards","loyalty"], team: "Engagement-Eng", tier: "high", slo: 99.5, jurisdictions: ["UKGC","NJ-DGE"] },
  { name: "reporting-db", aliases: ["data warehouse","analytics db","regulatory reporting","dwh"], team: "Data-Platform", tier: "high", slo: 99.0, jurisdictions: ["UKGC","NJ-DGE","MGM"] },
  { name: "edge-cdn", aliases: ["cdn","edge","waf","reverse proxy","ingress"], team: "Platform-SRE", tier: "high", slo: 99.9, jurisdictions: ["GLOBAL"] },
  { name: "notifications", aliases: ["email service","sms gateway","push","comms"], team: "Engagement-Eng", tier: "standard", slo: 99.0, jurisdictions: ["GLOBAL"] },
  { name: "internal-tooling", aliases: ["jenkins","ci","ci/cd","deploy pipeline","grafana","internal dashboard"], team: "DevEx", tier: "internal", slo: 99.0, jurisdictions: ["GLOBAL"] }
];
const TYPE_ROUTING = { "security":"Security-IR","data-incident":"Compliance-Eng","deployment-failure":"DevEx","capacity":"SRE-Platform","dependency-failure":"SRE-Platform","configuration":"SRE-Platform","outage":"SRE-Platform","degradation":"SRE-Platform","other":"SRE-Platform" };
const REVIEW_THRESHOLD = 0.7;
const BUDGET_BREACH_FRACTION = 0.5;

function norm(t) {
  t = String(t || "").toLowerCase().trim();
  t = t.replace(/[_\-\/]+/g, " ");
  t = t.replace(/[^a-z0-9 ]+/g, "");
  t = t.replace(/\s+/g, " ");
  return t.trim();
}
const LOOKUP = {};
for (const e of SERVICES) {
  const keys = [e.name].concat(e.aliases || []);
  for (const k of keys) { LOOKUP[norm(k)] = e; }
}
function resolveOne(name) {
  if (!name) return null;
  const key = norm(name);
  if (LOOKUP[key]) return LOOKUP[key];
  for (const ak of Object.keys(LOOKUP)) {
    if (ak && (ak.indexOf(key) !== -1 || key.indexOf(ak) !== -1)) return LOOKUP[ak];
  }
  return null;
}
function resolveMany(names) {
  const seen = {};
  const order = [];
  for (const n of (names || [])) {
    const e = resolveOne(n);
    if (e && !seen[e.name]) { seen[e.name] = e; order.push(e); }
  }
  return order;
}

const TIER_SCORE = { critical: 4, high: 3, standard: 2, internal: 1 };
const SEV_RANK = { SEV4: 4, SEV3: 3, SEV2: 2, SEV1: 1 };
const HIGH_IMPACT = [
  /\bdata (loss|breach|leak)\b/, /\bbreach\b/, /\bpii\b/, /\bregulator(y)?\b/, /\bfine[sd]?\b/,
  /\bfunds?\b/, /\bmonetary\b/, /\bdouble[- ]charg/, /\brevenue\b/, /\bpayment[s]? (fail|down|unavailable)/,
  /\bcomplete (outage|down)/, /\btotal outage\b/, /\ball (users|players|customers)\b/
];
function impactHits(text) {
  text = String(text || "").toLowerCase();
  let n = 0;
  for (const re of HIGH_IMPACT) { if (re.test(text)) n++; }
  return n;
}

function round1(x) { return Math.round(x * 10) / 10; }
function round3(x) { return Math.round(x * 1000) / 1000; }

function scoreSeverity(reported, incidentType, resolved, jurisdictions, ttr, summary) {
  let score = 0;
  const rationale = [];
  if (resolved.length) {
    let top = resolved[0];
    for (const e of resolved) { if ((TIER_SCORE[e.tier]||1) > (TIER_SCORE[top.tier]||1)) top = e; }
    const pts = TIER_SCORE[top.tier] || 1;
    score += pts;
    rationale.push("highest-tier service '" + top.name + "' is " + top.tier + " (+" + pts + ")");
  } else {
    rationale.push("no catalogued service matched (+0)");
  }
  const realJx = (jurisdictions || []).filter(function (j) { return j && j.toUpperCase() !== "GLOBAL"; });
  if (realJx.length >= 2) { score += 3; rationale.push("multi-jurisdiction impact (" + realJx.join(", ") + ") (+3)"); }
  else if (realJx.length === 1) { score += 1; rationale.push("single-jurisdiction impact (" + realJx[0] + ") (+1)"); }
  const hits = impactHits(summary);
  if (hits) { const pts = Math.min(hits * 2, 4); score += pts; rationale.push("high-impact language (" + hits + " signal/s) (+" + pts + ")"); }
  const t = ttr || 0;
  if (t >= 120) { score += 3; rationale.push("downtime " + Math.round(t) + " min >= 2h (+3)"); }
  else if (t >= 30) { score += 2; rationale.push("downtime " + Math.round(t) + " min >= 30m (+2)"); }
  else if (t > 0) { score += 1; rationale.push("downtime " + Math.round(t) + " min (+1)"); }
  if (incidentType === "security" || incidentType === "data-incident") { score += 3; rationale.push("incident type '" + incidentType + "' carries regulatory weight (+3)"); }

  let computed;
  if (score >= 9) computed = "SEV1";
  else if (score >= 6) computed = "SEV2";
  else if (score >= 3) computed = "SEV3";
  else computed = "SEV4";

  const delta = Math.abs(SEV_RANK[computed] - (SEV_RANK[reported] || 3));
  const review = delta >= 1;
  if (review) {
    const dir = SEV_RANK[computed] < (SEV_RANK[reported] || 3) ? "higher" : "lower";
    rationale.push("rubric (" + computed + ") is " + dir + " than reported (" + reported + ") -> review");
  }
  return { computed: computed, score: score, rationale: rationale, review: review };
}

function classifySensitivity(incidentType, jurisdictions, entitiesBlob, summary) {
  const text = (String(summary || "") + " " + String(entitiesBlob || "")).toLowerCase();
  const realJx = (jurisdictions || []).filter(function (j) { return j && j.toUpperCase() !== "GLOBAL"; });
  const signals = [
    ["security incident", incidentType === "security"],
    ["data incident", incidentType === "data-incident"],
    ["PII / customer-data reference", /\bpii|customer data|personal data\b/.test(text)],
    ["monetary / payment exposure", /\bfunds?|payment|charge|refund|monetary\b/.test(text)],
    ["regulatory exposure", /\bregulator|ukgc|dge|fine\b/.test(text)],
    ["multi-jurisdiction", realJx.length >= 2]
  ];
  const triggered = [];
  for (const s of signals) { if (s[1]) triggered.push(s[0]); }
  if (triggered.length) return { sensitivity: "confidential", rationale: triggered };
  return { sensitivity: "internal", rationale: ["operational incident, no confidential markers"] };
}

function sloImpact(primary, ttr) {
  if (!primary) return { primary_service: null, slo_target: null, monthly_budget_minutes: null, budget_burn_minutes: null, budget_burn_pct: null, budget_breach: false };
  const minutesPerMonth = 30 * 24 * 60;
  const budget = round1(minutesPerMonth * (1 - primary.slo / 100.0));
  const burn = Number(ttr || 0);
  const burnPct = budget > 0 ? round1((burn / budget) * 100) : null;
  const breach = budget > 0 && burn >= budget * BUDGET_BREACH_FRACTION;
  return { primary_service: primary.name, slo_target: primary.slo, monthly_budget_minutes: budget, budget_burn_minutes: round1(burn), budget_burn_pct: burnPct, budget_breach: breach };
}

const STOP = { "the":1,"a":1,"an":1,"of":1,"to":1,"in":1,"on":1,"and":1,"or":1,"for":1,"was":1,"were":1,"is":1,"due":1,"caused":1,"by":1,"this":1,"that":1,"with":1,"from":1,"after":1,"led":1,"which":1,"resulted":1,"incident":1,"issue":1,"error":1,"failure":1 };
function fingerprint(services, rootCause, incidentType) {
  const tokens = String(rootCause || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").split(/\s+/).filter(Boolean);
  const uniq = {};
  for (const t of tokens) { if (!STOP[t] && t.length > 2) uniq[t] = 1; }
  const kw = Object.keys(uniq).sort().slice(0, 6);
  const basis = [incidentType].concat(services.slice().sort()).concat(kw).join("|");
  let h1 = 0x811c9dc5 >>> 0;
  for (let i = 0; i < basis.length; i++) { h1 ^= basis.charCodeAt(i); h1 = Math.imul(h1, 0x01000193) >>> 0; }
  const basis2 = basis.split("").reverse().join("");
  let h2 = 0x811c9dc5 >>> 0;
  for (let i = 0; i < basis2.length; i++) { h2 ^= basis2.charCodeAt(i); h2 = Math.imul(h2, 0x01000193) >>> 0; }
  return (("00000000" + h1.toString(16)).slice(-8) + ("00000000" + h2.toString(16)).slice(-8)).slice(0, 12);
}

function adjustConfidence(g) {
  let conf = Number(g.confidence_score || 0);
  const notes = [];
  let penalty = 0;
  if (!String(g.root_cause || "").trim()) { penalty += 0.20; notes.push("missing root cause (-0.20)"); }
  if (!(g.action_items && g.action_items.length)) { penalty += 0.10; notes.push("no action items extracted (-0.10)"); }
  if (!(g.affected_services && g.affected_services.length)) { penalty += 0.10; notes.push("no affected services identified (-0.10)"); }
  const m = g.metrics || {};
  const metricsPresent = !!(m.detected_at || m.resolved_at || (m.ttd_minutes !== null && m.ttd_minutes !== undefined) || (m.ttr_minutes !== null && m.ttr_minutes !== undefined));
  if (!metricsPresent) { penalty += 0.05; notes.push("no timing metrics (-0.05)"); }
  let adjusted = Math.max(0, Math.min(1, conf - penalty));
  if (adjusted < REVIEW_THRESHOLD) notes.push("below review threshold " + REVIEW_THRESHOLD);
  return { adjusted: round3(adjusted), delta: round3(adjusted - conf), notes: notes, present: metricsPresent };
}

function uuid() {
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") return globalThis.crypto.randomUUID();
  return "doc-" + Date.now() + "-" + Math.floor(Math.random() * 1e6);
}

const items = $input.all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const g = items[idx].json || {};
  const ent = g.entities || {};
  const resolved = resolveMany(g.affected_services || []);
  const resolvedNames = resolved.map(function (e) { return e.name; });
  let teams = Array.from(new Set(resolved.map(function (e) { return e.team; }))).sort();
  if (!teams.length) teams = [TYPE_ROUTING[g.incident_type] || DEFAULTS.team];
  const department = teams[0];

  const jxSet = {};
  for (const j of (g.affected_jurisdictions || [])) { if (j) jxSet[String(j).toUpperCase()] = 1; }
  for (const e of resolved) { for (const j of e.jurisdictions) { jxSet[j] = 1; } }
  let jxKeys = Object.keys(jxSet);
  if (jxKeys.length > 1 && jxSet["GLOBAL"]) { delete jxSet["GLOBAL"]; jxKeys = Object.keys(jxSet); }
  const jurisdictions = jxKeys.sort();

  const m = g.metrics || {};
  const ttr = Number(m.ttr_minutes || 0);
  const verdict = scoreSeverity(g.severity || "SEV3", g.incident_type || "other", resolved, jurisdictions, ttr, g.summary || "");

  const entitiesBlob = []
    .concat(ent.people || [], ent.teams || [], ent.systems || [], ent.error_codes || [])
    .join(" ");
  const sens = classifySensitivity(g.incident_type || "other", jurisdictions, entitiesBlob, g.summary || "");

  let primary = null;
  if (resolved.length) {
    primary = resolved[0];
    for (const e of resolved) { if ((TIER_SCORE[e.tier]||1) > (TIER_SCORE[primary.tier]||1)) primary = e; }
  }
  const slo = sloImpact(primary, ttr);

  const fp = fingerprint((resolvedNames.length ? resolvedNames : (g.affected_services || [])), g.root_cause || "", g.incident_type || "other");
  const conf = adjustConfidence(g);

  const actions = g.action_items || [];
  const totalActions = actions.length;
  const noOwner = actions.filter(function (a) { return !(a && a.owner && String(a.owner).trim()); }).length;
  const openP0 = actions.filter(function (a) { return a && String(a.priority || "").toUpperCase() === "P0"; }).length;

  const tags = ["auto-filed"];
  if (verdict.computed === "SEV1" || verdict.computed === "SEV2") tags.push("exec-escalation");
  if (verdict.computed === "SEV1") tags.push("page-oncall");
  if (jurisdictions.length >= 2) tags.push("regulatory-review");
  if (verdict.review) tags.push("severity-review");
  if (conf.adjusted < REVIEW_THRESHOLD) tags.push("needs-review");
  if (noOwner > 0) tags.push("unowned-actions");
  if (slo.budget_breach) tags.push("budget-breach");
  if (g.blameless_quality === "poor") tags.push("blameless-coaching");
  const tagsUniq = Array.from(new Set(tags));

  out.push({ json: {
    document_id: uuid(),
    processed_at: new Date().toISOString(),
    correlation_id: g.correlation_id || uuid(),
    source_filename: g.source_filename || null,
    incident_title: g.incident_title || "Untitled incident",
    incident_type: g.incident_type || "other",
    status: g.status || "resolved",
    reported_severity: g.severity || "SEV3",
    computed_severity: verdict.computed,
    severity_score: verdict.score,
    severity_rationale: verdict.rationale,
    severity_review: verdict.review,
    department: department,
    routed_teams: teams,
    affected_services_resolved: resolvedNames,
    affected_jurisdictions: jurisdictions,
    sensitivity: sens.sensitivity,
    sensitivity_rationale: sens.rationale,
    slo_impact: slo,
    recurrence_fingerprint: fp,
    routing_tags: tagsUniq,
    action_item_total: totalActions,
    action_items_without_owner: noOwner,
    open_p0_actions: openP0,
    confidence_score: conf.adjusted,
    confidence_delta: conf.delta,
    confidence_notes: conf.notes,
    ttr_minutes: ttr
  } });
}
return out;
