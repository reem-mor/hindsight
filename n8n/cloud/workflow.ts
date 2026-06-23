import { workflow, node, trigger, sticky, ifElse, expr, newCredential } from '@n8n/workflow-sdk';

const submitForm = trigger({
  type: 'n8n-nodes-base.formTrigger',
  version: 2.2,
  config: {
    name: 'Submit a Postmortem',
    parameters: {
      formTitle: 'HINDSIGHT — Cyber Incident Intake',
      formDescription: 'Upload a cyber incident log (.pdf, .md, or .txt): SIEM export, vulnerability scan, phishing report, or intrusion writeup. HINDSIGHT extracts with Gemini, re-scores severity, routes to SecOps, and files to the registry.',
      formFields: { values: [ { fieldLabel: 'Incident Log', fieldType: 'file', acceptFileTypes: '.pdf,.md,.txt,.markdown', multipleFiles: false, requiredField: true } ] },
      responseMode: 'onReceived',
      options: { appendAttribution: false, respondWithOptions: { values: { respondWith: 'text', formSubmittedText: 'Received — HINDSIGHT is analyzing your postmortem. The registry and your inbox will update momentarily.' } } }
    },
    position: [220, 460]
  },
  output: [{ submittedAt: '2026-06-21T10:00:00.000Z' }]
});

const prepareDoc = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Prepare Document',
    parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: `const PROMPT_HEAD = [
"You are HINDSIGHT, an incident-postmortem intelligence analyst for a regulated,",
"multi-jurisdiction online gaming platform (jurisdictions include UKGC, NJ-DGE,",
"MGM). You read engineering postmortems and extract a precise, structured record.",
"",
"Return ONLY a valid JSON object - no markdown, no code fences, no commentary -",
"with EXACTLY these fields:",
"{",
'  "incident_title": "short human title for the incident",',
'  "summary": "2-3 sentence executive summary of what happened and the impact",',
'  "severity": "one of: [SEV1, SEV2, SEV3, SEV4]",',
'  "incident_type": "one of: [outage, degradation, data-incident, security, deployment-failure, capacity, dependency-failure, configuration, other]",',
'  "status": "one of: [resolved, monitoring, ongoing]",',
'  "affected_services": ["service names exactly as written in the document"],',
'  "affected_jurisdictions": ["any of: UKGC, NJ-DGE, MGM, GLOBAL - only if explicitly impacted"],',
'  "root_cause": "the underlying root cause in one or two sentences",',
'  "trigger": "the immediate trigger that started the incident",',
'  "detection_method": "one of: [alert, monitoring, customer-report, manual, synthetic, unknown]",',
'  "entities": {"people": [], "teams": [], "systems": [], "dates": [], "error_codes": []},',
'  "action_items": [{"action": "follow-up action", "owner": "owner name or null", "priority": "one of: [P0, P1, P2] or null"}],',
'  "contributing_factors": ["secondary factors that made it worse or slower to resolve"],',
'  "sentiment": "one of: [positive, neutral, negative]",',
'  "blameless_quality": "one of: [good, acceptable, poor, unknown]",',
'  "confidence_score": 0.0,',
'  "metrics": {"detected_at": "ISO or null", "resolved_at": "ISO or null", "ttd_minutes": 0, "ttr_minutes": 0, "customer_impact": "one sentence or null"}',
"}",
"",
"RULES:",
"- SEV1 = critical service fully down OR data/security/regulatory exposure OR multi-jurisdiction customer impact; SEV2 = major degradation of a critical service or single-jurisdiction impact; SEV3 = partial/minor; SEV4 = negligible/internal. When unsure pick the LOWER severity; a downstream rubric re-scores and flags disagreements.",
"- Compute ttr_minutes from detected_at/resolved_at when present, else infer from the timeline, else 0.",
"- blameless_quality = 'poor' ONLY when the text blames a named person rather than a process/system gap.",
"- Use null (not empty string) where a value is genuinely unknown.",
"- Do not invent services, people, or jurisdictions not in the document.",
""
].join("\\n");

const items = $input.all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const item = items[idx];
  const bin = item.binary || {};
  const keys = Object.keys(bin);
  if (keys.length === 0) {
    throw new Error("No file was uploaded. Please attach a postmortem (.pdf, .md, or .txt).");
  }
  const key = keys[0];
  const meta = bin[key] || {};
  const fileName = meta.fileName || "postmortem";
  const mimeType = String(meta.mimeType || "").toLowerCase();
  const ext = String(meta.fileExtension || (fileName.split(".").pop() || "")).toLowerCase();
  const isPdf = mimeType.indexOf("pdf") !== -1 || ext === "pdf";

  let buf;
  try {
    buf = await this.helpers.getBinaryDataBuffer(idx, key);
  } catch (e) {
    buf = Buffer.from(meta.data || "", "base64");
  }

  let parts;
  let documentText = "";
  if (isPdf) {
    const b64 = buf.toString("base64");
    const promptText = PROMPT_HEAD
      + "VISION NOTES: The source PDF is attached below. Read any embedded dashboard/Grafana charts or screenshots directly and fold the numbers (error rates, latency, durations) into metrics and summary.\\n"
      + "DOCUMENT: (see attached PDF)";
    parts = [ { text: promptText }, { inline_data: { mime_type: "application/pdf", data: b64 } } ];
  } else {
    documentText = buf.toString("utf-8");
    const promptText = PROMPT_HEAD
      + "VISION NOTES: (none)\\n"
      + "DOCUMENT TEXT:\\n" + documentText;
    parts = [ { text: promptText } ];
  }

  let correlationId;
  if (globalThis.crypto && typeof globalThis.crypto.randomUUID === "function") {
    correlationId = globalThis.crypto.randomUUID();
  } else {
    correlationId = "hs-" + Date.now() + "-" + Math.floor(Math.random() * 1e6);
  }

  const geminiBody = {
    contents: [ { role: "user", parts: parts } ],
    generationConfig: { temperature: 0.1, responseMimeType: "application/json" }
  };

  out.push({ json: {
    correlationId: correlationId,
    sourceFilename: fileName,
    mimeType: mimeType,
    isPdf: isPdf,
    receivedAt: new Date().toISOString(),
    geminiBody: geminiBody
  } });
}
return out;
` },
    position: [440, 460]
  },
  output: [{ correlationId: 'hs-1', sourceFilename: 'incident.pdf', mimeType: 'application/pdf', isPdf: true, receivedAt: '2026-06-21T10:00:00.000Z', geminiBody: { contents: [], generationConfig: {} } }]
});

