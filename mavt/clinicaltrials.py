"""ClinicalTrials.gov v2 API lookup for completed interventional trials (Step 1 / Step 4 signal)."""

from __future__ import annotations

from dataclasses import dataclass

import requests

API = "https://clinicaltrials.gov/api/v2/studies"


@dataclass
class Trial:
    nct_id: str
    title: str
    status: str
    completion_date: str
    has_results: bool
    enrollment: int | None
    phases: list[str]

    @property
    def link(self) -> str:
        return f"https://clinicaltrials.gov/study/{self.nct_id}"


def search_trials(term: str, status: str = "COMPLETED", interventional_only: bool = True,
                  page_size: int = 25, session: requests.Session | None = None) -> tuple[int, list[Trial]]:
    """Search ClinicalTrials.gov. `term` is free text (e.g. 'thrombectomy AND stroke')."""
    params = {
        "query.term": term,
        "countTotal": "true",
        "pageSize": page_size,
        "sort": "LastUpdatePostDate:desc",
    }
    if status:
        params["filter.overallStatus"] = status
    if interventional_only:
        params["filter.advanced"] = "AREA[StudyType]INTERVENTIONAL"
    resp = (session or requests).get(API, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    trials = []
    for s in data.get("studies", []):
        proto = s.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        stat = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        trials.append(Trial(
            nct_id=ident.get("nctId", ""),
            title=ident.get("briefTitle", ""),
            status=stat.get("overallStatus", ""),
            completion_date=(stat.get("completionDateStruct") or {}).get("date", ""),
            has_results=bool(s.get("hasResults")),
            enrollment=(design.get("enrollmentInfo") or {}).get("count"),
            phases=list(design.get("phases", [])),
        ))
    return int(data.get("totalCount", len(trials))), trials
