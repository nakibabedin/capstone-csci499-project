import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import app


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.original = {key: app.config[key] for key in
                         ("TESTING", "UPLOAD_FOLDER", "MAX_CONTENT_LENGTH")}
        app.config.update(TESTING=True, UPLOAD_FOLDER=self.folder.name,
                          MAX_CONTENT_LENGTH=10 * 1024 * 1024)
        self.client = app.test_client()

    def tearDown(self):
        app.config.update(self.original)
        self.folder.cleanup()

    def upload(self, content=b"%PDF-1.4\nsynthetic test fixture", name="report.pdf"):
        return self.client.post("/api/upload", data={
            "file": (io.BytesIO(content), name)})

    def test_missing_file(self):
        self.assertEqual(self.client.post("/api/upload").status_code, 400)

    def test_empty_filename(self):
        self.assertEqual(self.upload(name="").status_code, 400)

    def test_wrong_extension(self):
        self.assertEqual(self.upload(name="report.txt").status_code, 400)

    def test_empty_or_disguised_pdf(self):
        for content in (b"", b"this is not a PDF"):
            with self.subTest(content=content):
                self.assertEqual(self.upload(content=content).status_code, 400)
        self.assertEqual(list(Path(self.folder.name).iterdir()), [])

    def test_saved_bytes_unique_names_and_safe_filename(self):
        content = b"%PDF-1.4\nsynthetic test fixture"
        first = self.upload(content, "../../report.PDF")
        second = self.upload(content, "../../report.PDF")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json["filename"], "report.PDF")
        self.assertNotEqual(first.json["upload_id"], second.json["upload_id"])
        saved = Path(self.folder.name) / (first.json["upload_id"] + ".pdf")
        self.assertEqual(saved.read_bytes(), content)
        self.assertEqual(first.json["size"], len(content))
        self.assertEqual(first.json["status"], "uploaded")

    def test_oversized_request_returns_json(self):
        app.config["MAX_CONTENT_LENGTH"] = 1024
        response = self.upload(b"%PDF-" + b"x" * 1024)
        self.assertEqual(response.status_code, 413)
        self.assertIn("error", response.json)
        self.assertEqual(list(Path(self.folder.name).iterdir()), [])

    def test_storage_error_returns_json(self):
        with patch("app.Path.mkdir", side_effect=OSError("test storage failure")):
            response = self.upload()
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json, {"error": "Could not save the uploaded file"})


if __name__ == "__main__":
    unittest.main()
