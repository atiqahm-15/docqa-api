# Document Q&A API — Design Spec

Date: 2026-08-18
Status: Approved

## Purpose

A portfolio project to learn FastAPI and LangChain together by building a
"chat with your PDFs" API. A user uploads PDF documents, the system chunks
and embeds them into a local vector store, and the user can ask questions
about the documents through a conversational, multi-turn chat endpoint. All
answers are grounded with source citations (filename + page) pulled from the
retrieved chunks.

## Goals

- Learn FastAPI: routing, request/response models, file uploads, error
  handling, background/async patterns.
- Learn LangChain: document loaders, text splitting, embeddings, vector
  stores, history-aware retrieval chains, chat memory.
- Zero ongoing cost: no paid API keys required.
- Small enough in scope to actually finish and demo.

## Non-Goals

- No multi-user accounts or authentication (single-user, local tool).
- No frontend UI — interaction happens through FastAPI's auto-generated
  Swagger docs (`/docs`) or `curl`.
- No support for non-PDF file formats in v1.
- No deployment/hosting — runs locally.

## Tech Stack

- **FastAPI** (Python 3.11+) — web framework and API layer.
- **LangChain** — RAG orchestration: document loading, chunking, retrieval
  chains, chat history.
- **Ollama** (local) — serves both the embedding model (`nomic-embed-text`)
  and the generation model (`llama3.2` or similar). No API key, no cost, but
  requires Ollama to be installed and running locally.
- **ChromaDB** — local, file-persisted vector store for document chunks.
- **SQLite** — persists chat history per session via LangChain's
  `SQLChatMessageHistory`, so conversations survive server restarts.

## Project Structure

```
docqa-api/
  app/
    main.py                 # FastAPI app + route registration
    config.py                # settings: model names, Ollama URL, data paths
    schemas.py                # Pydantic request/response models
    services/
      document_service.py     # PDF load -> chunk -> embed -> store in Chroma
      chat_service.py           # history-aware retrieval chain + SQLite memory
  data/                      # gitignored: chroma db, sqlite file, uploaded PDFs
  tests/
  requirements.txt
  .env.example
  README.md
```

`document_service` and `chat_service` are kept as separate modules, each
with one responsibility: turning PDFs into stored vectors, and turning
questions + history into grounded answers. Each can be reasoned about and
tested independently of the other.

## Data Flow

### Uploading a document

1. Client POSTs a PDF to `POST /documents/upload`.
2. File is saved to `data/uploads/`.
3. `PyPDFLoader` extracts text per page.
4. `RecursiveCharacterTextSplitter` splits the text into ~1000-character
   chunks with ~150-character overlap.
5. Each chunk is embedded via `OllamaEmbeddings` and stored in Chroma with
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
6. The chunks + question are passed to `ChatOllama` to generate an answer.
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

## Error Handling

- Non-PDF upload → `400` with a clear message.
- Corrupt/unreadable PDF → `422`.
- Chat request when no documents are indexed → `400` telling the user to
  upload a document first.
- Ollama unreachable → `503` with a message pointing at the local Ollama
  dependency.
- Unknown `session_id` on the history endpoint → `404`.

## Testing

- `pytest` with FastAPI's `TestClient`.
- Unit tests for `document_service` chunking logic using a small sample PDF
  fixture — no Ollama dependency.
- Endpoints that call Ollama (`/documents/upload`, `/chat`) use mocked
  `OllamaEmbeddings`/`ChatOllama` in the default test suite so it runs fast
  and without any local model server.
- A small set of tests marked `integration` hit real Ollama and are meant to
  be run manually while it's up locally — not part of a CI run, since CI
  won't have Ollama available.

## Open Decisions Deferred to Implementation

- Exact chunk size/overlap tuning (starting values: 1000/150 chars,
  adjustable based on retrieval quality observed during testing).
- Specific Ollama model tags to pin in `.env.example` (e.g.
  `llama3.2:3b` vs a larger variant) — chosen for a balance of speed and
  answer quality on typical consumer hardware.
