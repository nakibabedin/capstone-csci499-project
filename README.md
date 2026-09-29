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

Mock endpoints (in-memory data, resets on restart):

| Method | Path               | Description                         |
| ------ | ------------------ | ----------------------------------- |
| GET    | `/api/health`      | Health check                        |
| GET    | `/api/items`       | List items                          |
| GET    | `/api/items/<id>`  | Get one item                        |
| POST   | `/api/items`       | Create item (`{name, description}`) |
| DELETE | `/api/items/<id>`  | Delete item                         |
| GET    | `/api/users`       | List users                          |
| POST   | `/api/upload`      | Upload a file (multipart `file`)    |

## Frontend (React + Vite, port 5173)

Requires Node `^20.19` or `>=22.12` (`nvm use` picks up `.nvmrc`).

```sh
cd frontend
npm install
npm run dev
```

Vite proxies `/api/*` to the Flask server, so start the backend first. API helpers live in `frontend/src/api/client.ts`; pages are in `frontend/src/pages/`.
