# Document Q&A API — Design Spec

Date: 2026-08-18
Status: Approved

## Purpose

A portfolio project to learn FastAPI and LangChain together by building a
"chat with your PDFs" app. A user uploads PDF documents, the system chunks
and embeds them into a local vector store, and the user can ask questions
about the documents through a conversational, multi-turn chat interface. All
answers are grounded with source citations (filename + page) pulled from the
retrieved chunks. The finished project includes a backend API, a React
frontend, and a live deployment.

## Goals

- Learn FastAPI: routing, request/response models, file uploads, error
  handling, async patterns, CORS.
- Learn LangChain: document loaders, text splitting, embeddings, vector
  stores, history-aware retrieval chains, chat memory, multi-provider
  abstraction.
- Learn React (Vite): building a small chat UI against a REST API.
- Zero ongoing cost for the deployed version.
- Small enough in scope, and phased enough, to actually finish and demo.

## Non-Goals

- No multi-user accounts or authentication (single-user tool).
- No support for non-PDF file formats in v1.
- No CI/CD pipeline beyond Vercel's built-in auto-deploy (backend deploys
  are manual `fly deploy` for now).

## Tech Stack

- **FastAPI** (Python 3.11+) — web framework and API layer.
- **LangChain** — RAG orchestration: document loading, chunking, retrieval
  chains, chat history, multi-provider LLM abstraction.
- **LLM providers (swappable):**
  - **Ollama** (local dev) — serves both the embedding model
    (`nomic-embed-text`) and the generation model (`llama3.2` or similar).
    No API key, no cost, but requires Ollama installed and running locally.
  - **Google Gemini** (deployed) — free-tier hosted API, used for the live
    deployment where Ollama can't run.
- **ChromaDB** — persisted vector store for document chunks (local disk in
  dev, a Fly.io volume when deployed).
- **SQLite** — persists chat history per session via LangChain's
  `SQLChatMessageHistory`, so conversations survive restarts.
- **React + Vite** — frontend chat UI.
- **Fly.io** — backend hosting, with a small persistent volume for
  Chroma/SQLite/uploads.
- **Vercel** — frontend hosting, auto-deployed from GitHub.

## Important Technical Note: Provider Switch Changes the Vector Space

Ollama and Gemini produce embeddings in different vector spaces, so they are
not interchangeable. The local Chroma database (built with Ollama
embeddings) and the deployed one (built with Gemini embeddings) are
necessarily separate stores — a document uploaded locally will not appear
on the live deployed demo, and vice versa. This is expected behavior, not a
bug, and is driven entirely by the `LLM_PROVIDER` environment variable.

## Project Structure

```
docqa-api/
  backend/
    app/
      main.py                   # FastAPI app + route registration + CORS
      config.py                  # settings, LLM provider factory, paths
      schemas.py                  # Pydantic request/response models
      services/
        document_service.py       # PDF load -> chunk -> embed -> store in Chroma
        chat_service.py             # history-aware retrieval chain + SQLite memory
      providers/
        ollama_provider.py          # local embeddings + chat model
        gemini_provider.py           # hosted embeddings + chat model
    data/                        # gitignored: chroma db, sqlite file, uploads
    tests/
    requirements.txt
    Dockerfile
    fly.toml
    .env.example
  frontend/
    src/
      components/
        UploadPanel.jsx           # PDF upload UI
        DocumentList.jsx           # indexed documents, delete action
        ChatWindow.jsx              # message list, input, source citations
      App.jsx
      api.js                     # fetch wrapper, reads VITE_API_URL
    .env.example
    package.json
  README.md
```

`document_service` and `chat_service` are kept as separate modules, each
with one responsibility: turning PDFs into stored vectors, and turning
questions + history into grounded answers. The `providers/` package isolates
the two LLM backends behind a common interface so the rest of the app never
needs to know which one is active.

## Data Flow

### Uploading a document

1. Client POSTs a PDF to `POST /documents/upload`.
2. File is saved to `data/uploads/`.
3. `PyPDFLoader` extracts text per page.
4. `RecursiveCharacterTextSplitter` splits the text into ~1000-character
   chunks with ~150-character overlap.
5. Each chunk is embedded via the active provider's embeddings model and
   stored in Chroma with metadata: source filename, document ID, page
   number.
6. Endpoint returns `{document_id, filename, chunk_count}`.

### Asking a question

