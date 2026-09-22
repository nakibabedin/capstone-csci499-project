import io

from flask import Flask, jsonify, request
from flask_cors import CORS
import pdfplumber

app = Flask(__name__)
CORS(app)


@app.route("/upload", methods=["POST"])
def upload_pdf():
    file = request.files.get("file")
    if file is None or not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Please upload a PDF file."}), 400

    try:
        contents = file.read()
        with pdfplumber.open(io.BytesIO(contents)) as pdf:
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
        print(f"--- Extracted text from {file.filename} ---\n{text}", flush=True)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": f"Failed to extract text: {e}"}), 400


if __name__ == "__main__":
    app.run(debug=True, port=5001)
