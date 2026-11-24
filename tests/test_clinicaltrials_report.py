import io
from datetime import date

from docx import Document

from mavt import clinicaltrials
from mavt.example import thrombectomy_example
from mavt.report import build_report
from mavt.scoring import assess


class FakeSession:
    def get(self, url, params, timeout):
        self.params = params

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"totalCount": 7, "studies": [{
                    "hasResults": True,
                    "protocolSection": {
                        "identificationModule": {"nctId": "NCT01234567", "briefTitle": "Late EVT trial"},
                        "statusModule": {"overallStatus": "COMPLETED", "completionDateStruct": {"date": "2025-06"}},
                        "designModule": {"enrollmentInfo": {"count": 300}, "phases": ["PHASE3"]},
                    }}]}
        return R()


def test_trials_parse():
    s = FakeSession()
    total, trials = clinicaltrials.search_trials("thrombectomy", session=s)
    assert total == 7
    t = trials[0]
    assert (t.nct_id, t.has_results, t.enrollment) == ("NCT01234567", True, 300)
    assert t.link.endswith("NCT01234567")
    assert s.params["filter.overallStatus"] == "COMPLETED"


def test_report_contains_key_sections():
    p = thrombectomy_example()
    today = date(2026, 11, 23)
    data = build_report(p, assess(p, today), today)
    doc = Document(io.BytesIO(data))
    text = "\n".join(par.text for par in doc.paragraphs)
    for needle in ("Decision: Refine", "How we found this idea", "Previous systematic reviews",
                   "2025-02-28", "Several new studies", "Open items"):
        assert needle in text, needle
    table_text = " ".join(c.text for t in doc.tables for r in t.rows for c in r.cells)
    assert "S1878875025002992" in table_text
