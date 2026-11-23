"""Small client for NCBI E-utilities (PubMed) used for feasibility, timeliness and prior-review searches."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TOOL_NAME = "meta-analysis-validation-tool"

# Step 5: PubMed's systematic review subset plus the meta-analysis publication type.
SR_MA_FILTER = "(systematic[sb] OR meta-analysis[pt])"
# Step 5.3: explicit terms, to reduce dependence on indexing.
SR_MA_TEXT = '("systematic review"[tiab] OR "meta-analysis"[tiab] OR "meta-analyses"[tiab])'
RCT_FILTER = "(randomized controlled trial[pt] OR randomised[tiab] OR randomized[tiab])"
# Exclude reviews when counting original studies.
EXCLUDE_REVIEWS = "NOT (review[pt] OR systematic[sb] OR meta-analysis[pt])"


def build_query(concepts: str) -> str:
    """Turn concept lines into a boolean query.

    Each non-empty line is a concept; synonyms on a line are separated by ';' and ORed.
    Concepts are ANDed. Terms already containing a field tag ([...]) are kept as written;
    multi-word terms are quoted.
    """
    groups = []
    for line in concepts.splitlines():
        terms = [t.strip() for t in line.split(";") if t.strip()]
        if not terms:
            continue
        rendered = [t if "[" in t or t.startswith('"') or " " not in t else f'"{t}"' for t in terms]
        groups.append(rendered[0] if len(rendered) == 1 else "(" + " OR ".join(rendered) + ")")
    return " AND ".join(groups)


@dataclass
class Article:
    pmid: str
    title: str
    journal: str
    pub_date: str
    year: int | None
    pub_types: list[str]

    @property
    def link(self) -> str:
        return f"https://pubmed.ncbi.nlm.nih.gov/{self.pmid}/"


class PubMedClient:
    def __init__(self, api_key: str | None = None, session: requests.Session | None = None,
                 email: str | None = None):
        self.api_key = api_key if api_key is not None else os.environ.get("NCBI_API_KEY")
        self.email = email if email is not None else os.environ.get("NCBI_EMAIL")
        self.session = session or requests.Session()
        # NCBI allows 3 requests/s without a key, 10/s with one.
        self._min_interval = 0.11 if self.api_key else 0.34
        self._last = 0.0

    def _get(self, endpoint: str, params: dict) -> dict:
        params = {**params, "retmode": "json", "tool": TOOL_NAME}
        if self.api_key:
            params["api_key"] = self.api_key
        if self.email:
            params["email"] = self.email
        wait = self._min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        resp = self.session.get(f"{EUTILS}/{endpoint}", params=params, timeout=30)
        self._last = time.monotonic()
        resp.raise_for_status()
        return resp.json()

    def search(self, term: str, retmax: int = 0, mindate: str | None = None,
               maxdate: str | None = None, sort: str = "pub_date") -> tuple[int, list[str]]:
        """Return (total count, first `retmax` PMIDs). Dates are YYYY or YYYY/MM/DD (publication date)."""
        params = {"db": "pubmed", "term": term, "retmax": retmax, "sort": sort}
        if mindate or maxdate:
            params.update(datetype="pdat", mindate=mindate or "1800", maxdate=maxdate or "3000")
        data = self._get("esearch.fcgi", params)["esearchresult"]
        return int(data.get("count", 0)), list(data.get("idlist", []))

    def count(self, term: str, mindate: str | None = None, maxdate: str | None = None) -> int:
        return self.search(term, 0, mindate, maxdate)[0]

    def summaries(self, pmids: list[str]) -> list[Article]:
        if not pmids:
            return []
        result = self._get("esummary.fcgi", {"db": "pubmed", "id": ",".join(pmids)})["result"]
        articles = []
        for pmid in result.get("uids", pmids):
            item = result.get(pmid, {})
            pub_date = item.get("sortpubdate") or item.get("pubdate", "")
            year = None
            if pub_date[:4].isdigit():
                year = int(pub_date[:4])
            articles.append(Article(
                pmid=pmid,
                title=item.get("title", ""),
                journal=item.get("fulljournalname") or item.get("source", ""),
                pub_date=pub_date[:10].replace("/", "-"),
                year=year,
                pub_types=list(item.get("pubtype", [])),
            ))
        return articles


@dataclass
class EvidenceSnapshot:
    """Counts used by Steps 3-5."""

    query: str
    original_total: int
    original_last_two_years: int
    original_current_year: int
    rct_total: int
    reviews_filter: int
    reviews_text: int
    recent_original: list[Article]
    reviews: list[Article]

    @property
    def recent_share(self) -> float:
        return self.original_last_two_years / self.original_total if self.original_total else 0.0


def evidence_snapshot(client: PubMedClient, concepts: str, today: int | None = None,
                      list_size: int = 20) -> EvidenceSnapshot:
    import datetime as _dt

    year = today or _dt.date.today().year
    query = build_query(concepts)
    if not query:
        raise ValueError("Enter at least one search concept.")
    original = f"({query}) {EXCLUDE_REVIEWS}"
    total = client.count(original)
    last_two = client.count(original, mindate=str(year - 1), maxdate=str(year))
    current = client.count(original, mindate=str(year), maxdate=str(year))
    rct = client.count(f"({query}) AND {RCT_FILTER} {EXCLUDE_REVIEWS}")
    rev_count, rev_ids = client.search(f"({query}) AND {SR_MA_FILTER}", retmax=list_size)
    rev_text = client.count(f"({query}) AND {SR_MA_TEXT}")
    _, recent_ids = client.search(original, retmax=list_size, mindate=str(year - 1), maxdate=str(year))
    return EvidenceSnapshot(
        query=query,
        original_total=total,
        original_last_two_years=last_two,
        original_current_year=current,
        rct_total=rct,
        reviews_filter=rev_count,
        reviews_text=rev_text,
        recent_original=client.summaries(recent_ids),
        reviews=client.summaries(rev_ids),
    )


def studies_after(client: PubMedClient, concepts: str, search_date: str, list_size: int = 50
                  ) -> tuple[int, list[Article]]:
    """Original studies published after a prior review's last search date (YYYY-MM-DD)."""
    query = f"({build_query(concepts)}) {EXCLUDE_REVIEWS}"
    count, ids = client.search(query, retmax=list_size, mindate=search_date.replace("-", "/"),
                               maxdate="3000")
    return count, client.summaries(ids)