1. Client POSTs `{session_id (optional), question}` to `POST /chat`.
2. If `session_id` is omitted, a new one is generated.
3. Prior messages for that session are loaded from SQLite via
   `SQLChatMessageHistory`.
4. A history-aware retriever reformulates the question using that history
   (so follow-ups like "what about the second one?" resolve to a standalone
   query).
5. The reformulated query retrieves the top-k most relevant chunks from
   Chroma.
6. The chunks + question are passed to the active provider's chat model to
   generate an answer.
7. The question/answer pair is saved back to SQLite.
8. Endpoint returns `{answer, sources: [{filename, page}], session_id}`.

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/documents/upload` | POST | Upload a PDF, chunk + embed + index it. Returns `{document_id, filename, chunk_count}`. |
| `/documents` | GET | List indexed documents (id, filename, upload timestamp, chunk count). |
| `/documents/{document_id}` | DELETE | Remove a document's vectors from Chroma and delete its file. |
| `/chat` | POST | Ask a question. Body: `{session_id?, question}`. Returns `{answer, sources, session_id}`. |
| `/chat/{session_id}/history` | GET | Return stored message history for a session. |

CORS is enabled on the FastAPI app for the deployed Vercel origin (and
`localhost` during development).

## Frontend

A Vite + React single-page app with three pieces:

- **UploadPanel** — file picker for PDFs, shows upload/indexing progress,
  calls `POST /documents/upload`.
- **DocumentList** — sidebar listing indexed documents from `GET
  /documents`, with a delete action per document.
- **ChatWindow** — message list and input box, calls `POST /chat`, renders
  each answer with its source citations (filename + page). `session_id` is
  kept in the browser's local storage so a page refresh doesn't lose the
  conversation.

The API base URL is read from `VITE_API_URL`, pointing at `localhost:8000`
in dev and the deployed Fly.io URL in production.

## Deployment

- **Backend:** a `Dockerfile` packages the FastAPI app; deployed to Fly.io
  with a small persistent volume mounted at `/data` for Chroma, SQLite, and
  uploaded PDFs, so data survives restarts. `LLM_PROVIDER=gemini` and the
  Gemini API key are set as Fly secrets.
- **Frontend:** deployed to Vercel directly from the GitHub repo, which
  auto-builds and redeploys on every push to `main`. `VITE_API_URL` is set
  as a Vercel environment variable pointing at the Fly.io backend.
- Both platforms are used within their free tiers.

## Error Handling

- Non-PDF upload → `400` with a clear message.
- Corrupt/unreadable PDF → `422`.
- Chat request when no documents are indexed → `400` telling the user to
  upload a document first.
- Active LLM provider unreachable (Ollama not running locally, or Gemini API
  error) → `503` with a message identifying which provider failed.
- Unknown `session_id` on the history endpoint → `404`.

## Testing

- `pytest` with FastAPI's `TestClient`.
- Unit tests for `document_service` chunking logic using a small sample PDF
  fixture — no LLM provider dependency.
- Endpoints that call an LLM provider (`/documents/upload`, `/chat`) use
  mocked embeddings/chat models in the default test suite so it runs fast
  and without any live model server or API key.
- A small set of tests marked `integration` hit the real Ollama provider and
  are meant to be run manually while it's up locally — not part of a CI run.
- Frontend: manual testing against the local backend during development; no
  automated frontend test suite in v1 (kept out of scope to stay focused on
  FastAPI/LangChain learning goals).

## Build Phasing

Given the added scope (frontend + deployment), the project is built in four
independently-demoable phases rather than one push:

1. **Backend core** — FastAPI + LangChain + Ollama, fully working and
   tested locally via Swagger docs.
2. **Provider abstraction** — add the Gemini provider behind the same
   interface, config-switchable via `LLM_PROVIDER`.
3. **Frontend** — React app built against the local backend (either
   provider).
4. **Deployment** — backend to Fly.io (Gemini provider, persistent volume),
   frontend to Vercel, wired together via `VITE_API_URL`.

Each phase should get its own implementation plan and be verified working
before moving to the next.

## Open Decisions Deferred to Implementation

- Exact chunk size/overlap tuning (starting values: 1000/150 chars,
  adjustable based on retrieval quality observed during testing).
- Specific Ollama model tags to pin in `.env.example` (e.g. `llama3.2:3b`
  vs a larger variant) — chosen for a balance of speed and answer quality on
  typical consumer hardware.
- Specific Gemini model name for the deployed provider (e.g.
  `gemini-1.5-flash` or current equivalent free-tier model at
  implementation time).