const geminiExtract = node({
  type: 'n8n-nodes-base.httpRequest',
  version: 4.2,
  config: {
    name: 'Gemini — Extract Incident',
    parameters: {
      method: 'POST',
      url: 'https://generativelanguage.googleapis.com/v1beta/models/gemini-3-flash:generateContent',
      authentication: 'predefinedCredentialType',
      nodeCredentialType: 'googlePalmApi',
      sendBody: true,
      contentType: 'json',
      specifyBody: 'json',
      jsonBody: expr('{{ $json.geminiBody }}'),
      options: { response: { response: { responseFormat: 'json' } } }
    },
    credentials: { googlePalmApi: newCredential('Google Gemini(PaLM) Api account', '466Fl1znBcikPxtF') },
    retryOnFail: true,
    maxTries: 5,
    waitBetweenTries: 3000,
    position: [660, 460]
  },
  output: [{ candidates: [{ content: { parts: [{ text: '{}' }] } }] }]
});

const parseJson = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Parse Gemini JSON',
    parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: `const FENCE = String.fromCharCode(96, 96, 96);
const items = $input.all();
const prep = $("Prepare Document").all();
const out = [];
for (let idx = 0; idx < items.length; idx++) {
  const resp = items[idx].json || {};
  let raw = "";
  try {
    raw = resp.candidates[0].content.parts[0].text || "";
  } catch (e) {
    raw = "";
  }
  raw = String(raw).trim();
  if (raw.indexOf(FENCE) !== -1) {
    raw = raw.split(FENCE).join("");
    if (raw.toLowerCase().indexOf("json") === 0) { raw = raw.slice(4); }
    raw = raw.trim();
  }
  let g;
  try {
    g = JSON.parse(raw);
  } catch (e) {
    throw new Error("Gemini did not return valid JSON. First 200 chars: " + raw.slice(0, 200));
  }
  const p = (prep[idx] && prep[idx].json) ? prep[idx].json : {};
  g.correlation_id = p.correlationId || null;
  g.source_filename = p.sourceFilename || null;
  out.push({ json: g });
}
return out;
` },
    position: [880, 460]
  },
  output: [{ incident_title: 'Example', severity: 'SEV2', incident_type: 'outage', affected_services: [], affected_jurisdictions: [], action_items: [], metrics: {}, entities: {}, correlation_id: 'hs-1' }]
});

