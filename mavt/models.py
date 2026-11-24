"""Data model for one candidate meta-analysis idea, following the 9-step validation pathway."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from datetime import date
from typing import Any

STUDY_DESIGNS = [
    "RCT",
    "Prospective cohort",
    "Retrospective cohort",
    "Case-control",
    "Registry",
    "Single-arm",
    "Other",
]

REVIEW_OVERLAP = [
    "Same question",
    "Overlapping question",
    "Different question",
]

# Step 7: potential justifications and what must be demonstrated for each.
CONTRIBUTIONS: dict[str, str] = {
    "several_new_studies": "Several new studies",
    "important_new_rct": "One important new RCT",
    "omitted_outcome": "An important omitted outcome",
    "population_gap": "A relevant population or comparison gap",
    "prior_limitation": "A major limitation in the previous review",
    "subgroup": "Meaningful subgroup analysis",
    "sensitivity": "Meaningful sensitivity analysis",
    "meta_regression": "Meta-regression",
    "tsa": "Trial sequential analysis (TSA)",
}

CONTRIBUTION_REQUIREMENTS: dict[str, str] = {
    "several_new_studies": "Three or more new eligible studies could meaningfully improve precision, "
    "applicability, or certainty, or alter conclusions. The count alone is insufficient.",
    "important_new_rct": "Its size, quality, population, or results could materially affect the evidence.",
    "omitted_outcome": "The outcome matters clinically, and sufficient usable data exist.",
    "population_gap": "The new scope answers a distinct clinical question supported by available studies.",
    "prior_limitation": "Correcting it could change interpretation, for example, addressing overlapping "
    "cohorts or inappropriate pooling.",
    "subgroup": "A clinically justified effect-modification question can be investigated with adequate data.",
    "sensitivity": "A consequential assumption or decision can be tested for robustness.",
    "meta_regression": "A justified study-level explanation for variation can be investigated with "
    "sufficient studies and covariate data.",
    "tsa": "A specific question about accumulating evidence justifies it, with appropriate assumptions "
    "and expertise.",
}

# Contributions that add analyses only; they cannot on their own justify repeating a review.
ANALYSIS_ONLY = {"subgroup", "sensitivity", "meta_regression", "tsa"}

# Step 3 verification checklist.
FEASIBILITY_CHECKS: dict[str, str] = {
    "similar_populations": "Studies examine sufficiently similar populations and comparisons",
    "usable_common_outcome": "They report usable data for at least one common outcome",
    "alignable_outcomes": "Outcome definitions and follow-up periods can be meaningfully aligned",
    "no_overlap": "Multiple articles do not represent the same trial or overlapping patient cohorts",
    "appropriate_designs": "Designs are appropriate for the planned question and synthesis",
}

IDEA_SOURCES = [
    "Social media / news",
    "Clinical practice",
    "ClinicalTrials.gov",
    "Google / AI chatbots",
    "Exploratory PubMed search",
    "Guidelines / conference updates",
]


@dataclass
class Study:
    """A potentially eligible original study (Step 3) or a new study since the last review search."""

    citation: str = ""
    link: str = ""
    year: int | None = None
    pub_date: str = ""  # ISO date (YYYY-MM-DD) if known; used against prior reviews' search dates
    design: str = "Retrospective cohort"
    sample_size: int | None = None
    duplicate_of: str = ""  # citation of the study this one shares a trial / cohort with
    eligible: bool = True
    notes: str = ""

    @property
    def date_value(self) -> date | None:
        if self.pub_date:
            try:
                return date.fromisoformat(self.pub_date[:10])
            except ValueError:
                pass
        if self.year:
            return date(int(self.year), 1, 1)
        return None


@dataclass
class PriorReview:
    """An existing systematic review / meta-analysis (Steps 5-6)."""

    title: str = ""
    link: str = ""
    pub_year: int | None = None
    last_search_date: str = ""  # ISO date; the date that matters, not publication date
    overlap: str = "Overlapping question"
    population_comparison: str = ""
    included_studies: str = ""
    outcomes: str = ""
    rob_certainty: str = ""
    limitations: str = ""

    @property
    def search_date_value(self) -> date | None:
        if not self.last_search_date:
            return None
        try:
            return date.fromisoformat(self.last_search_date[:10])
        except ValueError:
            return None


@dataclass
class Project:
    # Step 1
    title: str = ""
    idea_sources: list[str] = field(default_factory=list)
    idea_origin: str = ""
    # Step 2 / 9 (PICOS)
    population: str = ""
    intervention: str = ""
    comparator: str = ""
    outcomes: str = ""
    study_designs: str = ""
    # Search concepts: each line is one concept, synonyms separated by ';'
    search_concepts: str = ""
    # Step 3
    studies: list[Study] = field(default_factory=list)
    feasibility_checks: dict[str, bool] = field(default_factory=dict)
    # Step 4
    ongoing_debate: bool = False
    new_rcts_reporting: bool = False
    clinical_decision_impact: bool = False
    # Step 6
    reviews: list[PriorReview] = field(default_factory=list)
    # Step 7
    contributions: dict[str, str] = field(default_factory=dict)  # key -> justification text
    # Step 9
    justification: str = ""
    # Cached search results (Steps 3-5)
    search_log: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Project":
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs["studies"] = [_build(Study, s) for s in data.get("studies", [])]
        kwargs["reviews"] = [_build(PriorReview, r) for r in data.get("reviews", [])]
        return cls(**kwargs)


def _build(cls, data: dict[str, Any]):
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})
