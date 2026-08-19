# Document Q&A API

A "chat with your PDFs" app: upload PDF documents, and ask grounded,
multi-turn questions about them with source citations (filename + page).
Built as a portfolio project to learn **FastAPI** and **LangChain** together,
backed by Google Gemini's free API tier.

Full design spec: [docs/superpowers/specs/2026-08-18-document-qa-api-design.md](docs/superpowers/specs/2026-08-18-document-qa-api-design.md)

## Features

- Upload PDFs — text is chunked, embedded, and indexed into a local vector store
- Ask questions in a multi-turn chat — follow-ups resolve using conversation history
- Every answer is grounded with source citations (filename + page number)
- Chat sessions persist across page reloads
- Document list with delete support

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, LangChain, ChromaDB, SQLite |
| LLM | Google Gemini (free tier) — embeddings + chat generation |
| Frontend | React 19 + Vite |
| Testing | pytest (backend), `node:test` + Playwright (frontend) |

## How it works

1. **Upload** — a PDF is loaded page-by-page, split into ~1000-character
   chunks, embedded via Gemini, and stored in Chroma with metadata
   (document ID, filename, page number).
2. **Ask** — a question is reformulated into a standalone query using chat
   history, the top-k most relevant chunks are retrieved from Chroma, and
   Gemini generates an answer grounded in those chunks.
3. Every answer returns its source chunks as `{filename, page}` citations,
   and the question/answer pair is saved to SQLite so the conversation
   survives a page refresh.

## Project Structure

```
docqa-api/
  backend/          FastAPI + LangChain API (see backend/README.md)
  frontend/         React + Vite chat UI (see frontend/README.md)
  docs/superpowers/  design spec + phased implementation plans
```

## Quick Start

You'll need a free Gemini API key from https://aistudio.google.com/apikey.

**1. Backend** (runs on http://localhost:8000)

```bash
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1        # Windows PowerShell — macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then paste your Gemini API key into .env
uvicorn app.main:app --reload
```

**2. Frontend** (runs on http://localhost:5173, in a second terminal)

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, upload a PDF, and start asking questions.

See [backend/README.md](backend/README.md) and
[frontend/README.md](frontend/README.md) for testing instructions and more
detail.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/documents/upload` | POST | Upload a PDF, chunk + embed + index it |
| `/documents` | GET | List indexed documents |
| `/documents/{document_id}` | DELETE | Remove a document and its vectors |
| `/chat` | POST | Ask a question, returns answer + source citations |
| `/chat/{session_id}/history` | GET | Get a session's message history |

Interactive Swagger docs are available at http://localhost:8000/docs once
the backend is running.

## Deployment

Deployment configs for Fly.io (backend, via `backend/Dockerfile` +
`backend/fly.toml`) and Vercel (frontend) are included and ready to use, but
this project currently runs locally only — it's a learning project, not a
hosted service. If you want to deploy your own copy, `backend/README.md`'s
"Known limitations" section is a good starting point.

## Known Limitations (by design)

Single-user, no authentication, PDF-only. See
[backend/README.md](backend/README.md#known-limitations-by-design-for-this-learning-project)
for the full list.