const enrichBrain = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'HINDSIGHT Enrich',
    parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: `// HINDSIGHT enrichment - faithful port of the FastAPI /enrich brain.
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
  t = t.replace(/[_\\-\\/]+/g, " ");
  t = t.replace(/[^a-z0-9 ]+/g, "");
  t = t.replace(/\\s+/g, " ");
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
  /\\bdata (loss|breach|leak)\\b/, /\\bbreach\\b/, /\\bpii\\b/, /\\bregulator(y)?\\b/, /\\bfine[sd]?\\b/,
  /\\bfunds?\\b/, /\\bmonetary\\b/, /\\bdouble[- ]charg/, /\\brevenue\\b/, /\\bpayment[s]? (fail|down|unavailable)/,
  /\\bcomplete (outage|down)/, /\\btotal outage\\b/, /\\ball (users|players|customers)\\b/
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
    ["PII / customer-data reference", /\\bpii|customer data|personal data\\b/.test(text)],
    ["monetary / payment exposure", /\\bfunds?|payment|charge|refund|monetary\\b/.test(text)],
    ["regulatory exposure", /\\bregulator|ukgc|dge|fine\\b/.test(text)],
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
  const tokens = String(rootCause || "").toLowerCase().replace(/[^a-z0-9 ]+/g, " ").split(/\\s+/).filter(Boolean);
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
` },
    position: [1100, 460]
  },
  output: [{ document_id: 'doc-1', computed_severity: 'SEV1', severity_score: 9, department: 'Payments-SRE', affected_jurisdictions: ['MGM','NJ-DGE','UKGC'], sensitivity: 'confidential', routing_tags: ['auto-filed','page-oncall'], slo_impact: { budget_burn_pct: 217.6, budget_breach: true }, confidence_score: 0.82 }]
});

