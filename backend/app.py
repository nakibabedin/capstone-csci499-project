import os
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID
from werkzeug.utils import secure_filename



app = Flask(__name__)
app.config.update(
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    UPLOAD_FOLDER=Path(app.root_path) / "uploads",
    RECORDS_FOLDER=Path(app.root_path) / "records",
)
CORS(app)

# Load the database URL from backend/.env
load_dotenv(Path(__file__).resolve().parent / ".env")

# Local development without Supabase: login is skipped and database routes
# return 503. Never enable this in a deployed environment.
supabase_disabled = os.getenv("DISABLE_SUPABASE", "").lower() == "true"

database_url = os.getenv("DATABASE_URL")
supabase_url = os.getenv("SUPABASE_URL")
supabase_publishable_key = os.getenv("SUPABASE_PUBLISHABLE_KEY")

if supabase_disabled:
    app.logger.warning(
        "DISABLE_SUPABASE=true: login is skipped and the database is off"
    )
    # Placeholder so SQLAlchemy can initialise; nothing connects to it.
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
else:
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is missing from backend/.env "
            "(set DISABLE_SUPABASE=true to develop without it)"
        )
    if not supabase_url or not supabase_publishable_key:
        raise RuntimeError(
            "Supabase URL or publishable key is missing from backend/.env "
            "(set DISABLE_SUPABASE=true to develop without it)"
        )
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "connect_args": {"sslmode": "require"}
    }

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config.update(
    SUPABASE_DISABLED=supabase_disabled,
    SUPABASE_URL=supabase_url,
    SUPABASE_PUBLISHABLE_KEY=supabase_publishable_key,
)

db = SQLAlchemy(app)
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(UUID(as_uuid=True), primary_key=True)
    email = db.Column(db.Text, nullable=False, unique=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.text("now()"),
    )


class Report(db.Model):
    __tablename__ = "reports"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=db.text("gen_random_uuid()"),
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    original_filename = db.Column(db.Text, nullable=False)
    stored_filename = db.Column(db.Text, nullable=True)
    test_date = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.Text,
        nullable=False,
        server_default=db.text("'uploaded'"),
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.text("now()"),
    )


class Biomarker(db.Model):
    __tablename__ = "biomarkers"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.Text, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)


class BiomarkerResult(db.Model):
    __tablename__ = "biomarker_results"

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=db.text("gen_random_uuid()"),
    )
    report_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    biomarker_id = db.Column(
        db.BigInteger,
        db.ForeignKey("biomarkers.id"),
        nullable=False,
    )
    value = db.Column(db.Numeric, nullable=False)
    unit = db.Column(db.Text, nullable=True)
    reference_low = db.Column(db.Numeric, nullable=True)
    reference_high = db.Column(db.Numeric, nullable=True)
    flag = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        server_default=db.text("now()"),
    )


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

# --- Biomarkers ---

@app.route("/api/biomarkers", methods=["GET"])
def list_biomarkers():
    if app.config["SUPABASE_DISABLED"]:
        return jsonify({"error": "Database is off (DISABLE_SUPABASE=true)"}), 503

    biomarkers =Biomarker.query.order_by(Biomarker.name).all()

    return jsonify([
        {
            "id": biomarker.id,
            "name": biomarker.name,
            "description": biomarker.description,
        }
        for biomarker in biomarkers
    ])


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
        "message": "PDF saved; parse it with POST /api/uploads/<upload_id>/parse",
    }), 201


# --- Lab report parsing and summaries (see reports.py) ---

from reports import reports_bp  # noqa: E402

app.register_blueprint(reports_bp)

# --- Saved reports for the dashboard (see records.py) ---

from records import records_bp  # noqa: E402

app.register_blueprint(records_bp)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
