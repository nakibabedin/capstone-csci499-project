import re
import time
from pathlib import Path

import ollama
from flask import Blueprint, Response, current_app, jsonify, request, stream_with_context

from lab_parser import parse_lab_report
from summarizer import OLLAMA_MODEL, stream_summary

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


# --- Stream a plain-language summary from Ollama ---

@reports_bp.route("/summarize", methods=["POST"])
def summarize():
    body = request.get_json(silent=True) or {}
    results = body.get("results")
    if not results:
        return jsonify({"error": "No results to summarize."}), 400

    try:
        chunks = stream_summary(results, body.get("panels") or [])
    except ConnectionError:
        return jsonify({"error": "Could not reach Ollama. Is `ollama serve` running?"}), 503
    except ollama.ResponseError as e:
        if e.status_code == 404:
            return jsonify({"error": f"Model not found. Run `ollama pull {OLLAMA_MODEL}`."}), 503
        return jsonify({"error": f"Summary failed: {e.error}"}), 500

    return Response(stream_with_context(chunks), mimetype="text/plain")
