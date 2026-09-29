from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

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


# --- Upload (mock: accepts a file and reports its name/size) ---

@app.route("/api/upload", methods=["POST"])
def upload():
    file = request.files.get("file")
    if file is None or file.filename == "":
        return jsonify({"error": "No file provided"}), 400

    size = len(file.read())
    return jsonify({
        "filename": file.filename,
        "size": size,
        "message": "File received (mock endpoint, nothing was saved)",
    })


if __name__ == "__main__":
    app.run(debug=True, port=5001)
