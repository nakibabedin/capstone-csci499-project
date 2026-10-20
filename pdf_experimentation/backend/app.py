import time

import ollama
from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS

from lab_parser import parse_lab_report
from summarizer import OLLAMA_MODEL, stream_summary

MAX_PAGES = 20

app = Flask(__name__)
CORS(app)


@app.route("/upload", methods=["POST"])
def upload_pdf():
    file = request.files.get("file")
    if file is None or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF file."}), 400

    try:
        start = time.perf_counter()
        report, num_pages = parse_lab_report(file.read(), MAX_PAGES)
        done = time.perf_counter()
    except Exception as e:
        return jsonify({"error": f"Failed to parse PDF: {e}"}), 400

    if report is None:
        return jsonify({"error": "No text found in PDF (it may be a scanned image)."}), 400

    print(
        f"Parsed {file.filename}: {num_pages} pages, {len(report['results'])} results "
        f"in {(done - start) * 1000:.0f}ms",
        flush=True,
    )
    return jsonify({"document": report})


@app.route("/summarize", methods=["POST"])
def summarize():
    results = (request.get_json(silent=True) or {}).get("results")
    if not results:
        return jsonify({"error": "No results to summarize."}), 400

    try:
        chunks = stream_summary(results)
    except ConnectionError:
        return jsonify({"error": "Could not reach Ollama. Is `ollama serve` running?"}), 503
    except ollama.ResponseError as e:
        if e.status_code == 404:
            return jsonify({"error": f"Model not found. Run `ollama pull {OLLAMA_MODEL}`."}), 503
        return jsonify({"error": f"Summary failed: {e.error}"}), 500

    return Response(stream_with_context(chunks), mimetype="text/plain")


if __name__ == "__main__":
    app.run(debug=True, port=5002)
