"""Word (.docx) justification report, mirroring the structure of the team's validation write-ups."""

from __future__ import annotations

import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from .models import CONTRIBUTION_REQUIREMENTS, CONTRIBUTIONS, FEASIBILITY_CHECKS, Project
from .scoring import DEFER, DUPLICATE, PROCEED, Assessment

VERDICT_COLORS = {
    PROCEED: RGBColor(0x1B, 0x7F, 0x3B),
    DEFER: RGBColor(0xB0, 0x3A, 0x2E),
    DUPLICATE: RGBColor(0xB0, 0x3A, 0x2E),
}
MARK = {"ok": "✔", "warn": "!", "fail": "✘", "info": "•"}


def _table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Light Grid Accent 1"
    for cell, text in zip(table.rows[0].cells, headers):
        cell.text = text
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for row in rows:
        cells = table.add_row().cells
        for cell, text in zip(cells, row):
            cell.text = text or "—"
    doc.add_paragraph()


def build_report(p: Project, a: Assessment, today: date | None = None) -> bytes:
    today = today or date.today()
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    doc.add_heading(p.title or "Meta-analysis idea validation", level=0)
    meta = doc.add_paragraph(f"Validation report · {today.isoformat()}")
    meta.runs[0].italic = True

    verdict = doc.add_paragraph()
    verdict.alignment = WD_ALIGN_PARAGRAPH.LEFT
    run = verdict.add_run(f"Decision: {a.verdict}")
    run.bold = True
    run.font.size = Pt(16)
    run.font.color.rgb = VERDICT_COLORS.get(a.verdict, RGBColor(0xA6, 0x6A, 0x00))
    for line in a.rationale:
        doc.add_paragraph(line, style="List Bullet")

    doc.add_heading("How we found this idea", level=1)
    if p.idea_sources:
        doc.add_paragraph("Sources: " + ", ".join(p.idea_sources))
    if p.idea_origin:
        doc.add_paragraph(p.idea_origin)

    doc.add_heading("Research question (PICOS)", level=1)
    _table(doc, ["Element", "Definition"], [
        ["Population", p.population], ["Intervention / exposure", p.intervention],
        ["Comparator", p.comparator], ["Outcomes", p.outcomes], ["Study designs", p.study_designs],
    ])

    doc.add_heading("Available original evidence", level=1)
    doc.add_paragraph(f"Independent eligible studies: {a.independent_studies} "
                      f"(feasibility: {a.feasibility}).")
    _table(doc, ["Study", "Year", "Design", "N", "Link / notes"], [
        [s.citation, str(s.year or ""), s.design, str(s.sample_size or ""),
         "\n".join(x for x in (s.link, ("Same cohort as: " + s.duplicate_of) if s.duplicate_of else "",
                               "" if s.eligible else "Not eligible", s.notes) if x)]
        for s in p.studies
    ])
    for key, label in FEASIBILITY_CHECKS.items():
        doc.add_paragraph(f"{'☑' if p.feasibility_checks.get(key) else '☐'} {label}")

    doc.add_heading("Timeliness and clinical importance", level=1)
    doc.add_paragraph(f"Priority signals: {a.timeliness_score} of {a.timeliness_max}.")
    for f in a.findings.get("Step 4 - Timeliness", []):
        doc.add_paragraph(f"{MARK[f.level]} {f.message}")

    doc.add_heading("Previous systematic reviews and meta-analyses", level=1)
    if p.reviews:
        _table(doc, ["Review", "Year", "Last search", "Overlap", "Scope / limitations"], [
            [r.title + (f"\n{r.link}" if r.link else ""), str(r.pub_year or ""), r.last_search_date or "Unknown",
             r.overlap, "\n".join(x for x in (r.population_comparison, r.included_studies, r.outcomes,
                                              r.rob_certainty, r.limitations) if x)]
            for r in p.reviews
        ])
        if a.latest_search_date:
            doc.add_paragraph(f"Latest search date of an overlapping review: {a.latest_search_date.isoformat()}. "
                              f"Eligible studies published after it: {len(a.new_since_search)}.")
    else:
        doc.add_paragraph("No previous review identified.")

    doc.add_heading("Evidence gap and expected contribution", level=1)
    claimed = [k for k in CONTRIBUTIONS if k in p.contributions]
    if claimed:
        for k in claimed:
            para = doc.add_paragraph(style="List Bullet")
            para.add_run(CONTRIBUTIONS[k] + ": ").bold = True
            para.add_run(p.contributions[k] or f"(Must demonstrate: {CONTRIBUTION_REQUIREMENTS[k]})")
    else:
        doc.add_paragraph("No contribution recorded.")
    for f in a.findings.get("Step 7 - Contribution", []):
        if f.level in ("warn", "fail"):
            doc.add_paragraph(f"{MARK[f.level]} {f.message}")

    if p.justification:
        doc.add_heading("Justification", level=1)
        doc.add_paragraph(p.justification)

    if p.search_log:
        doc.add_heading("PubMed searches", level=1)
        for entry in p.search_log:
            doc.add_paragraph(f"{entry.get('label', '')}: {entry.get('count', '')} — {entry.get('query', '')}",
                              style="List Bullet")

    doc.add_heading("Open items", level=1)
    open_items = [f.message for fs in a.findings.values() for f in fs if f.level in ("warn", "fail")]
    for item in open_items or ["None."]:
        doc.add_paragraph(item, style="List Bullet")

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
