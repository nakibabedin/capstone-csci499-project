# CS499 Project

React + TypeScript frontend (Vite) and Flask backend.

## Backend (Flask, port 5001)

```sh
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Items and users are mock data held in memory and reset on restart. Uploads are saved locally:

| Method | Path               | Description                         |
| ------ | ------------------ | ----------------------------------- |
| GET    | `/api/health`      | Health check                        |
| GET    | `/api/items`       | List items                          |
| GET    | `/api/items/<id>`  | Get one item                        |
| POST   | `/api/items`       | Create item (`{name, description}`) |
| DELETE | `/api/items/<id>`  | Delete item                         |
| GET    | `/api/users`       | List users                          |
| POST   | `/api/upload`      | Save a PDF (multipart `file`)       |

### Upload milestone

`POST /api/upload` accepts a `.pdf` filename (case insensitive) and checks for
the `%PDF-` header. This is a basic format check, not full PDF validation or
biomarker parsing. The entire request, including multipart overhead, is limited
to 10 MiB. Missing files, other extensions, and missing PDF headers return JSON
errors with status 400; oversized requests return 413; storage failures return 500.

Accepted files are saved in `backend/uploads/` under a generated upload ID, so
duplicate original filenames do not overwrite each other. The directory is
excluded from Git. A successful response has status 201 and includes
`upload_id`, a sanitized `filename`, `size` in bytes, `status: "uploaded"`, and
`message`. Existing frontend response fields are retained.

If a storage operation fails after this request creates a file, the endpoint
attempts to remove that incomplete upload before returning 500. It preserves
any existing file that caused exclusive creation to fail. If cleanup itself
fails, the server logs that failure and still returns the JSON storage error.
This handles caught storage errors, not abrupt process termination or power loss.

Uploads survive server restarts, but there is no report metadata database,
parser, user ownership, or download endpoint yet. Use synthetic reports for
development. Parser readability checks and database integration are next steps.

Run the upload tests from the project root:

```sh
backend/venv/bin/python -m unittest discover -s backend -p 'test_*.py' -v
```

### Lab report parsing & summaries

The parser and summarizer live in `backend/reports.py` and the modules it imports:
`lab_parser`, `summarizer`, `biomarkers`, `panels` and `units`.

| Method | Path                            | Description                                               |
| ------ | ------------------------------- | --------------------------------------------------------- |
| POST   | `/api/uploads/<upload_id>/parse` | Parse a PDF saved by `/api/upload` into lab results        |
| POST   | `/api/summarize`                | Stream a plain-language summary (`{results, panels}`)     |

Summaries need a local [Ollama](https://ollama.com) server. The model can be
overridden with the `OLLAMA_MODEL` environment variable:

```sh
ollama serve
ollama pull qwen2.5vl:7b
```

Run all backend tests, including the upload tests, from `backend/`:

```sh
venv/bin/python -m pytest
```

To check panel detection against a hand-verified answer key, run this from the project root:

```sh
backend/venv/bin/python eval/score_panels.py /path/to/report.pdf eval/expected/sterling-accuris-sample.json
```

## Frontend (React + Vite, port 5173)

Requires Node `^20.19` or `>=22.12` (`nvm use` picks up `.nvmrc`).

```sh
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to the Flask server, so start the backend first. API helpers live in `frontend/src/api/client.ts`; pages are in `frontend/src/pages/`.
