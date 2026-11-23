# Meta-analysis Validation Tool

A Streamlit app that walks a candidate meta-analysis idea through the team's 9-step validation pathway
and returns a **Proceed / Refine / Defer / Do not prioritize (duplicate)** decision with a Word report.

| Step | In the app |
|---|---|
| 1. Generate candidate ideas | Idea sources and "How we found this idea" notes |
| 2. Preliminary scope | PICO plus search concepts (synonyms per line), turned into a PubMed query |
| 3. Enough original evidence? | Live PubMed counts, add recent hits to a study table, flag overlapping cohorts, 5-point verification checklist (target ≥ 3–4 independent studies) |
| 4. Timeliness & importance | Recent-share and current-year signals, new RCTs, debate, clinical impact; ClinicalTrials.gov lookup |
| 5–6. Previous reviews | PubMed SR/MA filter + explicit-term search; review table with **last search date**, overlap, scope, limitations |
| 7. Meaningful contribution | Justification per contribution type, checked against the data (e.g. new studies after the latest search date, meta-regression with < 10 studies, TSA alone) |
| 8–9. Decision & PICOS | Verdict with rationale, final PICOS, justification, Word report and JSON project file |

Click **Load Thrombectomy example** in the sidebar to see the worked example (EVT beyond 24 hours).
It shows **Refine** until the full-text verification boxes in Step 3 are ticked.

## Run

```bash
pip install -r requirements.txt
streamlit run app.py
```

Optional: set `NCBI_API_KEY` (or paste it in the sidebar) to raise PubMed's rate limit from 3 to 10 requests/s.

## Test

```bash
pip install -r requirements-dev.txt
pytest
```

Tests mock PubMed and ClinicalTrials.gov, so they run offline.
