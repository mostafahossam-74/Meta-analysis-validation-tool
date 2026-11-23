"""Worked example: thrombectomy beyond 24 hours (from the team's Thrombectomy validation write-up).

Dates, designs and sample sizes not stated in the write-up are left blank or marked
"to verify" rather than guessed.
"""

from .models import FEASIBILITY_CHECKS, PriorReview, Project, Study

TO_VERIFY = "Design, date and sample size to verify from full text."


def thrombectomy_example() -> Project:
    return Project(
        title="Endovascular Thrombectomy Beyond 24 Hours in Acute Ischemic Stroke",
        idea_sources=["Social media / news", "Exploratory PubMed search"],
        idea_origin=(
            "By mapping the literature and neurology news we found two papers published in 2026 comparing "
            "thrombectomy before vs after 24 hours. Searching PubMed for thrombectomy and 24 hours with the "
            "systematic review / meta-analysis filter showed that the strongest meta-analysis compared EVT "
            "with best medical treatment (BMT), not timing, leaving a gap."
        ),
        population="Adults with acute ischemic stroke due to large vessel occlusion",
        intervention="Endovascular thrombectomy (EVT) performed more than 24 hours after last known well",
        comparator="(1) EVT within 24 hours; (2) best medical treatment (BMT) beyond 24 hours",
        outcomes="Functional independence (mRS 0-2) at 90 days; symptomatic ICH; mortality at 90 days; "
                 "successful reperfusion",
        study_designs="RCTs and comparative cohort studies (single-arm studies excluded)",
        search_concepts="thrombectomy; endovascular therapy; endovascular treatment\n"
                        "24 hours; late window; very late window; beyond 24 hours",
        studies=[
            Study("SVIN 2026 study (before vs after 24 h EVT)",
                  "https://www.ahajournals.org/doi/10.1161/SVIN.125.002024", 2026, notes=TO_VERIFY),
            Study("J Clin Neurosci 2026 study (before vs after 24 h EVT)",
                  "https://www.sciencedirect.com/science/article/pii/S0967586826003954", 2026, notes=TO_VERIFY),
            Study("PMID 41985838 (EVT vs BMT beyond 24 h)",
                  "https://pubmed.ncbi.nlm.nih.gov/41985838/", 2026, notes=TO_VERIFY),
            Study("PMID 41601320", "https://pubmed.ncbi.nlm.nih.gov/41601320/", 2026, notes=TO_VERIFY),
            Study("PMID 41573189", "https://pubmed.ncbi.nlm.nih.gov/41573189/", 2026, notes=TO_VERIFY),
            Study("PMID 42263905", "https://pubmed.ncbi.nlm.nih.gov/42263905/", 2026, notes=TO_VERIFY),
        ],
        feasibility_checks={k: False for k in FEASIBILITY_CHECKS},
        ongoing_debate=True,
        new_rcts_reporting=False,
        clinical_decision_impact=True,
        reviews=[
            PriorReview(
                title="Stroke 2025 meta-analysis: EVT vs BMT beyond 24 hours (strongest prior review)",
                link="https://www.ahajournals.org/doi/10.1161/STROKEAHA.125.052121",
                pub_year=2025, overlap="Overlapping question",
                population_comparison="EVT vs BMT; does not compare before vs after 24 hours",
            ),
            PriorReview(
                title="Clin Neurol Neurosurg 2024 meta-analysis: before vs after 24 hours",
                link="https://www.sciencedirect.com/science/article/pii/S0303846724004979",
                pub_year=2024, overlap="Overlapping question",
                population_comparison="EVT before vs after 24 hours",
                included_studies="Mainly single-arm studies",
                limitations="Relied mainly on single-arm studies that did not provide the timing comparison; "
                            "search ran only to 2024.",
            ),
            PriorReview(title="2023 meta-analysis (timing comparison)",
                        link="https://pubmed.ncbi.nlm.nih.gov/37355251/", pub_year=2023,
                        overlap="Overlapping question", population_comparison="EVT timing comparison"),
            PriorReview(title="2023 meta-analysis (EVT vs BMT)",
                        link="https://pubmed.ncbi.nlm.nih.gov/38964022/", pub_year=2023,
                        overlap="Overlapping question", population_comparison="EVT vs BMT"),
            PriorReview(
                title="World Neurosurg 2025 meta-analysis: both comparisons",
                link="https://www.sciencedirect.com/science/article/pii/S1878875025002992",
                pub_year=2025, last_search_date="2025-02-28", overlap="Same question",
                population_comparison="Both: before vs after 24 h, and EVT vs BMT",
                limitations="Search to February 2025 (exact day to verify); many studies published since.",
            ),
        ],
        contributions={
            "several_new_studies": "At least six eligible studies were published in 2026, after the latest "
                                   "prior search (February 2025), which could improve precision and certainty "
                                   "for both comparisons.",
            "prior_limitation": "The 2024 review relied mainly on single-arm studies that did not provide the "
                                "before vs after 24 h comparison; restricting to comparative studies addresses "
                                "this.",
        },
    )
