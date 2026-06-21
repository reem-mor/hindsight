function esc(s) {
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
      actionsMd += "- [" + prio + "] " + String(a.action || "") + "  (owner: " + owner + ")\n";
      actionsHtml += "<li><b>" + esc(prio) + "</b> " + esc(a.action || "") + " &mdash; <i>" + esc(owner) + "</i></li>";
    }
  } else {
    actionsMd = "- (none extracted)\n";
    actionsHtml = "<li>(none extracted)</li>";
  }

  let factorsMd = "";
  const factors = g.contributing_factors || [];
  if (factors.length) { for (const f of factors) { factorsMd += "- " + String(f) + "\n"; } }
  else { factorsMd = "- (none noted)\n"; }

  // ---- Polished postmortem markdown ----
  const md = ""
    + "# " + sev + " - " + String(e.incident_title || "Untitled incident") + "\n\n"
    + "> Auto-classified by HINDSIGHT on " + String(e.processed_at) + "  \n"
    + "> Correlation ID: " + String(e.correlation_id) + " | Source: " + String(e.source_filename || "n/a") + "\n\n"
    + "| Field | Value |\n|---|---|\n"
    + "| Reported severity | " + String(e.reported_severity) + " |\n"
    + "| **Computed severity** | **" + sev + "** (score " + String(e.severity_score) + ") |\n"
    + "| Severity review needed | " + (e.severity_review ? "YES - rubric disagrees with author" : "no") + " |\n"
    + "| Owning team | " + String(e.department) + " |\n"
    + "| Routed teams | " + joinList(e.routed_teams) + " |\n"
    + "| Resolved services | " + joinList(e.affected_services_resolved) + " |\n"
    + "| Jurisdictions | " + joinList(e.affected_jurisdictions) + " |\n"
    + "| Data sensitivity | " + String(e.sensitivity) + " |\n"
    + "| Incident type | " + String(e.incident_type) + " |\n"
    + "| Status | " + String(e.status) + " |\n"
    + "| TTR (minutes) | " + String(e.ttr_minutes) + " |\n"
    + "| SLO target | " + (slo.slo_target != null ? String(slo.slo_target) + "%" : "n/a") + " |\n"
    + "| Error-budget burn | " + (slo.budget_burn_pct != null ? String(slo.budget_burn_pct) + "% of monthly" : "n/a") + (slo.budget_breach ? "  ** BUDGET BREACH**" : "") + " |\n"
    + "| Confidence | " + String(e.confidence_score) + " |\n"
    + "| Recurrence fingerprint | " + String(e.recurrence_fingerprint) + " |\n"
    + "| Routing tags | " + joinList(e.routing_tags) + " |\n\n"
    + "## Summary\n" + String(g.summary || e.incident_title || "") + "\n\n"
    + "## Root cause\n" + String(g.root_cause || "(not stated)") + "\n\n"
    + "## Trigger\n" + String(g.trigger || "(not stated)") + "\n\n"
    + "## Detection\n" + String(g.detection_method || "unknown") + "\n\n"
    + "## Action items\n" + actionsMd + "\n"
    + "## Contributing factors\n" + factorsMd + "\n"
    + "## Severity rationale\n- " + (e.severity_rationale || []).join("\n- ") + "\n\n"
    + "---\n*HINDSIGHT - institutional memory for incidents. The fire is out; this makes sure it never burns the same way twice.*\n";

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