const composeOut = node({
  type: 'n8n-nodes-base.code',
  version: 2,
  config: {
    name: 'Compose Outputs',
    parameters: { mode: 'runOnceForAllItems', language: 'javaScript', jsCode: `function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function joinList(a) { return (a && a.length) ? a.join(", ") : ""; }

const SEV_COLOR = { SEV1: "#FF4D5E", SEV2: "#FF9F43", SEV3: "#FFD23F", SEV4: "#4DD0A7" };

const enriched = $input.all();
const parsed = $("Parse Gemini JSON").all();
const out = [];

for (let idx = 0; idx < enriched.length; idx++) {
  const e = enriched[idx].json || {};
  const g = (parsed[idx] && parsed[idx].json) ? parsed[idx].json : {};
  const slo = e.slo_impact || {};
  const ent = g.entities || {};
  const actions = g.action_items || [];
  const sev = e.computed_severity;
  const color = SEV_COLOR[sev] || "#FF9F43";

  // ---- Action items as text + html ----
  let actionsMd = "";
  let actionsHtml = "";
  if (actions.length) {
    for (const a of actions) {
      const owner = (a && a.owner && String(a.owner).trim()) ? String(a.owner) : "UNOWNED";
      const prio = (a && a.priority) ? String(a.priority) : "-";
      actionsMd += "- [" + prio + "] " + String(a.action || "") + "  (owner: " + owner + ")\\n";
      actionsHtml += "<li><b>" + esc(prio) + "</b> " + esc(a.action || "") + " &mdash; <i>" + esc(owner) + "</i></li>";
    }
  } else {
    actionsMd = "- (none extracted)\\n";
    actionsHtml = "<li>(none extracted)</li>";
  }

  let factorsMd = "";
  const factors = g.contributing_factors || [];
  if (factors.length) { for (const f of factors) { factorsMd += "- " + String(f) + "\\n"; } }
  else { factorsMd = "- (none noted)\\n"; }

  // ---- Polished postmortem markdown ----
  const md = ""
    + "# " + sev + " - " + String(e.incident_title || "Untitled incident") + "\\n\\n"
    + "> Auto-classified by HINDSIGHT on " + String(e.processed_at) + "  \\n"
    + "> Correlation ID: " + String(e.correlation_id) + " | Source: " + String(e.source_filename || "n/a") + "\\n\\n"
    + "| Field | Value |\\n|---|---|\\n"
    + "| Reported severity | " + String(e.reported_severity) + " |\\n"
    + "| **Computed severity** | **" + sev + "** (score " + String(e.severity_score) + ") |\\n"
    + "| Severity review needed | " + (e.severity_review ? "YES - rubric disagrees with author" : "no") + " |\\n"
    + "| Owning team | " + String(e.department) + " |\\n"
    + "| Routed teams | " + joinList(e.routed_teams) + " |\\n"
    + "| Resolved services | " + joinList(e.affected_services_resolved) + " |\\n"
    + "| Jurisdictions | " + joinList(e.affected_jurisdictions) + " |\\n"
    + "| Data sensitivity | " + String(e.sensitivity) + " |\\n"
    + "| Incident type | " + String(e.incident_type) + " |\\n"
    + "| Status | " + String(e.status) + " |\\n"
    + "| TTR (minutes) | " + String(e.ttr_minutes) + " |\\n"
    + "| SLO target | " + (slo.slo_target != null ? String(slo.slo_target) + "%" : "n/a") + " |\\n"
    + "| Error-budget burn | " + (slo.budget_burn_pct != null ? String(slo.budget_burn_pct) + "% of monthly" : "n/a") + (slo.budget_breach ? "  ** BUDGET BREACH**" : "") + " |\\n"
    + "| Confidence | " + String(e.confidence_score) + " |\\n"
    + "| Recurrence fingerprint | " + String(e.recurrence_fingerprint) + " |\\n"
    + "| Routing tags | " + joinList(e.routing_tags) + " |\\n\\n"
    + "## Summary\\n" + String(g.summary || e.incident_title || "") + "\\n\\n"
    + "## Root cause\\n" + String(g.root_cause || "(not stated)") + "\\n\\n"
    + "## Trigger\\n" + String(g.trigger || "(not stated)") + "\\n\\n"
    + "## Detection\\n" + String(g.detection_method || "unknown") + "\\n\\n"
    + "## Action items\\n" + actionsMd + "\\n"
    + "## Contributing factors\\n" + factorsMd + "\\n"
    + "## Severity rationale\\n- " + (e.severity_rationale || []).join("\\n- ") + "\\n\\n"
    + "---\\n*HINDSIGHT - institutional memory for incidents. The fire is out; this makes sure it never burns the same way twice.*\\n";

  // ---- Email variants ----
  const tagPills = (e.routing_tags || []).map(function (t) {
    return '<span style="display:inline-block;background:#1b2030;color:#9fb0c8;border:1px solid #2b3550;border-radius:10px;padding:2px 8px;margin:2px;font-size:12px;font-family:monospace">' + esc(t) + "</span>";
  }).join(" ");

  const cardTop = ""
    + '<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:auto;background:#0d1018;color:#e6edf5;border-radius:14px;overflow:hidden;border:1px solid #1f2738">'
    + '<div style="background:' + color + ';height:6px"></div>'
    + '<div style="padding:20px 24px">'
    + '<div style="font-size:12px;letter-spacing:2px;color:' + color + ';font-weight:700;text-transform:uppercase">' + esc(sev) + ' &middot; ' + esc(e.department) + '</div>'
    + '<div style="font-size:21px;font-weight:700;margin:6px 0 14px">' + esc(e.incident_title) + "</div>";

  const cardGrid = ""
    + '<table style="width:100%;border-collapse:collapse;font-size:14px">'
    + '<tr><td style="padding:4px 0;color:#8a97ab">Computed severity</td><td style="text-align:right;font-weight:600">' + esc(sev) + " (score " + esc(e.severity_score) + ")</td></tr>"
    + '<tr><td style="padding:4px 0;color:#8a97ab">Reported severity</td><td style="text-align:right">' + esc(e.reported_severity) + (e.severity_review ? ' <span style="color:' + color + '">&#9888; review</span>' : "") + "</td></tr>"
    + '<tr><td style="padding:4px 0;color:#8a97ab">Jurisdictions</td><td style="text-align:right">' + esc(joinList(e.affected_jurisdictions)) + "</td></tr>"
    + '<tr><td style="padding:4px 0;color:#8a97ab">Sensitivity</td><td style="text-align:right">' + esc(e.sensitivity) + "</td></tr>"
    + '<tr><td style="padding:4px 0;color:#8a97ab">Error-budget burn</td><td style="text-align:right">' + esc(slo.budget_burn_pct != null ? slo.budget_burn_pct + "%" : "n/a") + (slo.budget_breach ? ' <span style="color:' + color + '">breach</span>' : "") + "</td></tr>"
    + '<tr><td style="padding:4px 0;color:#8a97ab">Fingerprint</td><td style="text-align:right;font-family:monospace">' + esc(e.recurrence_fingerprint) + "</td></tr>"
    + "</table>";

  const cardBody = ""
    + '<div style="margin:16px 0;padding:14px;background:#11151f;border-radius:10px;font-size:14px;line-height:1.5;color:#c7d2e0">' + esc(g.summary || "") + "</div>"
    + '<div style="font-size:13px;color:#8a97ab;margin-bottom:6px">Action items</div>'
    + '<ul style="margin:0 0 14px 18px;padding:0;font-size:14px;line-height:1.6">' + actionsHtml + "</ul>"
    + '<div style="margin-bottom:6px">' + tagPills + "</div>"
    + "</div></div>";

  const emailHtmlDigest = cardTop + cardGrid + cardBody;
  const emailHtmlSev1 = ""
    + '<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:auto"><div style="background:' + color + ';color:#1a0408;font-weight:800;padding:10px 16px;border-radius:10px 10px 0 0;letter-spacing:1px">&#128680; SEV1 PAGE &middot; ACTION REQUIRED</div></div>'
    + cardTop + cardGrid + cardBody;

  const subjSev1 = "[SEV1 PAGE] " + String(e.incident_title) + " - " + String(e.department);
  const subjDigest = "[" + sev + "] " + String(e.incident_title) + " - filed by HINDSIGHT";

  out.push({ json: {
    document_id: e.document_id,
    processed_at: e.processed_at,
    correlation_id: e.correlation_id,
    source_filename: e.source_filename,
    incident_title: e.incident_title,
    incident_type: e.incident_type,
    status: e.status,
    reported_severity: e.reported_severity,
    computed_severity: sev,
    severity_score: e.severity_score,
    severity_review: e.severity_review,
    department: e.department,
    routed_teams: joinList(e.routed_teams),
    affected_services: joinList(e.affected_services_resolved),
    affected_jurisdictions: joinList(e.affected_jurisdictions),
    sensitivity: e.sensitivity,
    slo_target: slo.slo_target,
    budget_burn_pct: slo.budget_burn_pct,
    budget_breach: slo.budget_breach,
    recurrence_fingerprint: e.recurrence_fingerprint,
    routing_tags: joinList(e.routing_tags),
    action_items_total: e.action_item_total,
    action_items_unowned: e.action_items_without_owner,
    open_p0_actions: e.open_p0_actions,
    confidence_score: e.confidence_score,
    ttr_minutes: e.ttr_minutes,
    summary: g.summary || "",
    postmortem_markdown: md,
    emailSubjectSev1: subjSev1,
    emailHtmlSev1: emailHtmlSev1,
    emailSubjectDigest: subjDigest,
    emailHtmlDigest: emailHtmlDigest
  } });
}
return out;
` },
    position: [1320, 460]
  },
  output: [{ document_id: 'doc-1', computed_severity: 'SEV1', incident_title: 'Example', department: 'Payments-SRE', affected_jurisdictions: 'MGM, NJ-DGE, UKGC', routing_tags: 'auto-filed, page-oncall', postmortem_markdown: '# SEV1 ...', emailSubjectSev1: '[SEV1 PAGE] Example', emailHtmlSev1: '<div></div>', emailSubjectDigest: '[SEV1] Example', emailHtmlDigest: '<div></div>' }]
});

