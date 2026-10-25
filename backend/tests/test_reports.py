import io

import fitz
import pytest

from app import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "UPLOAD_FOLDER", tmp_path)
    return app.test_client()


def make_pdf(lines):
    doc = fitz.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + 14 * i), line)
    return doc.tobytes()


def upload(client, content):
    res = client.post("/api/upload", data={"file": (io.BytesIO(content), "report.pdf")})
    assert res.status_code == 201
    return res.json["upload_id"]


def test_parse_uploaded_report(client):
    upload_id = upload(client, make_pdf(["Hemoglobin 13.5 g/dL 12.0 - 15.5"]))
    res = client.post(f"/api/uploads/{upload_id}/parse")
    assert res.status_code == 200
    assert {"results", "biomarkers", "panels", "features", "unparsed"} <= res.json["document"].keys()


def test_rejects_malformed_upload_id(client):
    assert client.post("/api/uploads/..%2Fsecret/parse").status_code in (400, 404)
    assert client.post("/api/uploads/not-hex/parse").status_code == 400


def test_unknown_upload_id(client):
    assert client.post(f"/api/uploads/{'0' * 32}/parse").status_code == 404


def test_pdf_without_text(client):
    upload_id = upload(client, make_pdf([]))
    res = client.post(f"/api/uploads/{upload_id}/parse")
    assert res.status_code == 400
    assert "No text found" in res.json["error"]


def test_unreadable_pdf(client):
    upload_id = upload(client, b"%PDF-1.4\nsynthetic test fixture")
    res = client.post(f"/api/uploads/{upload_id}/parse")
    assert res.status_code == 400
    assert "error" in res.json


def test_summarize_requires_results(client):
    assert client.post("/api/summarize", json={}).status_code == 400
