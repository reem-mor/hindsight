#!/usr/bin/env python3
"""Generate a vulnerability-scan PDF with an embedded severity-trend chart, so the
Gemini Vision branch of the pipeline has a cyber-domain document to read.

Portable: writes next to this script. Requires matplotlib + reportlab:
    pip install matplotlib reportlab
Run:
    python samples/make_cyber_pdf_sample.py
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(OUT_DIR, "_vuln_severity_trend.png")
PDF = os.path.join(OUT_DIR, "vuln_scan_sev1_critical_rce.pdf")


def render_chart() -> float:
    """Render a dark 'security dashboard' panel: open critical vulns per scan."""
    t0 = datetime(2026, 6, 1)
    days = np.arange(0, 18)
    dates = [t0 + timedelta(days=int(d)) for d in days]
    # Critical vuln count: low, then a vendor disclosure spikes it on 2026-06-18.
    critical = np.array([1, 1, 0, 2, 1, 1, 0, 1, 2, 1, 1, 0, 1, 2, 1, 1, 23, 21])
    high = np.array([6, 5, 7, 6, 8, 7, 6, 9, 7, 8, 6, 7, 8, 9, 7, 8, 14, 13])

    plt.rcParams.update(
        {
            "figure.facecolor": "#0F1419",
            "axes.facecolor": "#11161D",
            "axes.edgecolor": "#2A333E",
            "axes.labelcolor": "#9AA7B4",
            "xtick.color": "#7A8794",
            "ytick.color": "#7A8794",
            "text.color": "#C7D2DC",
            "font.size": 10,
        }
    )
    fig, ax = plt.subplots(figsize=(8.6, 3.1), dpi=150)
    ax.plot(dates, critical, color="#FF4D5E", linewidth=2.0, label="critical (CVSS >= 9)")
    ax.fill_between(dates, critical, color="#FF4D5E", alpha=0.16)
    ax.plot(dates, high, color="#FFA23F", linewidth=1.4, label="high (CVSS 7-8.9)")
    ax.set_title(
        "payments estate \u00b7 open vulnerabilities by severity \u00b7 Nessus",
        color="#E6EDF3",
        fontsize=11,
        loc="left",
        pad=10,
    )
    ax.set_ylabel("open vulns")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    ax.grid(True, color="#1C232C", linewidth=0.8)
    for s in ax.spines.values():
        s.set_color("#2A333E")
    peak = int(critical.max())
    ann = dates[int(np.argmax(critical))]
    ax.annotate(
        f"CVE-2026-21841 disclosed: {peak} critical",
        xy=(ann, peak),
        xytext=(t0 + timedelta(days=4), peak - 4),
        color="#FF4D5E",
        fontsize=9,
        arrowprops=dict(arrowstyle="->", color="#FF4D5E"),
    )
    ax.legend(facecolor="#11161D", edgecolor="#2A333E", labelcolor="#C7D2DC", fontsize=8)
    fig.tight_layout()
    fig.savefig(IMG, facecolor=fig.get_facecolor())
    plt.close(fig)
    return float(peak)


def build_pdf() -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Image,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("H", parent=styles["Title"], fontSize=18, spaceAfter=4))
    styles.add(ParagraphStyle("Meta", parent=styles["Normal"], textColor=colors.HexColor("#555"), fontSize=9))
    styles.add(
        ParagraphStyle(
            "Sec", parent=styles["Heading2"], fontSize=12,
            textColor=colors.HexColor("#1a2b3c"), spaceBefore=12, spaceAfter=4,
        )
    )
    body = styles["BodyText"]

    doc = SimpleDocTemplate(
        PDF, pagesize=A4, topMargin=20 * mm, bottomMargin=18 * mm,
        leftMargin=20 * mm, rightMargin=20 * mm,
        title="Vulnerability Scan: Critical RCE in payments estate",
        author="SecOps vulnerability management",
    )
    story = [
        Paragraph("Vulnerability Scan: Critical RCE in payments estate", styles["H"]),
        Paragraph(
            "Scan date: 2026-06-18 &nbsp;\u00b7&nbsp; Scanner: Tenable Nessus &nbsp;\u00b7&nbsp; "
            "Author: SecOps vulnerability management",
            styles["Meta"],
        ),
        Spacer(1, 10),
        Paragraph("Summary", styles["Sec"]),
        Paragraph(
            "An authenticated Nessus scan flagged a critical remote code execution vulnerability "
            "(CVE-2026-21841, CVSS 9.8) in the TLS termination library used by the payments gateway "
            "and wallet hosts. 23 internet-facing hosts are affected. The hosts process customer "
            "funds data across UKGC, NJ-DGE and MGM jurisdictions. No exploitation observed yet.",
            body,
        ),
        Paragraph("Open vulnerabilities at time of scan", styles["Sec"]),
        Image(IMG, width=165 * mm, height=59 * mm),
        Paragraph(
            "Figure: open vulnerabilities by severity. Critical count jumps from ~1 to 23 on "
            "2026-06-18 when CVE-2026-21841 was disclosed and matched across the payments estate.",
            styles["Meta"],
        ),
        Paragraph("Finding detail", styles["Sec"]),
    ]
    detail = [
        ["CVE", "CVE-2026-21841"],
        ["CVSS", "9.8 (Critical) \u2014 network / low complexity / no auth"],
        ["Affected", "payments-gateway, wallet (23 hosts)"],
        ["Jurisdictions", "UKGC, NJ-DGE, MGM"],
    ]
    tbl = Table(detail, colWidths=[30 * mm, 132 * mm])
    tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.HexColor("#1a2b3c")),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, -2), 0.4, colors.HexColor("#E2E6EA")),
            ]
        )
    )
    story.append(tbl)
    story.append(Paragraph("Action items", styles["Sec"]))
    for a in [
        "Rebuild payments-gateway and wallet images against the patched library \u2014 owner: Payments-SRE \u2014 priority: P0",
        "Apply WAF virtual-patch as interim mitigation \u2014 owner: SecOps \u2014 priority: P0",
        "Confirm no exploitation in SIEM handshake logs \u2014 owner: SecOps \u2014 priority: P1",
    ]:
        story.append(Paragraph("\u2022 " + a, body))
    story.append(Paragraph("Notes", styles["Sec"]))
    story.append(
        Paragraph(
            "PCI and multi-jurisdiction exposure \u2014 treat as confidential. CVSS 9.8 should be "
            "triaged as a critical, paging event.",
            body,
        )
    )
    doc.build(story)


if __name__ == "__main__":
    peak = render_chart()
    print("chart peak critical = %d" % peak)
    build_pdf()
    print("wrote", PDF, os.path.getsize(PDF), "bytes")
