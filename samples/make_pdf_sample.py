#!/usr/bin/env python3
"""Generate a realistic postmortem PDF with an embedded Grafana-style dashboard
screenshot, so the Gemini Vision branch of the pipeline has something to read."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from datetime import datetime, timedelta
import os

OUT_DIR = "/home/claude/hindsight/samples"
IMG = os.path.join(OUT_DIR, "_edge_cdn_error_rate.png")
PDF = os.path.join(OUT_DIR, "edge_cdn_sev2_eu_errors.pdf")

# ---------- 1. render a dark "Grafana" error-rate panel ----------
t0 = datetime(2026, 6, 9, 18, 0)
mins = np.arange(0, 180, 2)
times = [t0 + timedelta(minutes=int(m)) for m in mins]
base = 0.4 + 0.15 * np.sin(mins / 30)            # healthy ~0.4%
err = base.copy()
spike = (mins >= 40) & (mins <= 95)              # incident window
err[spike] += np.interp(mins[spike], [40, 58, 95], [0, 7.8, 0.6])
err += np.random.default_rng(17).normal(0, 0.06, len(err))
err = np.clip(err, 0, None)

plt.rcParams.update({
    "figure.facecolor": "#0F1419", "axes.facecolor": "#11161D",
    "axes.edgecolor": "#2A333E", "axes.labelcolor": "#9AA7B4",
    "xtick.color": "#7A8794", "ytick.color": "#7A8794",
    "text.color": "#C7D2Dc", "font.size": 10,
})
fig, ax = plt.subplots(figsize=(8.6, 3.1), dpi=150)
ax.plot(times, err, color="#FF6B4A", linewidth=1.8)
ax.fill_between(times, err, color="#FF6B4A", alpha=0.16)
ax.axhline(2.0, color="#FFD23F", linewidth=1, linestyle="--", alpha=0.7)
ax.text(times[2], 2.2, "SLO error budget 2.0%", color="#FFD23F", fontsize=8)
ax.set_title("edge-cdn · 5xx error rate (%) · eu-west", color="#E6EDF3",
             fontsize=11, loc="left", pad=10)
ax.set_ylabel("error rate %")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
ax.set_ylim(0, 9)
ax.grid(True, color="#1C232C", linewidth=0.8)
for s in ax.spines.values():
    s.set_color("#2A333E")
ann = times[int(np.argmax(err))]
ax.annotate(f"peak {err.max():.1f}%", xy=(ann, err.max()),
            xytext=(ann + timedelta(minutes=18), err.max() - 1.2),
            color="#FF6B4A", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="#FF6B4A"))
fig.tight_layout()
fig.savefig(IMG, facecolor=fig.get_facecolor())
plt.close(fig)
print("chart peak %.1f%%" % err.max())

# ---------- 2. assemble the postmortem PDF ----------
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Image,
                                Table, TableStyle)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

styles = getSampleStyleSheet()
styles.add(ParagraphStyle("H", parent=styles["Title"], fontSize=18, spaceAfter=4))
styles.add(ParagraphStyle("Meta", parent=styles["Normal"], textColor=colors.HexColor("#555"), fontSize=9))
styles.add(ParagraphStyle("Sec", parent=styles["Heading2"], fontSize=12,
                          textColor=colors.HexColor("#1a2b3c"), spaceBefore=12, spaceAfter=4))
body = styles["BodyText"]

doc = SimpleDocTemplate(PDF, pagesize=A4, topMargin=20*mm, bottomMargin=18*mm,
                        leftMargin=20*mm, rightMargin=20*mm,
                        title="Postmortem: EU edge errors during UCL match",
                        author="Reliability on-call")
story = []
story.append(Paragraph("Postmortem: EU edge errors during UCL match", styles["H"]))
story.append(Paragraph("Date: 2026-06-09 &nbsp;·&nbsp; Status: Resolved &nbsp;·&nbsp; "
                       "Authors: Edge / Reliability on-call", styles["Meta"]))
story.append(Spacer(1, 10))

story.append(Paragraph("Summary", styles["Sec"]))
story.append(Paragraph(
    "During a high-traffic Champions League fixture, the EU edge CDN began returning elevated "
    "5xx errors for static and API traffic in eu-west. A bad cache configuration pushed to the "
    "edge fleet caused a subset of nodes to fail origin fetches. Sportsbook and casino static "
    "assets were intermittently unavailable to EU players for roughly 55 minutes during peak.", body))

story.append(Paragraph("Impact", styles["Sec"]))
story.append(Paragraph(
    "Affected services: edge-cdn, sportsbook. Error rate on the EU edge peaked near 8% against "
    "a 2% SLO error budget. Jurisdictions affected: UKGC. No data loss; degraded availability "
    "for EU players only. Detected at 18:40 UTC, mitigated at 19:35 UTC.", body))

story.append(Paragraph("Dashboard at time of incident", styles["Sec"]))
story.append(Image(IMG, width=165*mm, height=59*mm))
story.append(Paragraph(
    "Figure: EU edge 5xx error rate. Healthy baseline ~0.4%; the spike begins at 18:40 and "
    "peaks around 18:58 before recovering after the rollback.", styles["Meta"]))

story.append(Paragraph("Timeline (UTC)", styles["Sec"]))
tl = [
    ["18:34", "Edge cache config v220 rolled to EU fleet"],
    ["18:40", "5xx error-rate alert fires for eu-west; on-call paged"],
    ["18:51", "Bad config correlated with the 18:34 rollout"],
    ["19:12", "Rollback of v220 begins, node by node"],
    ["19:35", "Error rate back under SLO; incident closed"],
]
tbl = Table(tl, colWidths=[22*mm, 140*mm])
tbl.setStyle(TableStyle([
    ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
    ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a2b3c")),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E2E6EA")),
]))
story.append(tbl)

story.append(Paragraph("Root cause", styles["Sec"]))
story.append(Paragraph(
    "Cache config v220 set an origin-fetch timeout below the origin's p99 response time for a "
    "subset of routes. Under match-peak load, those routes exceeded the timeout and the edge "
    "returned 5xx instead of serving stale or waiting. The config rolled fleet-wide without a "
    "canary stage.", body))

story.append(Paragraph("Detection", styles["Sec"]))
story.append(Paragraph("Automated alert on EU edge 5xx error rate.", body))

story.append(Paragraph("Action items", styles["Sec"]))
for a in [
    "Add a canary stage to edge config rollouts (1 node, then fleet) — owner: Platform-SRE — priority: high",
    "Set origin-fetch timeout from the origin p99, and serve-stale on timeout — owner: Platform-SRE — priority: high",
    "Add an edge config diff review to the deploy gate — owner: Platform-SRE — priority: medium",
]:
    story.append(Paragraph("• " + a, body))

story.append(Paragraph("Notes", styles["Sec"]))
story.append(Paragraph(
    "TTR ~55 min. This is the second edge-config rollout incident in eu-west this quarter; the "
    "missing canary stage is the recurring theme.", body))

doc.build(story)
print("wrote", PDF, os.path.getsize(PDF), "bytes")