const appendRegistry = node({
  type: 'n8n-nodes-base.googleSheets',
  version: 4.7,
  config: {
    name: 'Append to Registry',
    parameters: {
      resource: 'sheet',
      operation: 'append',
      documentId: { __rl: true, mode: 'id', value: '1Z7tiPISHB5siYby_lQnWA9wtXbDXVSGTu4HGZ5Dk2tk', cachedResultName: 'HINDSIGHT Incident Registry' },
      sheetName: { __rl: true, mode: 'name', value: 'Incidents' },
      columns: { mappingMode: 'autoMapInputData', value: {} },
      options: { handlingExtraData: 'ignoreIt', useAppend: true }
    },
    credentials: { googleSheetsOAuth2Api: newCredential('Google Sheets Amdocs Course API', '6CH1fQ50fz9t2M9G') },
    position: [1540, 320]
  },
  output: [{ document_id: 'doc-1' }]
});

const sevCheck = ifElse({
  version: 2.2,
  config: {
    name: 'Is SEV1?',
    parameters: {
      conditions: {
        options: { caseSensitive: true, leftValue: '', typeValidation: 'loose' },
        conditions: [{ leftValue: expr('{{ $json.computed_severity }}'), operator: { type: 'string', operation: 'equals' }, rightValue: 'SEV1' }],
        combinator: 'and'
      }
    },
    position: [1540, 600]
  },
  output: [{ computed_severity: 'SEV1' }]
});

