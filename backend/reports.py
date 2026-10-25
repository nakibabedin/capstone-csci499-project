import re
import time
from pathlib import Path

import ollama
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from analysis import available_analyses, report_models
from biomarkers import PANELS
from lab_parser import parse_lab_report
from panels import derive, enrich
from summarizer import OLLAMA_MODEL, stream_panel_summary

MAX_PAGES = 20
UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{32}$")

reports_bp = Blueprint("reports", __name__, url_prefix="/api")


# --- Parse a PDF previously saved by POST /api/upload ---

@reports_bp.route("/uploads/<upload_id>/parse", methods=["POST"])
def parse_upload(upload_id):
    # upload_id comes from uuid4().hex; anything else could escape the folder.
    if not UPLOAD_ID_RE.match(upload_id):
        return jsonify({"error": "Invalid upload ID"}), 400

    path = Path(current_app.config["UPLOAD_FOLDER"]) / f"{upload_id}.pdf"
    if not path.is_file():
        return jsonify({"error": "Upload not found"}), 404

    try:
        start = time.perf_counter()
        report, num_pages = parse_lab_report(path.read_bytes(), MAX_PAGES)
        done = time.perf_counter()
    except Exception as e:
        return jsonify({"error": f"Failed to parse PDF: {e}"}), 400

    if report is None:
        return jsonify({"error": "No text found in PDF (it may be a scanned image)."}), 400

    current_app.logger.info(
        "Parsed upload %s: %d pages, %d results in %.0fms",
        upload_id, num_pages, len(report["results"]), (done - start) * 1000,
    )
    return jsonify({"document": report})


# --- Re-analyze after the user corrects values ---

def _corrected_results():
    """The request's `results`, enriched and with derived values recomputed, or None if malformed."""
    results = (request.get_json(silent=True) or {}).get("results")
    if not isinstance(results, list) or not all(isinstance(r, dict) for r in results):
        return None
    # Derived values may be stale after a correction, so they're recomputed.
    return derive(enrich([r for r in results if not r.get("derived")]))


def _patient():
    """The request's `patient` age and sex, with anything missing or invalid as None."""
    patient = (request.get_json(silent=True) or {}).get("patient")
    patient = patient if isinstance(patient, dict) else {}
    age, sex = patient.get("age"), patient.get("sex")
    valid_age = isinstance(age, (int, float)) and not isinstance(age, bool) and 0 <= age <= 120
    return {"age": age if valid_age else None, "sex": sex if sex in ("male", "female") else None}


@reports_bp.route("/analyze", methods=["POST"])
def analyze():
    results = _corrected_results()
    if not results:
        return jsonify({"error": "No results to analyze."}), 400
    patient = _patient()
    return jsonify({"analyses": available_analyses(results, patient), "overall": report_models(results, patient)})


# --- Stream a plain-language summary of one panel from Ollama ---

@reports_bp.route("/panels/<panel_id>/summarize", methods=["POST"])
def summarize_panel(panel_id):
    if panel_id not in PANELS:
        return jsonify({"error": "Unknown panel."}), 404
    results = _corrected_results()
    if not results:
        return jsonify({"error": "No results to summarize."}), 400
    patient = _patient()
    analysis = next((a for a in available_analyses(results, patient) if a["id"] == panel_id), None)
    if analysis is None:
        return jsonify({"error": "Not enough of this panel's tests are in the report to summarize it."}), 400
    inputs = PANELS[panel_id]["inputs"]
    panel_results = [r for r in results if r.get("canonical") in inputs and not r.get("derived")]

    try:
        chunks = stream_panel_summary(analysis, panel_results, patient)
    except ConnectionError:
        return jsonify({"error": "Could not reach Ollama. Is `ollama serve` running?"}), 503
    except ollama.ResponseError as e:
        if e.status_code == 404:
            return jsonify({"error": f"Model not found. Run `ollama pull {OLLAMA_MODEL}`."}), 503
        return jsonify({"error": f"Summary failed: {e.error}"}), 500

    return Response(stream_with_context(chunks), mimetype="text/plain")
