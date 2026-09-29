import io
import json
import os
import time

import ollama
import pdfplumber
from flask import Flask, jsonify, request
from flask_cors import CORS

MAX_PAGES = 20
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5vl:7b")
# Large enough to fit MAX_PAGES of typical text plus the model's response.
OLLAMA_NUM_CTX = int(os.environ.get("OLLAMA_NUM_CTX", "16384"))

DOCUMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "heading": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["heading", "content"],
            },
        },
    },
    "required": ["title", "sections"],
}

SYSTEM_PROMPT = (
    "You convert raw text extracted from a PDF into a structured document. "
    "Identify the document title and split the text into its sections, using the "
    "document's own headings. Keep section content faithful to the source text: "
    "fix broken line wraps and hyphenation, but do not summarize, add, or omit content."
)

app = Flask(__name__)
CORS(app)

llm = ollama.Client()


def extract_text(contents):
    with pdfplumber.open(io.BytesIO(contents)) as pdf:
        pages = pdf.pages[:MAX_PAGES]
        return "\n\n".join(page.extract_text() or "" for page in pages), len(pages)


def structure_text(text):
    response = llm.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        format=DOCUMENT_SCHEMA,
        options={"temperature": 0, "num_ctx": OLLAMA_NUM_CTX},
    )
    return json.loads(response.message.content)


@app.route("/upload", methods=["POST"])
def upload_pdf():
    file = request.files.get("file")
    if file is None or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF file."}), 400

    try:
        start = time.perf_counter()
        text, num_pages = extract_text(file.read())
        extracted = time.perf_counter()
    except Exception as e:
        return jsonify({"error": f"Failed to parse PDF: {e}"}), 400

    if not text.strip():
        return jsonify({"error": "No text found in PDF (it may be a scanned image)."}), 400

    try:
        document = structure_text(text)
    except ConnectionError:
        return jsonify({"error": "Could not reach Ollama. Is `ollama serve` running?"}), 503
    except Exception as e:
        return jsonify({"error": f"LLM failed to structure the document: {e}"}), 500

    done = time.perf_counter()
    print(
        f"Parsed {file.filename}: {num_pages} pages, "
        f"extract {extracted - start:.1f}s, LLM {done - extracted:.1f}s",
        flush=True,
    )
    return jsonify({"document": document})


if __name__ == "__main__":
    app.run(debug=True, port=5002)
