import io

import fitz
import pytest

from app import app

AUTH_HEADERS = {"Authorization": "Bearer test-token"}  # accepted by conftest.py


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "UPLOAD_FOLDER", tmp_path)
    monkeypatch.setitem(app.config, "RECORDS_FOLDER", tmp_path / "records")
    return app.test_client()


def make_pdf(lines):
    doc = fitz.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + 14 * i), line)
    return doc.tobytes()


def upload(client, content):
    res = client.post("/api/upload", headers=AUTH_HEADERS, data={"file": (io.BytesIO(content), "report.pdf")})
    assert res.status_code == 201
    return res.json["upload_id"]


def test_parse_uploaded_report(client):
    upload_id = upload(client, make_pdf(["Hemoglobin 13.5 g/dL 12.0 - 15.5"]))
    res = client.post(f"/api/uploads/{upload_id}/parse", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert {"results", "biomarkers", "panels", "analyses", "unparsed"} <= res.json["document"].keys()


def test_rejects_malformed_upload_id(client):
    assert client.post("/api/uploads/..%2Fsecret/parse", headers=AUTH_HEADERS).status_code in (400, 404)
    assert client.post("/api/uploads/not-hex/parse", headers=AUTH_HEADERS).status_code == 400


def test_unknown_upload_id(client):
    assert client.post(f"/api/uploads/{'0' * 32}/parse", headers=AUTH_HEADERS).status_code == 404


def test_pdf_without_text(client):
    upload_id = upload(client, make_pdf([]))
    res = client.post(f"/api/uploads/{upload_id}/parse", headers=AUTH_HEADERS)
    assert res.status_code == 400
    assert "No text found" in res.json["error"]


def test_unreadable_pdf(client):
    upload_id = upload(client, b"%PDF-1.4\nsynthetic test fixture")
    res = client.post(f"/api/uploads/{upload_id}/parse", headers=AUTH_HEADERS)
    assert res.status_code == 400
    assert "error" in res.json


def test_analyze_recomputes_from_corrected_results(client):
    results = [{"test": "TSH", "canonical": "TSH", "value": 2.5, "value_text": "2.5", "unit": "uIU/mL"},
               {"test": "Free T4", "canonical": "Free T4", "value": 1.3, "value_text": "1.3", "unit": "ng/dL"}]
    res = client.post("/api/analyze", json={"results": results})
    assert res.status_code == 200
    [thyroid] = res.json["analyses"]
    assert thyroid["id"] == "thyroid" and thyroid["inputs"]["values"]["TSH"] == 2.5


@pytest.mark.parametrize("body", [{}, {"results": []}, {"results": "TSH"}, {"results": [1, 2]}])
def test_analyze_rejects_missing_or_malformed_results(client, body):
    assert client.post("/api/analyze", json=body).status_code == 400


def test_panel_summary_errors(client):
    tsh = [{"test": "TSH", "canonical": "TSH", "value": 2.5, "value_text": "2.5", "unit": "uIU/mL"}]
    assert client.post("/api/panels/not-a-panel/summarize", json={"results": tsh}).status_code == 404
    assert client.post("/api/panels/thyroid/summarize", json={}).status_code == 400
    # TSH alone says nothing about the lipid panel.
    assert client.post("/api/panels/lipid/summarize", json={"results": tsh}).status_code == 400


def test_panel_summary_streams_only_that_panels_results(client, monkeypatch):
    seen = {}

    def fake_stream(analysis, results):
        seen.update(panel=analysis["id"], tests=[r["canonical"] for r in results])
        return iter(["TSH is ", "in range."])

    monkeypatch.setattr("reports.stream_panel_summary", fake_stream)
    results = [{"test": "TSH", "canonical": "TSH", "value": 2.5, "value_text": "2.5", "unit": "uIU/mL", "ref_low": 0.4, "ref_high": 4.0},
               {"test": "Glucose", "canonical": "Glucose", "value": 90, "value_text": "90", "unit": "mg/dL"}]
    res = client.post("/api/panels/thyroid/summarize", json={"results": results})
    assert res.status_code == 200 and res.get_data(as_text=True) == "TSH is in range."
    assert seen == {"panel": "thyroid", "tests": ["TSH"]}
