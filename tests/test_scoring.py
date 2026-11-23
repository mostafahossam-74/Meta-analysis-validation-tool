from datetime import date

from mavt.example import thrombectomy_example
from mavt.models import FEASIBILITY_CHECKS, PriorReview, Project, Study
from mavt.scoring import DEFER, DUPLICATE, PROCEED, REFINE, assess

TODAY = date(2026, 11, 23)


def feasible_project(**kw) -> Project:
    p = Project(
        studies=[Study(f"S{i}", year=2026, design="RCT") for i in range(4)],
        feasibility_checks={k: True for k in FEASIBILITY_CHECKS},
        clinical_decision_impact=True,
    )
    for k, v in kw.items():
        setattr(p, k, v)
    return p


def test_too_few_studies_defers():
    p = feasible_project(studies=[Study("A", year=2026), Study("B", year=2026)])
    assert assess(p, TODAY).verdict == DEFER


def test_overlapping_cohorts_not_counted():
    studies = [Study("A", year=2026), Study("B", year=2026), Study("C", year=2026, duplicate_of="A")]
    a = assess(feasible_project(studies=studies), TODAY)
    assert a.independent_studies == 2
    assert a.verdict == DEFER


def test_unverified_checks_refine():
    p = feasible_project(feasibility_checks={})
    a = assess(p, TODAY)
    assert a.feasibility == "uncertain"
    assert a.verdict == REFINE


def test_no_prior_review_proceeds():
    assert assess(feasible_project(), TODAY).verdict == PROCEED


def test_same_question_with_only_tsa_is_duplicate():
    p = feasible_project(
        reviews=[PriorReview("Old MA", last_search_date="2026-06-01", overlap="Same question")],
        contributions={"tsa": "Check whether the evidence is conclusive."},
    )
    a = assess(p, TODAY)
    assert a.verdict == DUPLICATE
    assert any("do not justify" in r for r in a.rationale)


def test_new_studies_after_search_date_proceed():
    p = feasible_project(
        reviews=[PriorReview("Old MA", last_search_date="2025-02-28", overlap="Same question")],
        contributions={"several_new_studies": "Four new studies since Feb 2025."},
    )
    a = assess(p, TODAY)
    assert a.verdict == PROCEED
    assert len(a.new_since_search) == 4
    assert a.latest_search_date == date(2025, 2, 28)


def test_several_new_studies_claim_checked_against_dates():
    p = feasible_project(
        studies=[Study(f"S{i}", year=2020) for i in range(4)],
        reviews=[PriorReview("Old MA", last_search_date="2025-02-28", overlap="Same question")],
        contributions={"several_new_studies": "Claimed."},
    )
    a = assess(p, TODAY)
    msgs = [f.message for f in a.findings["Step 7 - Contribution"]]
    assert any("fewer than 3" in m for m in msgs)
    assert any("more than two years old" in f.message for f in a.findings["Step 4 - Timeliness"])


def test_meta_regression_warning_under_ten_studies():
    a = assess(feasible_project(contributions={"meta_regression": "Dose."}), TODAY)
    assert any("fewer than 10" in f.message for f in a.findings["Step 7 - Contribution"])


def test_different_question_review_ignored_for_search_date():
    p = feasible_project(reviews=[PriorReview("Other", last_search_date="2026-10-01",
                                              overlap="Different question")])
    assert assess(p, TODAY).latest_search_date is None


def test_timeliness_signals():
    p = feasible_project(ongoing_debate=True, new_rcts_reporting=True)
    a = assess(p, TODAY)
    assert a.timeliness_score == 5


def test_thrombectomy_example():
    p = thrombectomy_example()
    a = assess(p, TODAY)
    assert a.independent_studies == 6
    assert a.latest_search_date == date(2025, 2, 28)
    assert len(a.new_since_search) == 6
    # Full-text checks are still unticked in the example, so it is a Refine until verified.
    assert a.verdict == REFINE
    p.feasibility_checks = {k: True for k in FEASIBILITY_CHECKS}
    assert assess(p, TODAY).verdict == PROCEED


def test_project_roundtrip():
    p = thrombectomy_example()
    assert Project.from_dict(p.to_dict()) == p
