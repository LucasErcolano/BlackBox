# SPDX-License-Identifier: MIT
"""NTSB-inspired PDF report builder for Black Box forensic reports."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape as _xml_escape


def _esc(s: Any) -> str:
    """Escape untrusted text for reportlab Paragraph mini-XML."""
    return _xml_escape("" if s is None else str(s), {'"': "&quot;", "'": "&apos;"})

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

try:  # Pillow is optional at import time
    from PIL import Image as PILImage  # noqa: F401
except Exception:  # pragma: no cover
    PILImage = None  # type: ignore


# ---------- styles ----------

def _styles():
    base = getSampleStyleSheet()
    styles = {
        "cover_title": ParagraphStyle(
            "cover_title",
            parent=base["Title"],
            fontName="Times-Bold",
            fontSize=28,
            leading=34,
            alignment=1,
            spaceAfter=18,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            leading=16,
            alignment=1,
            spaceAfter=6,
        ),
        "cover_classification": ParagraphStyle(
            "cover_classification",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=1,
            textColor=colors.HexColor("#b22222"),
            spaceAfter=4,
        ),
        "cover_case_key": ParagraphStyle(
            "cover_case_key",
            parent=base["Normal"],
            fontName="Courier-Bold",
            fontSize=14,
            leading=18,
            alignment=1,
            spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Times-Bold",
            fontSize=18,
            leading=22,
            spaceBefore=12,
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=base["Heading2"],
            fontName="Times-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "body",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceAfter=4,
        ),
        "body_small": ParagraphStyle(
            "body_small",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=2,
        ),
        "caption": ParagraphStyle(
            "caption",
            parent=base["Italic"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=11,
            alignment=1,
            textColor=colors.grey,
        ),
        "mono": ParagraphStyle(
            "mono",
            parent=base["Code"],
            fontName="Courier",
            fontSize=8,
            leading=10,
        ),
    }
    return styles


# ---------- helpers ----------

def _rule(width: float, color=colors.grey) -> Table:
    t = Table([[""]], colWidths=[width], rowHeights=[0.5])
    t.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, -1), 0.5, color)]))
    return t


def _pil_to_rl(img, max_w: float, max_h: float | None = None) -> RLImage | None:
    """Convert a PIL image to a reportlab Image, resized to fit max_w/max_h."""
    if img is None:
        return None
    try:
        buf = io.BytesIO()
        # Ensure RGB and save PNG in-memory.
        im = img.convert("RGB") if hasattr(img, "convert") else img
        im.save(buf, format="PNG")
        buf.seek(0)
        w, h = im.size
        aspect = h / float(w) if w else 1.0
        new_w = max_w
        new_h = new_w * aspect
        if max_h and new_h > max_h:
            new_h = max_h
            new_w = new_h / aspect if aspect else max_w
        return RLImage(buf, width=new_w, height=new_h)
    except Exception:
        return None


def _confidence_bar_table(conf: float, width: float) -> Table:
    """Render a filled red confidence bar using a Table."""
    conf = max(0.0, min(1.0, float(conf)))
    filled_w = max(0.01, width * conf)
    empty_w = max(0.01, width - filled_w)
    t = Table([["", ""]], colWidths=[filled_w, empty_w], rowHeights=[6])
    t.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#b22222")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#eeeeee")),
            ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ])
    )
    return t


def _timeline_flowable(events: list[dict], width: float, height: float = 1.1 * inch):
    """Build a timeline drawing as a reportlab Flowable."""
    from reportlab.graphics.shapes import Circle, Drawing, Line, String

    d = Drawing(width, height)
    if not events:
        return d

    baseline_y = height * 0.55
    margin = 10
    line_w = width - 2 * margin
    d.add(Line(margin, baseline_y, margin + line_w, baseline_y,
               strokeColor=colors.black, strokeWidth=0.7))

    ts = [float(e.get("t_ns", 0)) for e in events]
    tmin, tmax = min(ts), max(ts)
    span = (tmax - tmin) or 1.0

    for i, e in enumerate(events):
        t = float(e.get("t_ns", 0))
        x = margin + (t - tmin) / span * line_w
        d.add(Circle(x, baseline_y, 3, fillColor=colors.black, strokeColor=colors.black))
        label = str(e.get("label") or e.get("name") or f"ev{i}")
        # Alternate above/below to reduce overlap.
        if i % 2 == 0:
            y = baseline_y - 14
        else:
            y = baseline_y + 6
        d.add(String(x, y, label[:28], fontName="Helvetica", fontSize=7,
                     textAnchor="middle", fillColor=colors.black))
    return d


# ---------- builder ----------

def build_report(
    report_json: dict,
    artifacts: dict,
    out_pdf: Path,
    case_meta: dict,
) -> Path:
    """Build the forensic PDF. Returns the output path."""
    out_pdf = Path(out_pdf)
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    styles = _styles()
    page_w, page_h = LETTER
    case_key = case_meta.get("case_key", "unknown")
    mode_label = case_meta.get("mode", "post_mortem")
    doc = SimpleDocTemplate(
        str(out_pdf),
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.95 * inch,
        bottomMargin=0.85 * inch,
        title=f"Black Box Report — {case_key}",
        author="Black Box",
    )
    content_w = page_w - doc.leftMargin - doc.rightMargin

    def _draw_page_chrome(canvas, doc_):
        canvas.saveState()
        # Top rule
        canvas.setStrokeColor(colors.black)
        canvas.setLineWidth(0.75)
        canvas.line(
            doc_.leftMargin,
            page_h - 0.55 * inch,
            page_w - doc_.rightMargin,
            page_h - 0.55 * inch,
        )
        # Header text
        canvas.setFont("Times-Bold", 9)
        canvas.setFillColor(colors.black)
        canvas.drawString(
            doc_.leftMargin,
            page_h - 0.42 * inch,
            "BLACK BOX — FORENSIC REPORT",
        )
        canvas.setFont("Courier", 8)
        canvas.setFillColor(colors.HexColor("#6b6b66"))
        canvas.drawRightString(
            page_w - doc_.rightMargin,
            page_h - 0.42 * inch,
            f"CASE {case_key} · {mode_label}",
        )
        # Footer rule + page number
        canvas.setStrokeColor(colors.HexColor("#b0ac9f"))
        canvas.setLineWidth(0.35)
        canvas.line(
            doc_.leftMargin,
            0.58 * inch,
            page_w - doc_.rightMargin,
            0.58 * inch,
        )
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6b6b66"))
        canvas.drawString(doc_.leftMargin, 0.42 * inch, "Inference-only · Opus 4.7")
        canvas.drawRightString(
            page_w - doc_.rightMargin,
            0.42 * inch,
            f"Page {canvas.getPageNumber()}",
        )
        canvas.restoreState()

    hypotheses = list(report_json.get("hypotheses", []) or [])
    timeline = list(report_json.get("timeline", []) or [])

    story: list[Any] = []

    # ---------- 1. Cover ----------
    story.append(Spacer(1, 1.1 * inch))
    story.append(Paragraph(
        "— OFFICIAL CASE REPORT · FOR TECHNICAL REVIEW —",
        styles["cover_classification"],
    ))
    story.append(Spacer(1, 0.12 * inch))
    story.append(Paragraph("BLACK BOX — FORENSIC REPORT", styles["cover_title"]))
    story.append(_rule(content_w * 0.6, colors.black))
    story.append(Spacer(1, 0.3 * inch))
    story.append(Paragraph(case_key, styles["cover_case_key"]))
    story.append(Paragraph(f"Mode: {mode_label}", styles["cover_meta"]))
    if case_meta.get("bag_path"):
        story.append(Paragraph(f"Source: {case_meta['bag_path']}", styles["cover_meta"]))
    if case_meta.get("duration_s") is not None:
        story.append(Paragraph(f"Duration: {case_meta['duration_s']:.2f} s",
                               styles["cover_meta"]))
    story.append(Paragraph(
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ')}",
        styles["cover_meta"],
    ))
    story.append(Spacer(1, 0.3 * inch))
    story.append(_rule(content_w * 0.6, colors.grey))
    story.append(Spacer(1, 0.3 * inch))

    if hypotheses:
        first = hypotheses[0]
        one_sent = first.get("summary") or first.get("bug_class") or "See body for details."
    else:
        one_sent = "Nothing anomalous detected."
    story.append(Paragraph(f"<i>{_esc(one_sent)}</i>", styles["cover_meta"]))
    story.append(PageBreak())

    # ---------- 2. Executive summary ----------
    story.append(Paragraph("Executive Summary", styles["h1"]))
    story.append(_rule(content_w))
    story.append(Spacer(1, 6))
    if hypotheses:
        # Find root cause (highest-confidence, or explicitly flagged).
        root_idx = 0
        best = -1.0
        for i, h in enumerate(hypotheses):
            if h.get("is_root_cause"):
                root_idx = i
                break
            c = float(h.get("confidence", 0.0) or 0.0)
            if c > best:
                best = c
                root_idx = i

        bar_w = content_w * 0.35
        rows = []
        for i, h in enumerate(hypotheses):
            tag = " <b>[ROOT CAUSE]</b>" if i == root_idx else ""
            bug_class = h.get("bug_class", "unclassified")
            summary = h.get("summary", "")
            conf = float(h.get("confidence", 0.0) or 0.0)
            label_html = (
                f"<b>{i + 1}. {_esc(bug_class)}</b>{tag}<br/>"
                f"<font size=9>{_esc(summary)}</font>"
            )
            rows.append([
                Paragraph(label_html, styles["body"]),
                _confidence_bar_table(conf, bar_w),
                Paragraph(f"{conf:.2f}", styles["body_small"]),
            ])
        tbl = Table(rows, colWidths=[content_w - bar_w - 0.6 * inch, bar_w, 0.6 * inch])
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.lightgrey),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No hypotheses generated.", styles["body"]))

    # ---------- 3. Timeline ----------
    if timeline:
        story.append(Spacer(1, 0.25 * inch))
        story.append(Paragraph("Timeline", styles["h1"]))
        story.append(_rule(content_w))
        story.append(Spacer(1, 6))
        story.append(_timeline_flowable(timeline, content_w, height=1.2 * inch))
        story.append(Spacer(1, 4))
        # tabular detail
        rows = [["t_ns", "label", "source"]]
        for ev in timeline[:40]:
            rows.append([
                str(ev.get("t_ns", "")),
                str(ev.get("label") or ev.get("name") or ""),
                str(ev.get("source", "")),
            ])
        tbl = Table(rows, colWidths=[content_w * 0.3, content_w * 0.5, content_w * 0.2])
        tbl.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9),
            ("FONT", (0, 1), (-1, -1), "Helvetica", 8),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(tbl)

    # ---------- 4. Annotated frames ----------
    frames = [f for f in (artifacts.get("frames") or []) if f is not None][:6]
    if frames:
        story.append(PageBreak())
        story.append(Paragraph("Annotated Frames", styles["h1"]))
        story.append(_rule(content_w))
        frame_w = content_w * (2.0 / 3.0)
        for i, fr in enumerate(frames):
            rl = _pil_to_rl(fr, max_w=frame_w, max_h=4.5 * inch)
            if rl is None:
                continue
            story.append(Spacer(1, 6))
            story.append(rl)
            story.append(Paragraph(f"Figure {i + 1}. Frame {i + 1} (annotated).",
                                   styles["caption"]))

    # ---------- 5. Plots ----------
    plots = [p for p in (artifacts.get("plots") or []) if p is not None][:3]
    if plots:
        story.append(PageBreak())
        story.append(Paragraph("Telemetry", styles["h1"]))
        story.append(_rule(content_w))
        for i, pl in enumerate(plots):
            rl = _pil_to_rl(pl, max_w=content_w, max_h=4.0 * inch)
            if rl is None:
                continue
            story.append(Spacer(1, 6))
            story.append(rl)
            story.append(Paragraph(f"Plot {i + 1}.", styles["caption"]))

    # ---------- 6. Hypotheses detail ----------
    if hypotheses:
        story.append(PageBreak())
        story.append(Paragraph("Hypotheses", styles["h1"]))
        story.append(_rule(content_w))
        for i, h in enumerate(hypotheses):
            story.append(Spacer(1, 6))
            bug_class = h.get("bug_class", "unclassified")
            conf = float(h.get("confidence", 0.0) or 0.0)
            story.append(Paragraph(f"{i + 1}. {_esc(bug_class)} &nbsp; "
                                   f"<font color='grey'>confidence {conf:.2f}</font>",
                                   styles["h2"]))
            if h.get("summary"):
                story.append(Paragraph(_esc(h["summary"]), styles["body"]))
            evidence = h.get("evidence") or []
            if evidence:
                story.append(Paragraph("<b>Evidence</b>", styles["body"]))
                for ev in evidence:
                    src = ev.get("source", "")
                    topic = ev.get("topic_or_file") or ev.get("topic") or ev.get("file") or ""
                    tns = ev.get("t_ns")
                    snippet = ev.get("snippet", "")
                    tns_str = f" @ t_ns={tns}" if tns is not None else ""
                    story.append(Paragraph(
                        f"&bull; <b>{_esc(src)}</b> <i>{_esc(topic)}</i>{_esc(tns_str)}<br/>"
                        f"<font face='Courier' size=8>{_esc(snippet)}</font>",
                        styles["body_small"],
                    ))
            if h.get("patch_hint"):
                story.append(Paragraph(f"<b>Patch hint:</b> {_esc(h['patch_hint'])}",
                                       styles["body_small"]))

    # ---------- 7. Proposed patch ----------
    code_diff = artifacts.get("code_diff")
    if code_diff:
        story.append(PageBreak())
        story.append(Paragraph("Proposed Patch", styles["h1"]))
        story.append(_rule(content_w))
        story.append(Spacer(1, 6))
        story.append(Preformatted(code_diff, styles["mono"]))

    doc.build(story, onFirstPage=_draw_page_chrome, onLaterPages=_draw_page_chrome)
    return out_pdf
