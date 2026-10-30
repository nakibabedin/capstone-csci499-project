import io
from unittest.mock import Mock

import fitz
import pytest
import requests

from app import app

AUTH_HEADERS = {"Authorization": "Bearer test-token"}  # accepted by conftest.py
REPORT_LINES = [
    "Date Collected: 01/21/2025",
    "Hemoglobin 13.5 g/dL 12.0 - 15.5",
    "Glucose 130 mg/dL 70 - 99",
]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setitem(app.config, "TESTING", True)
    monkeypatch.setitem(app.config, "UPLOAD_FOLDER", tmp_path / "uploads")
    monkeypatch.setitem(app.config, "RECORDS_FOLDER", tmp_path / "records")
    return app.test_client()


def make_pdf(lines):
    doc = fitz.open()
    page = doc.new_page()
    for i, line in enumerate(lines):
        page.insert_text((72, 72 + 14 * i), line)
    return doc.tobytes()


def upload_and_parse(client):
    """Upload and parse without logging in, as a visitor would."""
    res = client.post("/api/upload", data={"file": (io.BytesIO(make_pdf(REPORT_LINES)), "report.pdf")})
    assert res.status_code == 201
    upload_id = res.json["upload_id"]
    res = client.post(f"/api/uploads/{upload_id}/parse")
    assert res.status_code == 200
    return upload_id, res.json["document"]


def save(client, upload_id, filename="my report.pdf", **extra):
    return client.post("/api/records", headers=AUTH_HEADERS,
                       json={"upload_id": upload_id, "filename": filename, **extra})


def test_parsing_does_not_save(client):
    upload_and_parse(client)
    assert client.get("/api/records", headers=AUTH_HEADERS).json["records"] == []


def test_save_adds_record_to_dashboard(client):
    upload_id, document = upload_and_parse(client)
    res = save(client, upload_id)
    assert res.status_code == 201
    saved = res.json["record"]

    records = client.get("/api/records", headers=AUTH_HEADERS).json["records"]
    assert [r["id"] for r in records] == [saved["id"]]
    record = records[0]
    assert record["original_filename"] == "my_report.pdf"
    assert record["test_date"] == "2025-01-21"
    assert record["report_date"]["label"] == "Collected"
    assert record["status"] == "parsed"
    assert record["summary"] == {"tests": 2, "in_range": 1, "out_of_range": 1, "no_range": 0}
    assert "document" not in record  # the list stays small

    full = client.get(f"/api/records/{record['id']}", headers=AUTH_HEADERS).json["record"]
    assert full["document"]["results"] == document["results"]
    assert full["confirmed_results"] is None


def test_save_keeps_corrected_results(client):
    upload_id, document = upload_and_parse(client)
    corrected = [dict(r) for r in document["results"] if not r.get("derived")]
    glucose = next(r for r in corrected if r["canonical"] == "Glucose")
    glucose.update(value=85, value_text="85", flag=None)

    record = save(client, upload_id, results=corrected).json["record"]
    assert record["status"] == "reviewed"
    assert record["summary"]["in_range"] == 2

    full = client.get(f"/api/records/{record['id']}", headers=AUTH_HEADERS).json["record"]
    saved_glucose = next(r for r in full["confirmed_results"] if r["canonical"] == "Glucose")
    assert saved_glucose["value"] == 85
    assert full["confirmed_analyses"] is not None


def test_saving_twice_returns_the_same_record(client):
    upload_id, _ = upload_and_parse(client)
    first = save(client, upload_id).json["record"]["id"]
    res = save(client, upload_id)
    assert res.status_code == 200
    assert res.json["record"]["id"] == first
    assert len(client.get("/api/records", headers=AUTH_HEADERS).json["records"]) == 1


def test_records_newest_first(client):
    first = save(client, upload_and_parse(client)[0], "first.pdf").json["record"]["id"]
    second = save(client, upload_and_parse(client)[0], "second.pdf").json["record"]["id"]
    records = client.get("/api/records", headers=AUTH_HEADERS).json["records"]
    assert [r["id"] for r in records] == [second, first]


def test_record_pdf_is_the_original(client):
    record_id = save(client, upload_and_parse(client)[0]).json["record"]["id"]
    res = client.get(f"/api/records/{record_id}/pdf", headers=AUTH_HEADERS)
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"
    assert res.data.startswith(b"%PDF-")


def test_delete_record_removes_it_and_its_pdf(client):
    record_id = save(client, upload_and_parse(client)[0]).json["record"]["id"]
    assert client.delete(f"/api/records/{record_id}", headers=AUTH_HEADERS).status_code == 200
    assert client.get("/api/records", headers=AUTH_HEADERS).json["records"] == []
    assert client.get(f"/api/records/{record_id}/pdf", headers=AUTH_HEADERS).status_code == 404
    assert list((app.config["RECORDS_FOLDER"] / "pdfs").iterdir()) == []


def test_users_only_see_their_own_records(client, monkeypatch):
    record_id = save(client, upload_and_parse(client)[0]).json["record"]["id"]

    other = Mock(status_code=200, ok=True)
    other.json.return_value = {"id": "22222222-2222-2222-2222-222222222222"}
    monkeypatch.setattr(requests, "get", Mock(return_value=other))

    assert client.get("/api/records", headers=AUTH_HEADERS).json["records"] == []
    for method in (client.get, client.delete):
        assert method(f"/api/records/{record_id}", headers=AUTH_HEADERS).status_code == 404
    assert client.get(f"/api/records/{record_id}/pdf", headers=AUTH_HEADERS).status_code == 404


def test_saving_and_records_require_login(client):
    upload_id, _ = upload_and_parse(client)
    assert client.post("/api/records", json={"upload_id": upload_id}).status_code == 401
    assert client.get("/api/records").status_code == 401


@pytest.mark.parametrize("body, status", [
    ({}, 400),
    ({"upload_id": "../../secret"}, 400),
    ({"upload_id": "0" * 32}, 404),
])
def test_save_rejects_bad_uploads(client, body, status):
    assert client.post("/api/records", headers=AUTH_HEADERS, json=body).status_code == status


def test_save_rejects_malformed_results(client):
    upload_id, _ = upload_and_parse(client)
    assert save(client, upload_id, results="nope").status_code == 400


@pytest.mark.parametrize("record_id", ["not-hex", "..%2F..%2Fsecret"])
def test_malformed_record_id(client, record_id):
    assert client.get(f"/api/records/{record_id}", headers=AUTH_HEADERS).status_code == 404
