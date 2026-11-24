"""Decision logic for Steps 3, 4, 7 and 8 of the validation pathway."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .models import ANALYSIS_ONLY, CONTRIBUTIONS, FEASIBILITY_CHECKS, Project, Study

PROCEED = "Proceed"
REFINE = "Refine"
DEFER = "Defer"
DUPLICATE = "Do not prioritize (duplicate review)"

MIN_STUDIES = 3
META_REGRESSION_MIN = 10


@dataclass
class Finding:
    level: str  # "ok", "warn", "fail", "info"
    message: str


@dataclass
class Assessment:
    verdict: str
    rationale: list[str]
    feasibility: str  # "adequate" | "uncertain" | "insufficient"
    independent_studies: int
    timeliness_score: int
    timeliness_max: int
    latest_search_date: date | None
    new_since_search: list[Study]
    findings: dict[str, list[Finding]] = field(default_factory=dict)


def independent_eligible(studies: list[Study]) -> list[Study]:
    """Eligible studies, collapsing those that share a trial or cohort with another study."""
    return [s for s in studies if s.eligible and not s.duplicate_of.strip()]


def assess_feasibility(p: Project) -> tuple[str, int, list[Finding]]:
    studies = independent_eligible(p.studies)
    n = len(studies)
    out: list[Finding] = []
    dupes = [s for s in p.studies if s.eligible and s.duplicate_of.strip()]
    if dupes:
        out.append(Finding("info", f"{len(dupes)} report(s) share a trial/cohort with another study and "
                                   "are not counted as independent."))
    unchecked = [label for key, label in FEASIBILITY_CHECKS.items() if not p.feasibility_checks.get(key)]
    if n >= MIN_STUDIES + 1:
        out.append(Finding("ok", f"{n} independent eligible studies (target 3-4)."))
    elif n == MIN_STUDIES:
        out.append(Finding("ok", f"{n} independent eligible studies, at the minimum target of 3-4."))
    else:
        out.append(Finding("fail", f"Only {n} independent eligible studies; target is at least 3-4."))
    for label in unchecked:
        out.append(Finding("warn", f"Not yet verified: {label}."))

    if n < MIN_STUDIES:
        status = "insufficient"
    elif unchecked:
        status = "uncertain"
    else:
        status = "adequate"
    return status, n, out


def assess_timeliness(p: Project, today: date | None = None) -> tuple[int, int, list[Finding]]:
    """Priority indicators from Step 4; not eligibility criteria."""
    today = today or date.today()
    studies = independent_eligible(p.studies)
    dated = [s for s in studies if s.date_value]
    out: list[Finding] = []
    score = 0

    recent = [s for s in dated if (today - s.date_value).days <= 730]
    if dated and len(recent) / len(dated) > 0.5:
        score += 1
        out.append(Finding("ok", f"Most eligible studies are recent ({len(recent)}/{len(dated)} within 2 years)."))
    elif dated:
        out.append(Finding("info", f"{len(recent)}/{len(dated)} eligible studies are within the last 2 years."))

    this_year = [s for s in dated if s.date_value.year == today.year]
    if len(this_year) >= 2:
        score += 1
        out.append(Finding("ok", f"{len(this_year)} studies published in {today.year}."))
    else:
        out.append(Finding("info", f"{len(this_year)} study/studies published in {today.year} (signal: 2 or more)."))

    for flag, label in ((p.new_rcts_reporting, "New RCTs are reporting results"),
                        (p.ongoing_debate, "Guidelines or clinical practice continue to debate the question"),
                        (p.clinical_decision_impact, "The answer could influence a meaningful clinical decision")):
        if flag:
            score += 1
            out.append(Finding("ok", label + "."))

    if dated:
        latest = max(s.date_value for s in dated)
        if (today - latest).days > 730:
            out.append(Finding("warn", "The latest study is more than two years old: ask whether the "
                                       "uncertainty still matters (do not reject automatically)."))
    return score, 5, out


def latest_relevant_search(p: Project) -> date | None:
    dates = [r.search_date_value for r in p.reviews
             if r.overlap != "Different question" and r.search_date_value]
    return max(dates) if dates else None


def assess_contribution(p: Project, n_studies: int, search_date: date | None
                        ) -> tuple[list[Study], list[str], list[Finding]]:
    new = [s for s in independent_eligible(p.studies)
           if search_date and s.date_value and s.date_value > search_date]
    claimed = [k for k, v in p.contributions.items() if k in CONTRIBUTIONS and v is not None]
    out: list[Finding] = []

    if search_date:
        out.append(Finding("info", f"Latest search date of an overlapping review: {search_date.isoformat()}. "
                                   f"{len(new)} eligible stud{'y' if len(new) == 1 else 'ies'} published after it."))
    if "several_new_studies" in claimed and len(new) < 3:
        out.append(Finding("warn", "'Several new studies' claimed, but fewer than 3 eligible studies are dated "
                                   "after the latest prior search."))
    if "important_new_rct" in claimed and not any(s.design == "RCT" for s in new):
        out.append(Finding("warn", "'One important new RCT' claimed, but no RCT is listed after the latest "
                                   "prior search."))
    if "meta_regression" in claimed and n_studies < META_REGRESSION_MIN:
        out.append(Finding("warn", f"Meta-regression is generally not recommended with fewer than "
                                   f"{META_REGRESSION_MIN} studies (you have {n_studies})."))
    if "tsa" in claimed:
        out.append(Finding("info", "TSA should not automatically qualify an otherwise duplicative review."))
    for k in claimed:
        if not (p.contributions.get(k) or "").strip():
            out.append(Finding("warn", f"'{CONTRIBUTIONS[k]}' has no written justification."))
    return new, claimed, out


def assess(p: Project, today: date | None = None) -> Assessment:
    feas, n, f_feas = assess_feasibility(p)
    t_score, t_max, f_time = assess_timeliness(p, today)
    search_date = latest_relevant_search(p)
    new, claimed, f_contrib = assess_contribution(p, n, search_date)

    same = [r for r in p.reviews if r.overlap == "Same question"]
    substantive = [k for k in claimed if k not in ANALYSIS_ONLY and (p.contributions.get(k) or "").strip()]
    rationale: list[str] = []

    if feas == "insufficient":
        verdict = DEFER
        rationale.append("The evidence cannot yet support the planned synthesis: defer, refine the question "
                         "for a clinical reason, or consider a systematic review without pooling.")
    elif same and not substantive:
        verdict = DUPLICATE
        rationale.append("An existing review answers the same question and no consequential new evidence "
                         "or gap has been justified.")
        if claimed:
            rationale.append("Additional analyses alone (subgroup, sensitivity, meta-regression, TSA) do not "
                             "justify repeating the review.")
    elif feas == "uncertain":
        verdict = REFINE
        rationale.append("Enough studies may exist, but eligibility or data availability still needs "
                         "full-text verification.")
    elif p.reviews and not substantive:
        verdict = REFINE
        rationale.append("Overlapping reviews exist; state the exact gap and expected contribution (Step 7).")
    elif not p.clinical_decision_impact:
        verdict = REFINE
        rationale.append("Confirm that the answer could influence a meaningful clinical decision.")
    else:
        verdict = PROCEED
        rationale.append("The evidence is suitable, the question matters clinically, and there is a "
                         "defensible contribution.")
        if substantive:
            rationale.append("Contribution: " + "; ".join(CONTRIBUTIONS[k] for k in substantive) + ".")
        if not p.reviews:
            rationale.append("No previous review was recorded; confirm with Cochrane, Google Scholar and "
                             "explicit-term searches.")

    return Assessment(
        verdict=verdict,
        rationale=rationale,
        feasibility=feas,
        independent_studies=n,
        timeliness_score=t_score,
        timeliness_max=t_max,
        latest_search_date=search_date,
        new_since_search=new,
        findings={"Step 3 - Feasibility": f_feas, "Step 4 - Timeliness": f_time,
                  "Step 7 - Contribution": f_contrib},
    )
