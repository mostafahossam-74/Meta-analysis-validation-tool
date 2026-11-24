"""Streamlit app: Meta-analysis Validation Tool.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import json
import re
from datetime import date

import pandas as pd
import requests
import streamlit as st

from mavt import clinicaltrials, pubmed
from mavt.example import thrombectomy_example
from mavt.models import (CONTRIBUTION_REQUIREMENTS, CONTRIBUTIONS, FEASIBILITY_CHECKS, IDEA_SOURCES,
                         REVIEW_OVERLAP, STUDY_DESIGNS, PriorReview, Project, Study)
from mavt.report import build_report
from mavt.scoring import DEFER, DUPLICATE, PROCEED, assess

st.set_page_config(page_title="Meta-analysis Validation Tool", page_icon="🔎", layout="wide")

STUDY_COLS = ["citation", "link", "year", "pub_date", "design", "sample_size", "duplicate_of", "eligible", "notes"]
REVIEW_COLS = ["title", "link", "pub_year", "last_search_date", "overlap", "population_comparison",
               "included_studies", "outcomes", "rob_certainty", "limitations"]


# ---------------------------------------------------------------- state helpers
def load_project(p: Project) -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("w_"):
            del st.session_state[key]
    st.session_state.project = p
    st.session_state.studies_df = _studies_df(p.studies)
    st.session_state.reviews_df = _reviews_df(p.reviews)
    st.session_state.editor_ver = st.session_state.get("editor_ver", 0) + 1
    st.session_state.pop("snapshot", None)
    st.session_state.pop("trials", None)


def _studies_df(studies: list[Study]) -> pd.DataFrame:
    df = pd.DataFrame([s.__dict__ for s in studies], columns=STUDY_COLS)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["sample_size"] = pd.to_numeric(df["sample_size"], errors="coerce").astype("Int64")
    df["eligible"] = df["eligible"].fillna(True).astype(bool)
    for c in ("citation", "link", "pub_date", "design", "duplicate_of", "notes"):
        df[c] = df[c].fillna("").astype(str)
    return df


def _reviews_df(reviews: list[PriorReview]) -> pd.DataFrame:
    df = pd.DataFrame([r.__dict__ for r in reviews], columns=REVIEW_COLS)
    df["pub_year"] = pd.to_numeric(df["pub_year"], errors="coerce").astype("Int64")
    for c in REVIEW_COLS:
        if c != "pub_year":
            df[c] = df[c].fillna("").astype(str)
    return df


def _clean(v):
    if v is None or (isinstance(v, float) and pd.isna(v)) or v is pd.NA:
        return None
    if hasattr(v, "item"):
        return v.item()
    return v


def _rows(df: pd.DataFrame) -> list[dict]:
    rows = []
    for rec in df.to_dict("records"):
        rec = {k: _clean(v) for k, v in rec.items()}
        if any(rec.get(k) for k in ("citation", "title", "link")):
            rows.append(rec)
    return rows


def _append_rows(df_key: str, new_rows: list[dict], current: pd.DataFrame, builder) -> None:
    existing_links = set(current["link"].astype(str))
    new_rows = [r for r in new_rows if r["link"] not in existing_links]
    if not new_rows:
        return
    merged = pd.concat([current, builder(new_rows)], ignore_index=True)
    st.session_state[df_key] = merged
    st.session_state.editor_ver += 1


if "project" not in st.session_state:
    load_project(Project())

p: Project = st.session_state.project
TODAY = date.today()

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Project")
    if st.button("Load Thrombectomy example", width="stretch"):
        load_project(thrombectomy_example())
        st.rerun()
    if st.button("Start a new idea", width="stretch"):
        load_project(Project())
        st.rerun()
    uploaded = st.file_uploader("Open saved project (.json)", type="json")
    if uploaded is not None and st.session_state.get("loaded_file") != uploaded.file_id:
        st.session_state.loaded_file = uploaded.file_id
        load_project(Project.from_dict(json.load(uploaded)))
        st.rerun()
    st.divider()
    st.caption("PubMed settings")
    api_key = st.text_input("NCBI API key (optional)", type="password",
                            help="Raises the PubMed rate limit from 3 to 10 requests/second. "
                                 "Can also be set with the NCBI_API_KEY environment variable.")

client = pubmed.PubMedClient(api_key=api_key or None)

st.title("Meta-analysis Validation Tool")
st.caption("Work through the validation pathway: is the idea feasible, timely, and a meaningful contribution?")

tabs = st.tabs(["1 · Idea", "2 · Scope", "3 · Evidence", "4 · Timeliness", "5–6 · Prior reviews",
                "7 · Contribution", "8–9 · Decision & report"])

# ---------------------------------------------------------------- Step 1
with tabs[0]:
    st.subheader("Step 1. Generate candidate ideas")
    p.title = st.text_input("Working title", p.title, key="w_title",
                            placeholder="Efficacy and Safety of Alteplase in Acute Ischemic Stroke")
    p.idea_sources = st.multiselect("Where did the idea come from?", IDEA_SOURCES,
                                    default=[s for s in p.idea_sources if s in IDEA_SOURCES], key="w_sources")
    p.idea_origin = st.text_area("How we found this idea", p.idea_origin, height=140, key="w_origin")
    st.info("Use these sources to generate candidates; verify claims and references against the original "
            "sources. A registered trial without results signals future evidence but does not yet supply "
            "data for pooling.")

# ---------------------------------------------------------------- Step 2
with tabs[1]:
    st.subheader("Step 2. Define the preliminary scope")
    c1, c2 = st.columns(2)
    p.population = c1.text_area("Population", p.population, key="w_pop")
    p.intervention = c2.text_area("Intervention or exposure", p.intervention, key="w_int")
    p.comparator = c1.text_area("Comparator", p.comparator, key="w_comp")
    p.outcomes = c2.text_area("Main outcome(s)", p.outcomes, key="w_out")
    st.markdown("**Search concepts** — one concept per line, synonyms separated by `;`. "
                "Lines are combined with AND, synonyms with OR.")
    p.search_concepts = st.text_area("Search concepts", p.search_concepts, height=110, key="w_concepts",
                                     label_visibility="collapsed",
                                     placeholder="alteplase; tPA; tissue plasminogen activator\n"
                                                 "ischemic stroke; ischaemic stroke")
    if p.search_concepts.strip():
        st.code(pubmed.build_query(p.search_concepts), language=None)

# ---------------------------------------------------------------- Step 3
with tabs[2]:
    st.subheader("Step 3. Check whether enough relevant original evidence exists")
    if st.button("Run PubMed searches", type="primary", disabled=not p.search_concepts.strip()):
        try:
            with st.spinner("Searching PubMed…"):
                snap = pubmed.evidence_snapshot(client, p.search_concepts, today=TODAY.year)
            st.session_state.snapshot = snap
            p.search_log = [
                {"label": "Original studies (all years)", "count": snap.original_total, "query": snap.query},
                {"label": f"Original studies {TODAY.year - 1}–{TODAY.year}", "count": snap.original_last_two_years,
                 "query": snap.query},
                {"label": f"Original studies {TODAY.year}", "count": snap.original_current_year, "query": snap.query},
                {"label": "RCTs", "count": snap.rct_total, "query": f"({snap.query}) AND {pubmed.RCT_FILTER}"},
                {"label": "SR/MA (PubMed filter)", "count": snap.reviews_filter,
                 "query": f"({snap.query}) AND {pubmed.SR_MA_FILTER}"},
                {"label": "SR/MA (explicit terms)", "count": snap.reviews_text,
                 "query": f"({snap.query}) AND {pubmed.SR_MA_TEXT}"},
            ]
        except (requests.RequestException, ValueError) as exc:
            st.error(f"PubMed search failed: {exc}")

    snap = st.session_state.get("snapshot")
    if snap:
        m = st.columns(4)
        m[0].metric("Original studies", snap.original_total)
        m[1].metric(f"Since {TODAY.year - 1}", snap.original_last_two_years)
        m[2].metric(f"In {TODAY.year}", snap.original_current_year)
        m[3].metric("RCT-tagged", snap.rct_total)
        if snap.recent_original:
            st.markdown("**Recent original studies** — tick the ones worth screening to add them below.")
            pick = pd.DataFrame([{"add": False, "title": a.title, "journal": a.journal, "date": a.pub_date,
                                  "link": a.link} for a in snap.recent_original])
            picked = st.data_editor(pick, hide_index=True, key="w_pick_studies", width="stretch",
                                    column_config={"link": st.column_config.LinkColumn()},
                                    disabled=["title", "journal", "date", "link"])
            if st.button("Add ticked studies"):
                rows = [{"citation": r["title"], "link": r["link"], "year": int(r["date"][:4]) if r["date"][:4].isdigit() else None,
                         "pub_date": r["date"], "design": "Other", "eligible": True,
                         "notes": "Added from PubMed; screen full text."}
                        for r in picked.to_dict("records") if r["add"]]
                _append_rows("studies_df", rows, st.session_state.studies_df,
                             lambda rs: _studies_df([Study(**r) for r in rs]))
                st.rerun()

    st.markdown("**Potentially eligible independent studies** (target: at least 3–4). "
                "Fill *duplicate_of* when a report shares a trial or cohort with another study.")
    edited = st.data_editor(
        st.session_state.studies_df, num_rows="dynamic", width="stretch",
        key=f"studies_editor_{st.session_state.editor_ver}",
        column_config={
            "link": st.column_config.LinkColumn(),
            "design": st.column_config.SelectboxColumn(options=STUDY_DESIGNS),
            "year": st.column_config.NumberColumn(format="%d", min_value=1900, max_value=2100),
            "pub_date": st.column_config.TextColumn(help="YYYY-MM-DD, if known"),
            "eligible": st.column_config.CheckboxColumn(default=True),
        })
    p.studies = [Study(**r) for r in _rows(edited)]
    st.session_state.studies_current = edited

    st.markdown("**Verify**")
    for key, label in FEASIBILITY_CHECKS.items():
        p.feasibility_checks[key] = st.checkbox(label, p.feasibility_checks.get(key, False), key=f"w_fc_{key}")

# ---------------------------------------------------------------- Step 4
with tabs[3]:
    st.subheader("Step 4. Assess timeliness and clinical importance")
    st.caption("Priority indicators, not mandatory eligibility criteria.")
    p.new_rcts_reporting = st.checkbox("New RCTs are reporting results", p.new_rcts_reporting, key="w_rcts")
    p.ongoing_debate = st.checkbox("Guidelines or clinical practice continue to debate the question",
                                   p.ongoing_debate, key="w_debate")
    p.clinical_decision_impact = st.checkbox("The answer could influence a meaningful clinical decision",
                                             p.clinical_decision_impact, key="w_impact")

    st.markdown("**ClinicalTrials.gov — completed interventional trials**")
    default_term = " AND ".join(line.split(";")[0].strip() for line in p.search_concepts.splitlines() if line.strip())
    c1, c2 = st.columns([3, 1])
    ct_term = c1.text_input("Search term", default_term, key="w_ct_term")
    ct_status = c2.selectbox("Status", ["COMPLETED", "RECRUITING", "ACTIVE_NOT_RECRUITING", ""], key="w_ct_status")
    if st.button("Search ClinicalTrials.gov", disabled=not ct_term.strip()):
        try:
            with st.spinner("Searching ClinicalTrials.gov…"):
                st.session_state.trials = clinicaltrials.search_trials(ct_term, status=ct_status)
        except requests.RequestException as exc:
            st.error(f"ClinicalTrials.gov search failed: {exc}")
    if st.session_state.get("trials"):
        total, trials = st.session_state.trials
        with_results = sum(t.has_results for t in trials)
        st.write(f"{total} trial(s) found; {with_results} of the {len(trials)} shown have posted results.")
        st.dataframe(pd.DataFrame([{"NCT": t.nct_id, "title": t.title, "status": t.status,
                                    "completion": t.completion_date, "results": t.has_results,
                                    "enrollment": t.enrollment, "link": t.link} for t in trials]),
                     hide_index=True, width="stretch",
                     column_config={"link": st.column_config.LinkColumn()})

# ---------------------------------------------------------------- Steps 5-6
with tabs[4]:
    st.subheader("Steps 5–6. Search for previous reviews and examine what they covered")
    snap = st.session_state.get("snapshot")
    if snap:
        st.write(f"PubMed SR/MA filter: **{snap.reviews_filter}** hits · explicit-term search: "
                 f"**{snap.reviews_text}** hits. Also check the Cochrane Library and Google Scholar.")
        if snap.reviews:
            pick = pd.DataFrame([{"add": False, "title": a.title, "journal": a.journal, "date": a.pub_date,
                                  "link": a.link} for a in snap.reviews])
            picked = st.data_editor(pick, hide_index=True, key="w_pick_reviews", width="stretch",
                                    column_config={"link": st.column_config.LinkColumn()},
                                    disabled=["title", "journal", "date", "link"])
            if st.button("Add ticked reviews"):
                rows = [{"title": r["title"], "link": r["link"],
                         "pub_year": int(r["date"][:4]) if r["date"][:4].isdigit() else None,
                         "overlap": "Overlapping question"}
                        for r in picked.to_dict("records") if r["add"]]
                _append_rows("reviews_df", rows, st.session_state.reviews_df,
                             lambda rs: _reviews_df([PriorReview(**r) for r in rs]))
                st.rerun()
    else:
        st.caption("Run the PubMed searches in Step 3 to list candidate reviews here.")

    st.markdown("**Previous reviews** — record the *last literature-search date*, not the publication date. "
                "A similar title does not mean an identical question.")
    edited_r = st.data_editor(
        st.session_state.reviews_df, num_rows="dynamic", width="stretch",
        key=f"reviews_editor_{st.session_state.editor_ver}",
        column_config={
            "link": st.column_config.LinkColumn(),
            "overlap": st.column_config.SelectboxColumn(options=REVIEW_OVERLAP),
            "pub_year": st.column_config.NumberColumn(format="%d"),
            "last_search_date": st.column_config.TextColumn(help="YYYY-MM-DD"),
        })
    p.reviews = [PriorReview(**r) for r in _rows(edited_r)]
    bad = [r.title for r in p.reviews if r.last_search_date and not r.search_date_value]
    if bad:
        st.warning("Use YYYY-MM-DD for last search dates: " + "; ".join(bad))
    missing = [r.title for r in p.reviews if r.overlap != "Different question" and not r.last_search_date]
    if missing:
        st.warning("Last search date missing for overlapping review(s): " + "; ".join(missing))

# ---------------------------------------------------------------- Step 7
with tabs[5]:
    st.subheader("Step 7. Identify a meaningful contribution")
    a = assess(p, TODAY)
    if a.latest_search_date:
        st.write(f"Latest search date of an overlapping review: **{a.latest_search_date}**. "
                 f"Eligible studies in your list published after it: **{len(a.new_since_search)}**.")
        if p.search_concepts.strip() and st.button("Count PubMed studies published after this date"):
            try:
                n, arts = pubmed.studies_after(client, p.search_concepts, a.latest_search_date.isoformat())
                st.write(f"{n} original studies in PubMed since {a.latest_search_date}.")
                st.dataframe(pd.DataFrame([{"title": x.title, "date": x.pub_date, "link": x.link} for x in arts]),
                             hide_index=True, width="stretch",
                             column_config={"link": st.column_config.LinkColumn()})
            except requests.RequestException as exc:
                st.error(f"PubMed search failed: {exc}")
    for key, label in CONTRIBUTIONS.items():
        on = st.checkbox(label, key in p.contributions, key=f"w_cb_{key}")
        if on:
            p.contributions[key] = st.text_area(f"Justify: {CONTRIBUTION_REQUIREMENTS[key]}",
                                                p.contributions.get(key, ""), key=f"w_ct_{key}")
        else:
            p.contributions.pop(key, None)
    st.caption("Additional analyses should answer a question, not merely add novelty. Meta-regression is "
               "generally not recommended with fewer than ten studies. TSA should not automatically qualify "
               "an otherwise duplicative review.")

# ---------------------------------------------------------------- Steps 8-9
with tabs[6]:
    a = assess(p, TODAY)
    st.subheader("Step 8. Decision")
    box = {PROCEED: st.success, DEFER: st.error, DUPLICATE: st.error}.get(a.verdict, st.warning)
    box(f"**{a.verdict}**\n\n" + "\n".join(f"- {r}" for r in a.rationale))
    m = st.columns(3)
    m[0].metric("Independent eligible studies", a.independent_studies)
    m[1].metric("Feasibility", a.feasibility.capitalize())
    m[2].metric("Priority signals", f"{a.timeliness_score}/{a.timeliness_max}")
    icons = {"ok": "✅", "warn": "⚠️", "fail": "❌", "info": "ℹ️"}
    for section, findings in a.findings.items():
        with st.expander(section, expanded=any(f.level in ("warn", "fail") for f in findings)):
            for f in findings:
                st.write(f"{icons[f.level]} {f.message}")

    st.subheader("Step 9. Research question (PICOS) and justification")
    st.caption("P, I, C and O are edited in Step 2. Finalize outcomes there with their assessment times.")
    st.markdown("\n".join(f"- **{k}:** {v or '—'}" for k, v in (
        ("P — Population", p.population), ("I — Intervention / exposure", p.intervention),
        ("C — Comparator", p.comparator), ("O — Outcomes", p.outcomes))))
    p.study_designs = st.text_input("S — Eligible study designs", p.study_designs, key="w_designs")
    p.justification = st.text_area(
        "Brief justification (clinical problem, previous review's search date, candidate studies, exact gap, "
        "expected contribution)", p.justification, height=150, key="w_just")

    slug = re.sub(r"[^A-Za-z0-9]+", "_", p.title or "validation").strip("_")[:60] or "validation"
    c1, c2 = st.columns(2)
    c1.download_button("Download Word report", build_report(p, a, TODAY), file_name=f"{slug}_validation.docx",
                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       type="primary", width="stretch")
    c2.download_button("Save project (.json)", json.dumps(p.to_dict(), indent=2), file_name=f"{slug}.json",
                       mime="application/json", width="stretch")
