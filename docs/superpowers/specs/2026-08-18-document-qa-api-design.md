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
frontend, and a live deployment, all built against the same LLM provider so
local development and the deployed app behave identically.

## Goals

- Learn FastAPI: routing, request/response models, file uploads, error
  handling, async patterns, CORS.
- Learn LangChain: document loaders, text splitting, embeddings, vector
  stores, history-aware retrieval chains, chat memory.
- Learn React (Vite): building a small chat UI against a REST API.
- Zero ongoing cost, using Google Gemini's free API tier for both embeddings
  and generation.
- Small enough in scope, and phased enough, to actually finish and demo.

## Non-Goals

- No multi-user accounts or authentication (single-user tool).
- No support for non-PDF file formats in v1.
- No CI/CD pipeline beyond Vercel's built-in auto-deploy (backend deploys
  are manual `fly deploy` for now).
- No multi-provider LLM abstraction in v1. The app talks to Gemini directly
  rather than through a swappable provider interface, to keep the code
  simple while there's only one provider to support. Provider-swapping
  (e.g. adding a local Ollama option) is a natural future enhancement — see
  "Future Enhancement" below — deferred so effort isn't spent on
  abstraction the project doesn't yet need.

## Tech Stack

- **FastAPI** (Python 3.11+) — web framework and API layer.
- **LangChain** — RAG orchestration: document loading, chunking, retrieval
  chains, chat history.
- **Google Gemini** (free API tier) — used for both embeddings
  (`models/embedding-001` or current equivalent) and chat generation
  (`gemini-1.5-flash` or current equivalent), in both local development and
  the deployed app. Requires a free Gemini API key and internet access, even
  when running locally.
- **ChromaDB** — persisted vector store for document chunks (local disk in
  dev, a Fly.io volume when deployed).
- **SQLite** — persists chat history per session via LangChain's
  `SQLChatMessageHistory`, so conversations survive restarts.
- **React + Vite** — frontend chat UI.
- **Fly.io** — backend hosting, with a small persistent volume for
  Chroma/SQLite/uploads.
- **Vercel** — frontend hosting, auto-deployed from GitHub.

Because the same provider is used everywhere, local development and the
deployed app share the same embedding space — a document indexed locally is
directly comparable to one indexed on the deployed instance (though each
environment still keeps its own separate Chroma database/volume; only the
embedding representation is shared, not the actual stored data).

## Project Structure

```
docqa-api/
  backend/
    app/
      main.py                   # FastAPI app + route registration + CORS
      config.py                  # settings, Gemini client setup, paths
      schemas.py                  # Pydantic request/response models
      services/
        document_service.py       # PDF load -> chunk -> embed -> store in Chroma
        chat_service.py             # history-aware retrieval chain + SQLite memory
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
questions + history into grounded answers. `config.py` centralizes Gemini
client construction so the embeddings/chat model are configured in one
place, even without a full provider-abstraction layer.

## Data Flow

### Uploading a document

1. Client POSTs a PDF to `POST /documents/upload`.
2. File is saved to `data/uploads/`.
3. `PyPDFLoader` extracts text per page.
4. `RecursiveCharacterTextSplitter` splits the text into ~1000-character
   chunks with ~150-character overlap.
5. Each chunk is embedded via Gemini embeddings and stored in Chroma with
   metadata: source filename, document ID, page number.
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
6. The chunks + question are passed to Gemini's chat model to generate an
   answer.
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
  uploaded PDFs, so data survives restarts. The Gemini API key is set as a
  Fly secret.
- **Frontend:** deployed to Vercel directly from the GitHub repo, which
  auto-builds and redeploys on every push to `main`. `VITE_API_URL` is set
  as a Vercel environment variable pointing at the Fly.io backend.
- Both platforms are used within their free tiers.

## Error Handling

- Non-PDF upload → `400` with a clear message.
- Corrupt/unreadable PDF → `422`.
- Chat request when no documents are indexed → `400` telling the user to
  upload a document first.
- Gemini API unreachable, rate-limited, or erroring → `503` with a message
  identifying the failure.
- Unknown `session_id` on the history endpoint → `404`.

## Testing

- `pytest` with FastAPI's `TestClient`.
- Unit tests for `document_service` chunking logic using a small sample PDF
  fixture — no Gemini dependency.
- Endpoints that call Gemini (`/documents/upload`, `/chat`) use mocked
  embeddings/chat models in the default test suite so it runs fast and
  without a live API key.
- A small set of tests marked `integration` hit the real Gemini API and are
  meant to be run manually with a valid API key set — not part of a CI run.
- Frontend: manual testing against the local backend during development; no
  automated frontend test suite in v1 (kept out of scope to stay focused on
  FastAPI/LangChain learning goals).

## Build Phasing

The project is built in three independently-demoable phases:

1. **Backend core** — FastAPI + LangChain + Gemini, fully working and
   tested locally via Swagger docs.
2. **Frontend** — React app built against the local backend.
3. **Deployment** — backend to Fly.io (persistent volume, Gemini secret),
   frontend to Vercel, wired together via `VITE_API_URL`.

Each phase should get its own implementation plan and be verified working
before moving to the next.

## Future Enhancement: Multi-Provider Abstraction

Not part of v1, but a natural next feature if desired later: introduce a
provider interface in `config.py` (e.g. `get_embeddings()` /
`get_chat_model()` factory functions) so a second provider — most likely a
local Ollama setup for fully offline development — can be added behind an
`LLM_PROVIDER` environment variable without changing `document_service` or
`chat_service`. Deferred for now because the project only exercises one
provider in practice, and building the abstraction ahead of that need would
add surface area without a demonstrable benefit.

## Open Decisions Deferred to Implementation

- Exact chunk size/overlap tuning (starting values: 1000/150 chars,
  adjustable based on retrieval quality observed during testing).
- Specific Gemini model names to pin in `.env.example` (embeddings and
  chat) — chosen at implementation time based on what's current in Gemini's
  free tier.
