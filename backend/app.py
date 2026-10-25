from pathlib import Path
from uuid import uuid4

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    UPLOAD_FOLDER=Path(app.root_path) / "uploads",
)
CORS(app)


@app.errorhandler(413)
def upload_too_large(error):
    return jsonify({"error": "Request exceeds the 10 MiB upload limit"}), 413

# --- Mock data (in-memory; resets on restart) ---

items = [
    {"id": 1, "name": "First item", "description": "A sample item"},
    {"id": 2, "name": "Second item", "description": "Another sample item"},
    {"id": 3, "name": "Third item", "description": "Yet another sample item"},
]

users = [
    {"id": 1, "name": "Alice", "email": "alice@example.com"},
    {"id": 2, "name": "Bob", "email": "bob@example.com"},
]


# --- Health ---

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# --- Items ---

@app.route("/api/items", methods=["GET"])
def list_items():
    return jsonify(items)


@app.route("/api/items/<int:item_id>", methods=["GET"])
def get_item(item_id):
    item = next((i for i in items if i["id"] == item_id), None)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    return jsonify(item)


@app.route("/api/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "'name' is required"}), 400

    new_item = {
        "id": max((i["id"] for i in items), default=0) + 1,
        "name": data["name"],
        "description": data.get("description", ""),
    }
    items.append(new_item)
    return jsonify(new_item), 201


@app.route("/api/items/<int:item_id>", methods=["DELETE"])
def delete_item(item_id):
    item = next((i for i in items if i["id"] == item_id), None)
    if item is None:
        return jsonify({"error": "Item not found"}), 404
    items.remove(item)
    return jsonify({"deleted": item_id})


# --- Users ---

@app.route("/api/users", methods=["GET"])
def list_users():
    return jsonify(users)


# --- Upload (local storage; parsing and database integration come later) ---

@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if file is None or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    filename = secure_filename(file.filename)
    if not filename or Path(filename).suffix.lower() != ".pdf":
        return jsonify({"error": "Only PDF files are accepted"}), 400

    # Basic signature check only. The parser must check document readability.
    if file.stream.read(5) != b"%PDF-":
        return jsonify({"error": "File does not have a PDF header"}), 400
    file.stream.seek(0)

    upload_id = uuid4().hex
    upload_folder = Path(app.config["UPLOAD_FOLDER"])
    destination = upload_folder / f"{upload_id}.pdf"
    created = False
    try:
        upload_folder.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents an existing file from being overwritten.
        with destination.open("xb") as output:
            created = True
            file.save(output)
        size = destination.stat().st_size
    except OSError:
        app.logger.exception("Could not save upload %s", upload_id)
        # Only remove a file created by this request, never an existing file
        # that caused exclusive creation to fail.
        if created:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                app.logger.exception("Could not clean up upload %s", upload_id)
        return jsonify({"error": "Could not save the uploaded file"}), 500

    return jsonify({
        "upload_id": upload_id,
        "filename": filename,
        "size": size,
        "status": "uploaded",
        "message": "PDF saved locally; parsing is not implemented yet",
    }), 201


# --- Lab report parsing and summaries (see reports.py) ---

from reports import reports_bp  # noqa: E402

app.register_blueprint(reports_bp)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
