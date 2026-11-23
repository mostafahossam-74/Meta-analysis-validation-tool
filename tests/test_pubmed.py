from mavt import pubmed


class FakeResp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class FakeSession:
    def __init__(self):
        self.calls = []

    def get(self, url, params, timeout):
        self.calls.append((url, params))
        if url.endswith("esearch.fcgi"):
            count = 40 if params.get("mindate") else 100
            return FakeResp({"esearchresult": {"count": str(count), "idlist": ["111", "222"][: params["retmax"]]}})
        return FakeResp({"result": {
            "uids": ["111", "222"],
            "111": {"title": "Study one", "fulljournalname": "Stroke", "sortpubdate": "2026/03/01 00:00",
                    "pubtype": ["Journal Article"]},
            "222": {"title": "Study two", "source": "JNIS", "pubdate": "2025 Dec", "pubtype": []},
        }})


def test_build_query():
    q = pubmed.build_query("thrombectomy; endovascular therapy\n24 hours; late window\n\n")
    assert q == '(thrombectomy OR "endovascular therapy") AND ("24 hours" OR "late window")'
    assert pubmed.build_query('stroke[mh]') == "stroke[mh]"


def test_snapshot_uses_api_and_parses():
    s = FakeSession()
    client = pubmed.PubMedClient(api_key="k", session=s, email="")
    client._min_interval = 0
    snap = pubmed.evidence_snapshot(client, "thrombectomy\n24 hours", today=2026)
    assert snap.original_total == 100
    assert snap.original_last_two_years == 40
    assert snap.recent_share == 0.4
    assert snap.reviews[0].link == "https://pubmed.ncbi.nlm.nih.gov/111/"
    assert snap.reviews[0].pub_date == "2026-03-01" and snap.reviews[0].year == 2026
    assert snap.reviews[1].journal == "JNIS" and snap.reviews[1].year == 2025
    assert all(p["api_key"] == "k" and p["tool"] == pubmed.TOOL_NAME for _, p in s.calls)
    dated = [p for _, p in s.calls if p.get("mindate") == "2026"]
    assert dated and dated[0]["datetype"] == "pdat"


def test_studies_after_date_format():
    s = FakeSession()
    client = pubmed.PubMedClient(api_key="", session=s, email="")
    client._min_interval = 0
    n, arts = pubmed.studies_after(client, "thrombectomy", "2025-02-28")
    assert n == 40 and len(arts) == 2
    assert s.calls[0][1]["mindate"] == "2025/02/28"
