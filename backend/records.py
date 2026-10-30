"""Saved reports shown on each user's dashboard.

Anyone can upload, parse and analyze a report; saving it needs a login.

Temporary storage: one JSON file per user in RECORDS_FOLDER, plus a copy of
each saved PDF in RECORDS_FOLDER/pdfs, until the data moves to the Supabase
`reports` and `biomarker_results` tables (see app.py). The record fields follow
those tables so the move is mostly a storage swap.

Routes (all require login):
  POST   /api/records           save an uploaded report: {"upload_id", "filename", "results"?}
  GET    /api/records           the user's saved reports, newest first (summaries)
  GET    /api/records/<id>      one saved report, with its full parsed document
  GET    /api/records/<id>/pdf  the original PDF
  DELETE /api/records/<id>      remove a saved report and its PDF
"""

import json
import os
import re
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, g, jsonify, request, send_file
from werkzeug.utils import secure_filename

from analysis import available_analyses
from auth import require_auth
from lab_parser import parse_lab_report
from reports import MAX_PAGES, UPLOAD_ID_RE, recompute
from status import result_status

RECORD_ID_RE = re.compile(r"^[0-9a-f]{32}$")
USER_ID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")

records_bp = Blueprint("records", __name__, url_prefix="/api")
_lock = threading.Lock()


# --- Storage ---

def _records_folder():
    return Path(current_app.config["RECORDS_FOLDER"])


def _pdf_path(record_id):
    return _records_folder() / "pdfs" / f"{record_id}.pdf"


def _user_file(user_id):
    # Supabase user IDs are UUIDs; anything else could escape the folder.
    if not USER_ID_RE.match(str(user_id)):
        raise ValueError("Unexpected user ID")
    return _records_folder() / f"{user_id}.json"


def _load(user_id):
    path = _user_file(user_id)
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save(user_id, records):
    path = _user_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write to a temporary file first so a crash can't leave half a file.
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(records, f)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _summary_counts(results):
    counts = {"tests": 0, "in_range": 0, "out_of_range": 0, "no_range": 0}
    for r in results:
        if r.get("derived"):
            continue
        counts["tests"] += 1
        status = result_status(r)
        if status == "normal":
            counts["in_range"] += 1
        elif status == "unknown":
            counts["no_range"] += 1
        else:
            counts["out_of_range"] += 1
    return counts


def _build_record(user_id, upload_id, filename, document, num_pages, confirmed_results):
    report_date = document.get("report_date") or {}
    record = {
        "id": uuid4().hex,
        "user_id": user_id,
        "upload_id": upload_id,
        "original_filename": filename,
        "test_date": report_date.get("iso"),
        "report_date": document.get("report_date"),
        "num_pages": num_pages,
        "status": "parsed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "panels": [
            {"id": p["id"], "name": p["name"], "status": p["status"]}
            for p in document.get("panels", [])
        ],
        "document": document,
        # Results after the user reviewed and corrected them, if they did.
        "confirmed_results": None,
        "confirmed_analyses": None,
    }
    if confirmed_results is not None:
        record["status"] = "reviewed"
        record["confirmed_results"] = confirmed_results
        record["confirmed_analyses"] = available_analyses(confirmed_results)
    record["stored_filename"] = f"pdfs/{record['id']}.pdf"
    record["summary"] = _summary_counts(confirmed_results or document.get("results", []))
    return record


def _without_document(record):
    hidden = ("document", "confirmed_results", "confirmed_analyses")
    return {k: v for k, v in record.items() if k not in hidden}


def _find(record_id):
    """The signed-in user's record with this ID, or None."""
    if not RECORD_ID_RE.match(record_id):
        return None
    return next((r for r in _load(g.auth_user["id"]) if r["id"] == record_id), None)


# --- Routes ---

@records_bp.route("/records", methods=["POST"])
@require_auth
def save_record():
    body = request.get_json(silent=True) or {}
    upload_id = body.get("upload_id")
    if not isinstance(upload_id, str) or not UPLOAD_ID_RE.match(upload_id):
        return jsonify({"error": "Invalid upload ID"}), 400
    upload = Path(current_app.config["UPLOAD_FOLDER"]) / f"{upload_id}.pdf"
    if not upload.is_file():
        return jsonify({"error": "This upload is no longer available. Please upload the report again."}), 404

    confirmed = None
    if body.get("results") is not None:
        confirmed = recompute(body["results"])
        if not confirmed:
            return jsonify({"error": "Results are malformed."}), 400

    user_id = g.auth_user["id"]
    filename = secure_filename(str(body.get("filename") or "")) or "report.pdf"

    # Saving the same upload twice returns the existing record.
    existing = next((r for r in _load(user_id) if r["upload_id"] == upload_id), None)
    if existing is not None:
        return jsonify({"record": _without_document(existing)}), 200

    # Parsed again here rather than trusting a document sent by the browser.
    try:
        document, num_pages = parse_lab_report(upload.read_bytes(), MAX_PAGES)
    except Exception as e:
        return jsonify({"error": f"Failed to parse PDF: {e}"}), 400
    if document is None:
        return jsonify({"error": "No text found in PDF (it may be a scanned image)."}), 400

    record = _build_record(user_id, upload_id, filename, document, num_pages, confirmed)
    pdf = _pdf_path(record["id"])
    try:
        pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(upload, pdf)
        with _lock:
            records = _load(user_id)
            # Checked again: another request may have saved it meanwhile.
            existing = next((r for r in records if r["upload_id"] == upload_id), None)
            if existing is not None:
                pdf.unlink(missing_ok=True)
                return jsonify({"record": _without_document(existing)}), 200
            records.append(record)
            _save(user_id, records)
    except (OSError, ValueError):
        current_app.logger.exception("Could not save record for upload %s", upload_id)
        pdf.unlink(missing_ok=True)
        return jsonify({"error": "Could not save the report"}), 500

    return jsonify({"record": _without_document(record)}), 201


@records_bp.route("/records", methods=["GET"])
@require_auth
def list_records():
    records = sorted(_load(g.auth_user["id"]), key=lambda r: r["created_at"], reverse=True)
    return jsonify({"records": [_without_document(r) for r in records]})


@records_bp.route("/records/<record_id>", methods=["GET"])
@require_auth
def get_record(record_id):
    record = _find(record_id)
    if record is None:
        return jsonify({"error": "Report not found"}), 404
    return jsonify({"record": record})


@records_bp.route("/records/<record_id>/pdf", methods=["GET"])
@require_auth
def get_record_pdf(record_id):
    record = _find(record_id)
    if record is None:
        return jsonify({"error": "Report not found"}), 404
    path = _pdf_path(record["id"])
    if not path.is_file():
        return jsonify({"error": "The original PDF is no longer stored"}), 404
    return send_file(path, mimetype="application/pdf", download_name=record["original_filename"])


@records_bp.route("/records/<record_id>", methods=["DELETE"])
@require_auth
def delete_record(record_id):
    if not RECORD_ID_RE.match(record_id):
        return jsonify({"error": "Report not found"}), 404
    user_id = g.auth_user["id"]
    with _lock:
        records = _load(user_id)
        if not any(r["id"] == record_id for r in records):
            return jsonify({"error": "Report not found"}), 404
        _save(user_id, [r for r in records if r["id"] != record_id])
    try:
        _pdf_path(record_id).unlink(missing_ok=True)
    except OSError:
        current_app.logger.exception("Could not delete PDF for record %s", record_id)
    return jsonify({"deleted": record_id})