const pageOncall = node({
  type: 'n8n-nodes-base.gmail',
  version: 2.2,
  config: {
    name: 'Page On-Call (SEV1)',
    parameters: {
      resource: 'message',
      operation: 'send',
      sendTo: 'reem.mor3@gmail.com',
      subject: expr('{{ $json.emailSubjectSev1 }}'),
      emailType: 'html',
      message: expr('{{ $json.emailHtmlSev1 }}'),
      options: { appendAttribution: false }
    },
    credentials: { gmailOAuth2: newCredential('Gmail Amdocs course API', 'klYiZaTrlUMuEunt') },
    position: [1780, 520]
  },
  output: [{ id: 'msg-1' }]
});

const fileDigest = node({
  type: 'n8n-nodes-base.gmail',
  version: 2.2,
  config: {
    name: 'Postmortem Filed',
    parameters: {
      resource: 'message',
      operation: 'send',
      sendTo: 'reem.mor3@gmail.com',
      subject: expr('{{ $json.emailSubjectDigest }}'),
      emailType: 'html',
      message: expr('{{ $json.emailHtmlDigest }}'),
      options: { appendAttribution: false }
    },
    credentials: { gmailOAuth2: newCredential('Gmail Amdocs course API', 'klYiZaTrlUMuEunt') },
    position: [1780, 680]
  },
  output: [{ id: 'msg-2' }]
});

const noteHeader = sticky('## HINDSIGHT — Postmortem Intelligence (Cloud)\nInstitutional memory for incidents. Upload a postmortem → Gemini extracts it → the rubric re-scores severity → routed, SLO-costed, fingerprinted → filed to the registry + paged.\n\n**One-time setup:** open *Append to Registry* and pick your Google Sheet (tab named Incidents). Add a header row with the column names shown in the node. Credentials for Gemini/Sheets/Gmail are already bound. Emails go to reem.mor3@gmail.com (change in the two Gmail nodes).', [], { color: 4, width: 460, height: 240 });
const note1 = sticky('### 1 — Intake & Vision\nForm upload. PDFs are sent to Gemini natively as inline_data, so embedded dashboard charts are read by real Vision — no separate OCR step.', [submitForm, prepareDoc], { color: 3 });
const note2 = sticky('### 2 — Gemini extraction\ngemini-3-flash returns strict JSON (controlled vocabulary). Auth via the n8n Gemini credential, not a hardcoded key. Retries 5x on transient failures.', [geminiExtract, parseJson], { color: 5 });
const note3 = sticky('### 3 — HINDSIGHT enrichment brain\nDeterministic re-scoring the LLM cannot be trusted to do: service-catalog routing, severity rubric, data-sensitivity, SLO error-budget burn, recurrence fingerprint, routing tags. Mirrors the repo FastAPI /enrich (swap this node for an HTTP call to host it).', [enrichBrain, composeOut], { color: 6 });
const note4 = sticky('### 4 — File & Route\nAppend to the Google Sheets registry (source of truth). SEV1 pages on-call; everything else files a digest. Both carry the full enriched record + generated postmortem.', [appendRegistry, sevCheck, pageOncall, fileDigest], { color: 7 });

export default workflow('hindsight-cloud', 'HINDSIGHT — Postmortem Intelligence (Cloud)')
  .add(submitForm)
  .to(prepareDoc)
  .to(geminiExtract)
  .to(parseJson)
  .to(enrichBrain)
  .to(composeOut)
  .to(appendRegistry)
  .add(composeOut)
  .to(sevCheck.onTrue(pageOncall).onFalse(fileDigest))
  .add(noteHeader)
  .add(note1)
  .add(note2)
  .add(note3)
  .add(note4);
