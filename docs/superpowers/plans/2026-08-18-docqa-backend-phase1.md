# Document Q&A API — Backend Core (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and test, entirely locally, the FastAPI + LangChain backend that lets a user upload PDFs and ask grounded, multi-turn questions about them via Google Gemini — no frontend, no deployment, verified through Swagger docs and pytest.

**Architecture:** A FastAPI app exposes five endpoints backed by two small service modules (`document_service` for PDF chunking/embedding, `chat_service` for retrieval + conversational answering) and a lightweight SQLite table for document metadata. LangChain's Gemini integrations provide embeddings and chat; ChromaDB persists vectors to disk; LangChain's `SQLChatMessageHistory` persists chat turns to the same SQLite file. FastAPI's dependency-injection system (`Depends`) wires Gemini/Chroma instances into routes, which is what makes the whole thing testable — tests override just the embeddings and chat-model dependencies with LangChain's fake test doubles, so the full HTTP → service → Chroma → SQLite path is exercised without ever calling the real Gemini API.

**Tech Stack:** Python 3.11+, FastAPI 0.141, LangChain 1.3 (langchain-core, langchain-community, langchain-text-splitters, langchain-chroma 1.1, langchain-google-genai 4.3), ChromaDB 1.5, pypdf 6.16, pydantic-settings 2.15, pytest 9.1.

## Global Constraints

- Python 3.11+ only; no frontend code, no Docker/Fly.io/deployment config in this phase (that's Phase 2/3 per the design spec).
- PDF is the only supported document format in v1.
- Single-user, no authentication.
- Zero ongoing cost: Google Gemini free API tier only, for both embeddings and chat generation.
- CORS must allow `http://localhost:5173` and `http://localhost:3000` (future frontend dev servers), configurable via `ALLOWED_ORIGINS`.
- Every endpoint that can fail for a Gemini-side reason (unreachable, rate-limited, erroring) must return `503` with a message identifying Gemini as the failure source — never a raw 500.
- Non-PDF upload → `400`; corrupt/unreadable PDF → `422`; chat request with zero indexed documents → `400`; unknown `session_id` on the history endpoint → `404`.
- Default `pytest` run must require no live API key and no network access — all Gemini-touching tests use LangChain's fake embeddings/chat-model test doubles via FastAPI dependency overrides. A separate `integration` marker is reserved for tests that hit the real Gemini API and are excluded from the default run.
- All package versions below are pinned to versions verified to install together without conflict; do not swap in different major versions without re-checking compatibility.

---

## File Structure

```
docqa-api/
  backend/
    requirements.txt
    .env.example
    .gitignore
    pytest.ini
    README.md
    app/
      __init__.py
      config.py          # Settings (pydantic-settings) + get_settings()
      exceptions.py       # ProviderUnavailableError
      dependencies.py      # FastAPI Depends providers: get_embeddings, get_chat_model, get_vectorstore
      db.py                 # SQLite documents-metadata table: connection + CRUD helpers
      schemas.py             # Pydantic request/response models
      main.py                 # FastAPI app, CORS, exception handler, all 5 routes + /health
      services/
        __init__.py
        document_service.py   # chunk_pdf, embed_and_store, delete_document_vectors
        chat_service.py         # get_session_history, answer_question
    data/                    # gitignored at runtime: chroma/, uploads/, app.db
    tests/
      __init__.py
      conftest.py
      fixtures/
        sample.pdf
      test_config.py
      test_exceptions.py
      test_dependencies.py
      test_db.py
      test_document_chunking.py
      test_document_storage.py
      test_documents_api.py
      test_chat_service.py
      test_chat_api.py
      integration/
        __init__.py
        test_gemini_integration.py
```

Each service file has one job: `document_service` only ever turns a PDF file into stored vectors (and removes them again); `chat_service` only ever turns a question + history into a grounded answer. `db.py` is the one place that touches the documents SQLite table directly, so nothing else needs to know the schema. `dependencies.py` is the one place Gemini/Chroma objects get constructed, which is exactly why tests can swap them out cleanly.

---

### Task 1: Project scaffolding and Settings

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/.gitignore`
- Create: `backend/pytest.ini`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/test_config.py`

**Interfaces:**
- Produces: `app.config.Settings` (pydantic-settings `BaseSettings` subclass) with fields `google_api_key: str`, `gemini_chat_model: str`, `gemini_embedding_model: str`, `data_dir: Path`, `allowed_origins: list[str]`, `retrieval_k: int`, `chunk_size: int`, `chunk_overlap: int`. Produces `app.config.get_settings() -> Settings` (`@lru_cache`d).

- [ ] **Step 1: Create the dependency and environment files**

`backend/requirements.txt`:
```
fastapi==0.141.1
uvicorn[standard]==0.52.3
python-multipart==0.0.32
pydantic-settings==2.15.0
langchain==1.3.15
langchain-google-genai==4.3.4
langchain-chroma==1.1.0
langchain-community==0.4.2
langchain-text-splitters==1.1.2
chromadb==1.5.9
pypdf==6.16.1
python-dotenv==1.2.3
pytest==9.1.1
pytest-mock==3.15.1
httpx==0.28.1
```

`backend/.env.example`:
```
GOOGLE_API_KEY=your-gemini-api-key-here
GEMINI_CHAT_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=gemini-embedding-2-preview
DATA_DIR=data
ALLOWED_ORIGINS=["http://localhost:5173","http://localhost:3000"]
```

`backend/.gitignore`:
```
data/
__pycache__/
*.pyc
.env
.pytest_cache/
*.egg-info/
.venv/
```

`backend/pytest.ini`:
```ini
[pytest]
markers =
    integration: tests that call the real Gemini API (requires GOOGLE_API_KEY, run manually)
addopts = -m "not integration"
testpaths = tests
```

Run:
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Expected: all packages install without dependency conflicts.

- [ ] **Step 2: Write the failing test**

`backend/tests/__init__.py`: (empty file)

`backend/tests/test_config.py`:
```python
from app.config import Settings, get_settings


def test_settings_reads_google_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key-123")
    settings = Settings(_env_file=None)
    assert settings.google_api_key == "test-key-123"


def test_settings_has_default_gemini_models():
    settings = Settings(_env_file=None, google_api_key="x")
    assert settings.gemini_chat_model == "gemini-2.5-flash"
    assert settings.gemini_embedding_model == "gemini-embedding-2-preview"


def test_settings_allows_model_override_from_env(monkeypatch):
    monkeypatch.setenv("GEMINI_CHAT_MODEL", "gemini-2.5-pro")
    settings = Settings(_env_file=None, google_api_key="x")
    assert settings.gemini_chat_model == "gemini-2.5-pro"


def test_settings_default_allowed_origins_include_localhost():
    settings = Settings(_env_file=None, google_api_key="x")
    assert "http://localhost:5173" in settings.allowed_origins


def test_get_settings_returns_cached_instance(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "x")
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
    get_settings.cache_clear()
```

`backend/app/__init__.py`: (empty file)

`backend/tests/conftest.py`:
```python
from pathlib import Path

import pytest
from langchain_core.embeddings import DeterministicFakeEmbedding

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fake_embeddings():
    return DeterministicFakeEmbedding(size=768)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 4: Write minimal implementation**

`backend/app/config.py`:
```python
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    google_api_key: str = ""
    gemini_chat_model: str = "gemini-2.5-flash"
    gemini_embedding_model: str = "gemini-embedding-2-preview"
    data_dir: Path = Path("data")
    allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
    ]
    retrieval_k: int = 4
    chunk_size: int = 1000
    chunk_overlap: int = 150

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/.env.example backend/.gitignore backend/pytest.ini \
  backend/app/__init__.py backend/app/config.py backend/tests/__init__.py \
  backend/tests/conftest.py backend/tests/test_config.py
git commit -m "feat: add backend scaffolding and Settings"
```

---

### Task 2: FastAPI app skeleton with health check and CORS

**Files:**
- Create: `backend/app/main.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Consumes: `app.config.get_settings` (Task 1).
- Produces: `app.main.app` (FastAPI instance) — every later task adds routes to this same object.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_check_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.main'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(title="Document Q&A API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_health.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_health.py
git commit -m "feat: add FastAPI app skeleton with health check and CORS"
```

---

### Task 3: Custom provider-unavailable exception and handler

**Files:**
- Create: `backend/app/exceptions.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_exceptions.py`

**Interfaces:**
- Produces: `app.exceptions.ProviderUnavailableError(provider: str, detail: str)` — later tasks raise this from route handlers whenever a Gemini call fails.
- Produces: `app.main.provider_unavailable_handler` (registered on `app` for `ProviderUnavailableError`, maps to HTTP 503).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_exceptions.py`:
```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.exceptions import ProviderUnavailableError
from app.main import provider_unavailable_handler


def test_provider_unavailable_error_returns_503():
    test_app = FastAPI()
    test_app.add_exception_handler(ProviderUnavailableError, provider_unavailable_handler)

    @test_app.get("/boom")
    def boom():
        raise ProviderUnavailableError("Gemini", "connection refused")

    client = TestClient(test_app)
    response = client.get("/boom")

    assert response.status_code == 503
    assert response.json() == {"detail": "Gemini is unavailable: connection refused"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_exceptions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.exceptions'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/exceptions.py`:
```python
class ProviderUnavailableError(Exception):
    """Raised when the configured LLM provider (Gemini) cannot serve a request."""

    def __init__(self, provider: str, detail: str):
        self.provider = provider
        self.detail = detail
        super().__init__(f"{provider} is unavailable: {detail}")
```

Modify `backend/app/main.py` — add these imports and the handler, right after the `CORSMiddleware` block and before the `/health` route:
```python
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.exceptions import ProviderUnavailableError

settings = get_settings()

app = FastAPI(title="Document Q&A API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ProviderUnavailableError)
async def provider_unavailable_handler(request: Request, exc: ProviderUnavailableError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_exceptions.py -v`
Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/exceptions.py backend/app/main.py backend/tests/test_exceptions.py
git commit -m "feat: add ProviderUnavailableError and its 503 handler"
```

---

### Task 4: Pydantic request/response schemas

**Files:**
- Create: `backend/app/schemas.py`
- Test: `backend/tests/test_schemas.py`

**Interfaces:**
- Produces: `DocumentUploadResponse{document_id, filename, chunk_count}`, `DocumentListItem{document_id, filename, uploaded_at, chunk_count}`, `DocumentListResponse{documents}`, `ChatRequest{question, session_id}`, `SourceCitation{filename, page}`, `ChatResponse{answer, sources, session_id}`, `ChatMessageItem{role, content}`, `ChatHistoryResponse{session_id, messages}` — every later route uses these exact names and fields.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_schemas.py`:
```python
import pytest
from pydantic import ValidationError

from app.schemas import ChatRequest, ChatResponse, DocumentUploadResponse, SourceCitation


def test_chat_request_requires_question():
    with pytest.raises(ValidationError):
        ChatRequest()


def test_chat_request_session_id_defaults_to_none():
    request = ChatRequest(question="What is this document about?")
    assert request.session_id is None


def test_chat_response_accepts_list_of_sources():
    response = ChatResponse(
        answer="It's about LangChain.",
        sources=[SourceCitation(filename="a.pdf", page=1)],
        session_id="sess-1",
    )
    assert response.sources[0].page == 1


def test_document_upload_response_fields():
    response = DocumentUploadResponse(document_id="d1", filename="a.pdf", chunk_count=3)
    assert response.chunk_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/schemas.py`:
```python
from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    uploaded_at: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None


class SourceCitation(BaseModel):
    filename: str
    page: int


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    session_id: str


class ChatMessageItem(BaseModel):
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessageItem]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_schemas.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/tests/test_schemas.py
git commit -m "feat: add request/response schemas"
```

---

### Task 5: Gemini and Chroma dependency providers

**Files:**
- Create: `backend/app/dependencies.py`
- Test: `backend/tests/test_dependencies.py`

**Interfaces:**
- Consumes: `app.config.Settings`, `app.config.get_settings` (Task 1).
- Produces: `get_embeddings(settings: Settings = Depends(get_settings)) -> Embeddings`, `get_chat_model(settings: Settings = Depends(get_settings)) -> BaseChatModel`, `get_vectorstore(embeddings: Embeddings = Depends(get_embeddings), settings: Settings = Depends(get_settings)) -> Chroma` — every route that touches Gemini or Chroma depends on these three names, and every test overrides `get_embeddings`/`get_chat_model` via `app.dependency_overrides`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_dependencies.py`:
```python
from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config import Settings
from app.dependencies import get_chat_model, get_embeddings, get_vectorstore


def test_get_embeddings_uses_configured_model():
    settings = Settings(_env_file=None, google_api_key="test-key", gemini_embedding_model="my-embed-model")
    embeddings = get_embeddings(settings)
    assert isinstance(embeddings, GoogleGenerativeAIEmbeddings)
    assert embeddings.model == "my-embed-model"


def test_get_chat_model_uses_configured_model():
    settings = Settings(_env_file=None, google_api_key="test-key", gemini_chat_model="my-chat-model")
    chat_model = get_chat_model(settings)
    assert isinstance(chat_model, ChatGoogleGenerativeAI)
    assert chat_model.model == "models/my-chat-model" or chat_model.model == "my-chat-model"


def test_get_vectorstore_persists_under_data_dir(tmp_path, fake_embeddings):
    settings = Settings(_env_file=None, google_api_key="test-key", data_dir=tmp_path)
    vectorstore = get_vectorstore(fake_embeddings, settings)
    assert isinstance(vectorstore, Chroma)
    assert (tmp_path / "chroma").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dependencies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.dependencies'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/dependencies.py`:
```python
from fastapi import Depends
from langchain_chroma import Chroma
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

from app.config import Settings, get_settings


def get_embeddings(settings: Settings = Depends(get_settings)) -> Embeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.gemini_embedding_model,
        google_api_key=settings.google_api_key,
    )


def get_chat_model(settings: Settings = Depends(get_settings)) -> BaseChatModel:
    return ChatGoogleGenerativeAI(
        model=settings.gemini_chat_model,
        google_api_key=settings.google_api_key,
    )


def get_vectorstore(
    embeddings: Embeddings = Depends(get_embeddings),
    settings: Settings = Depends(get_settings),
) -> Chroma:
    persist_dir = settings.data_dir / "chroma"
    persist_dir.mkdir(parents=True, exist_ok=True)
    return Chroma(
        collection_name="documents",
        embedding_function=embeddings,
        persist_directory=str(persist_dir),
    )
```

> Note: `ChatGoogleGenerativeAI` may normalize the model name internally (e.g. prefixing `models/`), which is why the test accepts either form — assert on whichever your installed version actually returns after running it once.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dependencies.py -v`
Expected: 3 passed. If the model-name assertion fails because of a different normalization, run `python3 -c "from app.dependencies import get_chat_model; from app.config import Settings; print(get_chat_model(Settings(_env_file=None, google_api_key='x', gemini_chat_model='my-chat-model')).model)"` to see the actual stored value and adjust the assertion to match it exactly.

- [ ] **Step 5: Commit**

```bash
git add backend/app/dependencies.py backend/tests/test_dependencies.py
git commit -m "feat: add Gemini embeddings/chat and Chroma dependency providers"
```

---

### Task 6: SQLite documents-metadata store

**Files:**
- Create: `backend/app/db.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: `get_db_path(data_dir: Path) -> Path`, `get_connection(data_dir: Path)` (context manager yielding a `sqlite3.Connection` with `row_factory = sqlite3.Row`, auto-creating the `documents` table), `insert_document(conn, document_id, filename, file_path, chunk_count)`, `list_documents(conn) -> list[sqlite3.Row]`, `get_document(conn, document_id) -> sqlite3.Row | None`, `delete_document(conn, document_id)`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_db.py`:
```python
from app import db


def test_insert_and_list_documents(tmp_path):
    with db.get_connection(tmp_path) as conn:
        db.insert_document(conn, "doc1", "a.pdf", str(tmp_path / "a.pdf"), 3)
        db.insert_document(conn, "doc2", "b.pdf", str(tmp_path / "b.pdf"), 5)

    with db.get_connection(tmp_path) as conn:
        rows = db.list_documents(conn)

    assert len(rows) == 2
    assert {row["document_id"] for row in rows} == {"doc1", "doc2"}


def test_get_document_returns_none_when_missing(tmp_path):
    with db.get_connection(tmp_path) as conn:
        row = db.get_document(conn, "nonexistent")
    assert row is None


def test_get_document_returns_matching_row(tmp_path):
    with db.get_connection(tmp_path) as conn:
        db.insert_document(conn, "doc1", "a.pdf", str(tmp_path / "a.pdf"), 3)

    with db.get_connection(tmp_path) as conn:
        row = db.get_document(conn, "doc1")

    assert row["filename"] == "a.pdf"
    assert row["chunk_count"] == 3


def test_delete_document_removes_row(tmp_path):
    with db.get_connection(tmp_path) as conn:
        db.insert_document(conn, "doc1", "a.pdf", str(tmp_path / "a.pdf"), 3)

    with db.get_connection(tmp_path) as conn:
        db.delete_document(conn, "doc1")

    with db.get_connection(tmp_path) as conn:
        assert db.get_document(conn, "doc1") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/db.py`:
```python
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def get_db_path(data_dir: Path) -> Path:
    return Path(data_dir) / "app.db"


def init_documents_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            chunk_count INTEGER NOT NULL
        )
        """
    )


@contextmanager
def get_connection(data_dir: Path):
    Path(data_dir).mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(get_db_path(data_dir))
    conn.row_factory = sqlite3.Row
    try:
        init_documents_table(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_document(
    conn: sqlite3.Connection,
    document_id: str,
    filename: str,
    file_path: str,
    chunk_count: int,
) -> None:
    conn.execute(
        "INSERT INTO documents (document_id, filename, file_path, uploaded_at, chunk_count) "
        "VALUES (?, ?, ?, ?, ?)",
        (document_id, filename, file_path, datetime.now(timezone.utc).isoformat(), chunk_count),
    )


def list_documents(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()


def get_document(conn: sqlite3.Connection, document_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM documents WHERE document_id = ?", (document_id,)
    ).fetchone()


def delete_document(conn: sqlite3.Connection, document_id: str) -> None:
    conn.execute("DELETE FROM documents WHERE document_id = ?", (document_id,))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_db.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/db.py backend/tests/test_db.py
git commit -m "feat: add SQLite documents-metadata store"
```

---

### Task 7: PDF chunking service

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/document_service.py`
- Modify: `backend/tests/conftest.py` (add `sample_pdf_path` fixture)
- Test: `backend/tests/test_document_chunking.py`
- Create (binary fixture): `backend/tests/fixtures/sample.pdf`

**Interfaces:**
- Produces: `chunk_pdf(file_path: Path, document_id: str, chunk_size: int = 1000, chunk_overlap: int = 150) -> list[Document]` where each returned `Document.metadata == {"document_id": ..., "filename": ..., "page": <1-indexed int>}`.

- [ ] **Step 1: Generate the sample PDF fixture**

This fixture is a real, two-page PDF with distinct text per page, used by chunking tests. Generate it once and commit the binary file — `reportlab` is only needed to create it, not at runtime, so don't add it to `requirements.txt`.

```bash
cd backend
pip install reportlab
mkdir -p tests/fixtures
python3 -c "
from reportlab.pdfgen import canvas
c = canvas.Canvas('tests/fixtures/sample.pdf')
c.drawString(100, 750, 'LangChain is a framework for building applications powered by large language models.')
c.drawString(100, 730, 'It provides abstractions for chains, agents, memory, and retrieval.')
c.showPage()
c.drawString(100, 750, 'FastAPI is a modern, fast web framework for building APIs with Python.')
c.drawString(100, 730, 'It is based on standard Python type hints and provides automatic interactive docs.')
c.showPage()
c.save()
"
pip uninstall -y reportlab
```
Expected: `tests/fixtures/sample.pdf` exists as a 2-page PDF.

- [ ] **Step 2: Write the failing test**

Modify `backend/tests/conftest.py` — add below the `fake_embeddings` fixture:
```python
@pytest.fixture
def sample_pdf_path() -> Path:
    return FIXTURES_DIR / "sample.pdf"
```

`backend/tests/test_document_chunking.py`:
```python
from app.services import document_service


def test_chunk_pdf_splits_into_chunks_with_metadata(sample_pdf_path):
    chunks = document_service.chunk_pdf(
        sample_pdf_path, document_id="doc1", chunk_size=1000, chunk_overlap=150
    )

    assert len(chunks) >= 1
    for chunk in chunks:
        assert chunk.metadata == {
            "document_id": "doc1",
            "filename": "sample.pdf",
            "page": chunk.metadata["page"],
        }
        assert chunk.page_content.strip() != ""


def test_chunk_pdf_page_numbers_are_one_indexed(sample_pdf_path):
    chunks = document_service.chunk_pdf(sample_pdf_path, document_id="doc1")
    pages = {chunk.metadata["page"] for chunk in chunks}
    assert min(pages) == 1
    assert max(pages) == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_document_chunking.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services'`

- [ ] **Step 4: Write minimal implementation**

`backend/app/services/__init__.py`: (empty file)

`backend/app/services/document_service.py`:
```python
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_pdf(
    file_path: Path,
    document_id: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[Document]:
    loader = PyPDFLoader(str(file_path))
    pages = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )
    chunks = splitter.split_documents(pages)

    filename = Path(file_path).name
    for chunk in chunks:
        page_number = chunk.metadata.get("page", 0) + 1
        chunk.metadata = {
            "document_id": document_id,
            "filename": filename,
            "page": page_number,
        }
    return chunks
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_document_chunking.py -v`
Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/document_service.py \
  backend/tests/conftest.py backend/tests/test_document_chunking.py backend/tests/fixtures/sample.pdf
git commit -m "feat: add PDF chunking service"
```

---

### Task 8: Embedding + vector storage service

**Files:**
- Modify: `backend/app/services/document_service.py`
- Test: `backend/tests/test_document_storage.py`

**Interfaces:**
- Consumes: `fake_embeddings` fixture (Task 1), `langchain_chroma.Chroma`.
- Produces: `embed_and_store(vectorstore: Chroma, chunks: list[Document]) -> int` (returns chunk count, `0` for an empty list), `delete_document_vectors(vectorstore: Chroma, document_id: str) -> None`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_document_storage.py`:
```python
from langchain_chroma import Chroma
from langchain_core.documents import Document

from app.services import document_service


def _make_vectorstore(tmp_path, embeddings):
    return Chroma(
        collection_name="test-documents",
        embedding_function=embeddings,
        persist_directory=str(tmp_path / "chroma"),
    )


def test_embed_and_store_adds_chunks_and_returns_count(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore(tmp_path, fake_embeddings)
    chunks = [
        Document(page_content="chunk one", metadata={"document_id": "doc1", "filename": "a.pdf", "page": 1}),
        Document(page_content="chunk two", metadata={"document_id": "doc1", "filename": "a.pdf", "page": 2}),
    ]

    count = document_service.embed_and_store(vectorstore, chunks)

    assert count == 2
    stored = vectorstore.get(where={"document_id": "doc1"})
    assert len(stored["ids"]) == 2


def test_embed_and_store_returns_zero_for_empty_chunks(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore(tmp_path, fake_embeddings)
    assert document_service.embed_and_store(vectorstore, []) == 0


def test_delete_document_vectors_removes_only_matching_document(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore(tmp_path, fake_embeddings)
    document_service.embed_and_store(
        vectorstore,
        [Document(page_content="doc1 chunk", metadata={"document_id": "doc1", "filename": "a.pdf", "page": 1})],
    )
    document_service.embed_and_store(
        vectorstore,
        [Document(page_content="doc2 chunk", metadata={"document_id": "doc2", "filename": "b.pdf", "page": 1})],
    )

    document_service.delete_document_vectors(vectorstore, "doc1")

    remaining = vectorstore.get()
    remaining_doc_ids = {meta["document_id"] for meta in remaining["metadatas"]}
    assert remaining_doc_ids == {"doc2"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_document_storage.py -v`
Expected: FAIL with `AttributeError: module 'app.services.document_service' has no attribute 'embed_and_store'`

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/services/document_service.py` — add below `chunk_pdf`:
```python
def embed_and_store(vectorstore, chunks: list[Document]) -> int:
    if not chunks:
        return 0
    document_id = chunks[0].metadata["document_id"]
    ids = [f"{document_id}-{i}" for i in range(len(chunks))]
    vectorstore.add_documents(chunks, ids=ids)
    return len(chunks)


def delete_document_vectors(vectorstore, document_id: str) -> None:
    existing = vectorstore.get(where={"document_id": document_id})
    ids = existing.get("ids", [])
    if ids:
        vectorstore.delete(ids=ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_document_storage.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/document_service.py backend/tests/test_document_storage.py
git commit -m "feat: add embedding and vector storage to document service"
```

---

### Task 9: POST /documents/upload endpoint

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py` (add `test_settings` and `client` fixtures)
- Test: `backend/tests/test_documents_api.py`

**Interfaces:**
- Consumes: `document_service.chunk_pdf`, `document_service.embed_and_store` (Task 7/8), `db.get_connection`, `db.insert_document` (Task 6), `get_settings`, `get_embeddings`, `get_vectorstore` (Task 1/5), `ProviderUnavailableError` (Task 3), `DocumentUploadResponse` (Task 4).
- Produces: `POST /documents/upload` route — `201`/`200` with `DocumentUploadResponse`; `400` for non-PDF; `422` for corrupt PDF; `503` if the embedding call raises.

- [ ] **Step 1: Write the failing test**

Modify `backend/tests/conftest.py` — add below the existing fixtures:
```python
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.dependencies import get_embeddings
from app.main import app


@pytest.fixture
def test_settings(tmp_path):
    return Settings(_env_file=None, google_api_key="test-key", data_dir=tmp_path)


@pytest.fixture
def client(test_settings, fake_embeddings):
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_embeddings] = lambda: fake_embeddings
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
```

`backend/tests/test_documents_api.py`:
```python
def test_upload_pdf_returns_document_id_and_chunk_count(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        response = client.post(
            "/documents/upload",
            files={"file": ("sample.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "sample.pdf"
    assert body["chunk_count"] >= 1
    assert body["document_id"]


def test_upload_rejects_non_pdf_file(client):
    response = client.post(
        "/documents/upload",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
    )
    assert response.status_code == 400


def test_upload_rejects_corrupt_pdf(client):
    response = client.post(
        "/documents/upload",
        files={"file": ("broken.pdf", b"not a real pdf", "application/pdf")},
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_documents_api.py -v`
Expected: FAIL with `404` (route doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/main.py` — add these imports near the top (after the existing ones) and the route at the end of the file:
```python
import uuid

from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pypdf.errors import PdfReadError

from app import db
from app.config import Settings, get_settings
from app.dependencies import get_embeddings, get_vectorstore
from app.exceptions import ProviderUnavailableError
from app.schemas import DocumentUploadResponse
from app.services import document_service
```

```python
@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    vectorstore=Depends(get_vectorstore),
) -> DocumentUploadResponse:
    is_pdf = (file.content_type == "application/pdf") or file.filename.lower().endswith(".pdf")
    if not is_pdf:
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    document_id = uuid.uuid4().hex
    upload_dir = settings.data_dir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{document_id}_{file.filename}"
    file_path.write_bytes(await file.read())

    try:
        chunks = document_service.chunk_pdf(
            file_path, document_id, settings.chunk_size, settings.chunk_overlap
        )
    except PdfReadError as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}") from exc

    try:
        chunk_count = document_service.embed_and_store(vectorstore, chunks)
    except Exception as exc:
        file_path.unlink(missing_ok=True)
        raise ProviderUnavailableError("Gemini", str(exc)) from exc

    with db.get_connection(settings.data_dir) as conn:
        db.insert_document(conn, document_id, file.filename, str(file_path), chunk_count)

    return DocumentUploadResponse(document_id=document_id, filename=file.filename, chunk_count=chunk_count)
```

> Note: the broad `except Exception` around the embedding call is intentional here — it's the single point where any Gemini-side failure (network error, rate limit, bad key) gets converted into a consistent `503`. This is a deliberate simplification for a single-provider learning project, not a pattern to copy into code with multiple failure-prone dependencies.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_documents_api.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/conftest.py backend/tests/test_documents_api.py
git commit -m "feat: add POST /documents/upload endpoint"
```

---

### Task 10: GET /documents and DELETE /documents/{id} endpoints

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_documents_api.py`

**Interfaces:**
- Consumes: everything from Task 9, plus `document_service.delete_document_vectors` (Task 8), `db.list_documents`, `db.get_document`, `db.delete_document` (Task 6), `DocumentListResponse`, `DocumentListItem` (Task 4).
- Produces: `GET /documents` → `200` with `DocumentListResponse`; `DELETE /documents/{document_id}` → `204` on success, `404` if unknown.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_documents_api.py`:
```python
def test_list_documents_returns_uploaded_documents(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        client.post("/documents/upload", files={"file": ("sample.pdf", f, "application/pdf")})

    response = client.get("/documents")

    assert response.status_code == 200
    documents = response.json()["documents"]
    assert len(documents) == 1
    assert documents[0]["filename"] == "sample.pdf"


def test_list_documents_empty_when_none_uploaded(client):
    response = client.get("/documents")
    assert response.status_code == 200
    assert response.json()["documents"] == []


def test_delete_document_removes_it_from_list(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        upload_response = client.post(
            "/documents/upload", files={"file": ("sample.pdf", f, "application/pdf")}
        )
    document_id = upload_response.json()["document_id"]

    delete_response = client.delete(f"/documents/{document_id}")
    assert delete_response.status_code == 204

    list_response = client.get("/documents")
    assert list_response.json()["documents"] == []


def test_delete_unknown_document_returns_404(client):
    response = client.delete("/documents/does-not-exist")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_documents_api.py -v`
Expected: FAIL — `GET /documents` and `DELETE /documents/{id}` return `404` (routes don't exist yet)

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/main.py` — add `Path` to the existing imports (`from pathlib import Path`), add `DocumentListItem, DocumentListResponse` to the `app.schemas` import, and add these two routes after `upload_document`:
```python
@app.get("/documents", response_model=DocumentListResponse)
def list_documents(settings: Settings = Depends(get_settings)) -> DocumentListResponse:
    with db.get_connection(settings.data_dir) as conn:
        rows = db.list_documents(conn)
    return DocumentListResponse(
        documents=[
            DocumentListItem(
                document_id=row["document_id"],
                filename=row["filename"],
                uploaded_at=row["uploaded_at"],
                chunk_count=row["chunk_count"],
            )
            for row in rows
        ]
    )


@app.delete("/documents/{document_id}", status_code=204)
def delete_document(
    document_id: str,
    settings: Settings = Depends(get_settings),
    vectorstore=Depends(get_vectorstore),
) -> None:
    with db.get_connection(settings.data_dir) as conn:
        row = db.get_document(conn, document_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Document not found.")
        document_service.delete_document_vectors(vectorstore, document_id)
        Path(row["file_path"]).unlink(missing_ok=True)
        db.delete_document(conn, document_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_documents_api.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_documents_api.py
git commit -m "feat: add GET /documents and DELETE /documents/{id} endpoints"
```

---

### Task 11: Chat service — session history and grounded answering

**Files:**
- Create: `backend/app/services/chat_service.py`
- Test: `backend/tests/test_chat_service.py`

**Interfaces:**
- Consumes: `langchain_community.chat_message_histories.SQLChatMessageHistory`, `langchain_chroma.Chroma`, `langchain_core.language_models.BaseChatModel`.
- Produces: `get_session_history(db_path: Path, session_id: str) -> SQLChatMessageHistory`, `answer_question(vectorstore: Chroma, chat_model: BaseChatModel, history: SQLChatMessageHistory, question: str, k: int = 4) -> dict` returning `{"answer": str, "sources": [{"filename": str, "page": int}, ...]}`. `answer_question` also appends the human question and AI answer onto `history` as a side effect.

> Implementation note: LangChain's `RunnableWithMessageHistory` wrapper is deprecated as of this LangChain version (in favor of LangGraph persistence). This service uses `SQLChatMessageHistory` directly with manual `add_user_message`/`add_ai_message` calls instead — it still persists to SQLite exactly as the design spec requires, avoids the deprecated wrapper, and is more explicit about what's happening at each step, which suits the learning goal of this project.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_chat_service.py`:
```python
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.services import chat_service


def _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings):
    vectorstore = Chroma(
        collection_name="test-chat-documents",
        embedding_function=fake_embeddings,
        persist_directory=str(tmp_path / "chroma"),
    )
    vectorstore.add_documents(
        [Document(page_content="LangChain builds LLM apps.", metadata={"document_id": "d1", "filename": "a.pdf", "page": 1})],
        ids=["d1-0"],
    )
    return vectorstore


def test_answer_question_returns_answer_and_sources(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings)
    chat_model = FakeListChatModel(responses=["LangChain helps build LLM apps."])
    history = chat_service.get_session_history(tmp_path / "chat.db", "session-1")

    result = chat_service.answer_question(vectorstore, chat_model, history, "What is LangChain?")

    assert result["answer"] == "LangChain helps build LLM apps."
    assert result["sources"] == [{"filename": "a.pdf", "page": 1}]


def test_answer_question_persists_turn_to_history(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings)
    chat_model = FakeListChatModel(responses=["LangChain helps build LLM apps."])
    db_path = tmp_path / "chat.db"
    history = chat_service.get_session_history(db_path, "session-1")

    chat_service.answer_question(vectorstore, chat_model, history, "What is LangChain?")

    reloaded_history = chat_service.get_session_history(db_path, "session-1")
    assert len(reloaded_history.messages) == 2
    assert reloaded_history.messages[0].content == "What is LangChain?"
    assert reloaded_history.messages[1].content == "LangChain helps build LLM apps."


def test_answer_question_uses_history_on_second_turn(tmp_path, fake_embeddings):
    vectorstore = _make_vectorstore_with_one_chunk(tmp_path, fake_embeddings)
    chat_model = FakeListChatModel(
        responses=["First answer.", "standalone follow-up question", "Second answer."]
    )
    history = chat_service.get_session_history(tmp_path / "chat.db", "session-1")

    chat_service.answer_question(vectorstore, chat_model, history, "What is LangChain?")
    result = chat_service.answer_question(vectorstore, chat_model, history, "What about agents?")

    assert result["answer"] == "Second answer."
    assert len(history.messages) == 4


def test_get_session_history_creates_data_dir_if_missing(tmp_path):
    db_path = tmp_path / "nested" / "chat.db"
    history = chat_service.get_session_history(db_path, "session-1")
    assert history.messages == []
    assert db_path.parent.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.chat_service'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/services/chat_service.py`:
```python
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.chat_message_histories import SQLChatMessageHistory
from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

CONTEXTUALIZE_SYSTEM_PROMPT = (
    "Given a chat history and the latest user question, rephrase the "
    "question into a standalone question that can be understood without "
    "the chat history. Do not answer the question, just reformulate it "
    "if needed, and otherwise return it as-is."
)

QA_SYSTEM_PROMPT = (
    "You are an assistant that answers questions using only the provided "
    "context. If the context does not contain the answer, say you don't "
    "know. Keep answers concise.\n\nContext:\n{context}"
)


def get_session_history(db_path: Path, session_id: str) -> SQLChatMessageHistory:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return SQLChatMessageHistory(session_id=session_id, connection=f"sqlite:///{db_path}")


def _contextualize_question(chat_model: BaseChatModel, question: str, chat_history: list) -> str:
    if not chat_history:
        return question
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", CONTEXTUALIZE_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )
    chain = prompt | chat_model | StrOutputParser()
    return chain.invoke({"chat_history": chat_history, "question": question})


def _format_docs(docs) -> str:
    return "\n\n".join(doc.page_content for doc in docs)


def answer_question(
    vectorstore: Chroma,
    chat_model: BaseChatModel,
    history: SQLChatMessageHistory,
    question: str,
    k: int = 4,
) -> dict:
    standalone_question = _contextualize_question(chat_model, question, history.messages)

    retriever = vectorstore.as_retriever(search_kwargs={"k": k})
    retrieved_docs = retriever.invoke(standalone_question)
    context = _format_docs(retrieved_docs)

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", QA_SYSTEM_PROMPT),
            MessagesPlaceholder("chat_history"),
            ("human", "{question}"),
        ]
    )
    qa_chain = qa_prompt | chat_model | StrOutputParser()
    answer = qa_chain.invoke(
        {"context": context, "chat_history": history.messages, "question": question}
    )

    history.add_user_message(question)
    history.add_ai_message(answer)

    sources = [
        {"filename": doc.metadata.get("filename", "unknown"), "page": doc.metadata.get("page", 0)}
        for doc in retrieved_docs
    ]
    return {"answer": answer, "sources": sources}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_service.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/chat_service.py backend/tests/test_chat_service.py
git commit -m "feat: add chat service with history-aware retrieval and answering"
```

---

### Task 12: POST /chat endpoint

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/conftest.py` (add `get_chat_model` to the overridable imports)
- Test: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `chat_service.get_session_history`, `chat_service.answer_question` (Task 11), `db.get_db_path`, `db.list_documents` (Task 6), `get_chat_model`, `get_vectorstore` (Task 5), `ChatRequest`, `ChatResponse`, `SourceCitation` (Task 4).
- Produces: `POST /chat` → `200` with `ChatResponse`; `400` if no documents are indexed; `503` if `answer_question` raises.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_chat_api.py`:
```python
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from app.dependencies import get_chat_model


def _upload_sample(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        return client.post("/documents/upload", files={"file": ("sample.pdf", f, "application/pdf")})


def test_chat_without_documents_returns_400(client):
    response = client.post("/chat", json={"question": "What is this about?"})
    assert response.status_code == 400


def test_chat_returns_answer_with_sources(client, sample_pdf_path):
    _upload_sample(client, sample_pdf_path)
    client.app.dependency_overrides[get_chat_model] = lambda: FakeListChatModel(
        responses=["LangChain helps build LLM apps."]
    )

    response = client.post("/chat", json={"question": "What is LangChain?"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "LangChain helps build LLM apps."
    assert body["session_id"]
    assert len(body["sources"]) >= 1


def test_chat_reuses_provided_session_id(client, sample_pdf_path):
    _upload_sample(client, sample_pdf_path)
    client.app.dependency_overrides[get_chat_model] = lambda: FakeListChatModel(
        responses=["First answer.", "standalone question", "Second answer."]
    )

    first = client.post("/chat", json={"question": "What is LangChain?"})
    session_id = first.json()["session_id"]

    second = client.post("/chat", json={"question": "What about agents?", "session_id": session_id})

    assert second.status_code == 200
    assert second.json()["session_id"] == session_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_api.py -v`
Expected: FAIL — `POST /chat` returns `404` (route doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/main.py` — add `get_chat_model` to the `app.dependencies` import, add `chat_service` to the `app.services` import, add `ChatHistoryResponse, ChatMessageItem, ChatRequest, ChatResponse, SourceCitation` to the `app.schemas` import, and add this route after `delete_document`:
```python
@app.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    chat_model=Depends(get_chat_model),
    vectorstore=Depends(get_vectorstore),
) -> ChatResponse:
    with db.get_connection(settings.data_dir) as conn:
        documents = db.list_documents(conn)
    if not documents:
        raise HTTPException(status_code=400, detail="No documents indexed yet. Upload a PDF first.")

    session_id = request.session_id or uuid.uuid4().hex
    history = chat_service.get_session_history(db.get_db_path(settings.data_dir), session_id)

    try:
        result = chat_service.answer_question(
            vectorstore, chat_model, history, request.question, settings.retrieval_k
        )
    except Exception as exc:
        raise ProviderUnavailableError("Gemini", str(exc)) from exc

    return ChatResponse(
        answer=result["answer"],
        sources=[SourceCitation(**source) for source in result["sources"]],
        session_id=session_id,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_api.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_chat_api.py
git commit -m "feat: add POST /chat endpoint"
```

---

### Task 13: GET /chat/{session_id}/history endpoint

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_chat_api.py`

**Interfaces:**
- Consumes: `chat_service.get_session_history` (Task 11), `ChatHistoryResponse`, `ChatMessageItem` (Task 4).
- Produces: `GET /chat/{session_id}/history` → `200` with `ChatHistoryResponse`; `404` if the session has no messages.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_chat_api.py`:
```python
def test_get_history_returns_messages_for_known_session(client, sample_pdf_path):
    _upload_sample(client, sample_pdf_path)
    client.app.dependency_overrides[get_chat_model] = lambda: FakeListChatModel(
        responses=["LangChain helps build LLM apps."]
    )
    chat_response = client.post("/chat", json={"question": "What is LangChain?"})
    session_id = chat_response.json()["session_id"]

    response = client.get(f"/chat/{session_id}/history")

    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == session_id
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "human"
    assert body["messages"][1]["role"] == "ai"


def test_get_history_returns_404_for_unknown_session(client):
    response = client.get("/chat/nonexistent-session/history")
    assert response.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_chat_api.py -v`
Expected: FAIL — `GET /chat/{session_id}/history` returns `404` for both cases indiscriminately because the route doesn't exist yet (the two new tests fail: the first expects `200`)

- [ ] **Step 3: Write minimal implementation**

Modify `backend/app/main.py` — add this route after `chat`:
```python
@app.get("/chat/{session_id}/history", response_model=ChatHistoryResponse)
def get_chat_history(session_id: str, settings: Settings = Depends(get_settings)) -> ChatHistoryResponse:
    history = chat_service.get_session_history(db.get_db_path(settings.data_dir), session_id)
    if not history.messages:
        raise HTTPException(status_code=404, detail="Session not found.")
    return ChatHistoryResponse(
        session_id=session_id,
        messages=[ChatMessageItem(role=m.type, content=m.content) for m in history.messages],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_chat_api.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/tests/test_chat_api.py
git commit -m "feat: add GET /chat/{session_id}/history endpoint"
```

---

### Task 14: Integration tests, README, and full-suite verification

**Files:**
- Create: `backend/tests/integration/__init__.py`
- Create: `backend/tests/integration/test_gemini_integration.py`
- Create: `backend/README.md`

**Interfaces:**
- Consumes: everything above. This task adds no new production code — it validates the whole stack against the real Gemini API and documents how to run the project.

- [ ] **Step 1: Write the integration tests**

`backend/tests/integration/__init__.py`: (empty file)

`backend/tests/integration/test_gemini_integration.py`:
```python
"""
Tests in this file call the real Gemini API. They require a valid
GOOGLE_API_KEY in the environment and network access, and are excluded from
the default `pytest` run (see pytest.ini). Run them explicitly with:

    pytest -m integration tests/integration -v
"""

import pytest

from app.config import Settings
from app.dependencies import get_chat_model, get_embeddings, get_vectorstore
from app.services import chat_service, document_service


@pytest.fixture
def real_settings(tmp_path):
    return Settings(data_dir=tmp_path)  # picks up GOOGLE_API_KEY from the real environment


@pytest.mark.integration
def test_upload_and_ask_round_trip_with_real_gemini(real_settings, sample_pdf_path):
    embeddings = get_embeddings(real_settings)
    vectorstore = get_vectorstore(embeddings, real_settings)
    chat_model = get_chat_model(real_settings)

    chunks = document_service.chunk_pdf(sample_pdf_path, document_id="integration-doc")
    chunk_count = document_service.embed_and_store(vectorstore, chunks)
    assert chunk_count >= 1

    history = chat_service.get_session_history(real_settings.data_dir / "chat.db", "integration-session")
    result = chat_service.answer_question(vectorstore, chat_model, history, "What is this document about?")

    assert result["answer"]
    assert len(result["sources"]) >= 1
```

- [ ] **Step 2: Run the integration test manually (requires a real GOOGLE_API_KEY)**

```bash
cd backend
cp .env.example .env
# edit .env and paste in a real Gemini API key from https://aistudio.google.com/apikey
export $(grep -v '^#' .env | xargs)
pytest -m integration tests/integration -v
```
Expected: 1 passed, hitting the real Gemini API. (If you don't have a key yet, skip this step for now — the default test suite doesn't need it.)

- [ ] **Step 3: Write the README**

`backend/README.md`:
```markdown
# Document Q&A API — Backend

FastAPI + LangChain backend for uploading PDFs and asking grounded,
multi-turn questions about them, using Google Gemini's free API tier for
both embeddings and chat generation.

## Setup

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Get a free Gemini API key from https://aistudio.google.com/apikey.

3. Copy `.env.example` to `.env` and fill in your key:
   ```bash
   cp .env.example .env
   ```

4. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

5. Open http://localhost:8000/docs for the interactive Swagger UI, where
   you can upload a PDF via `/documents/upload` and then ask questions via
   `/chat`.

## Running tests

Fast suite (no API key or network required — uses LangChain's fake
embeddings/chat model):
```bash
pytest
```

Integration suite (hits the real Gemini API, needs `GOOGLE_API_KEY` set):
```bash
pytest -m integration tests/integration -v
```

## Known limitations (by design, for this learning project)

- Single-user, no authentication.
- PDF only.
- The Chroma vector store is reopened on every request rather than kept as
  a long-lived singleton, which is simple but could hit SQLite locking
  issues under concurrent load — fine for local/demo use, not for
  production traffic.
- Gemini-side failures are caught broadly (any exception during an
  embedding or generation call becomes a 503) rather than distinguishing
  specific error types.
```

- [ ] **Step 4: Run the full default suite to verify everything passes together**

```bash
cd backend
pytest -v
```
Expected: all tests from Tasks 1–13 pass (around 35+ tests), zero requiring network access, in well under 30 seconds.

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration backend/README.md
git commit -m "test: add Gemini integration test suite and README"
```

---

## Self-Review Notes

- **Spec coverage:** all five endpoints, PDF-only support, error codes (400/422/503/404), Gemini-only provider, ChromaDB persistence, SQLite chat history, and the mocked-default/integration-marked test split from the design spec are each covered by a task above.
- **Type/signature consistency checked:** `document_service.chunk_pdf` → `document_service.embed_and_store` → `main.upload_document` all agree on `Document.metadata` shape (`document_id`, `filename`, `page`); `chat_service.answer_question`'s return dict (`answer`, `sources`) matches exactly what `main.chat` unpacks into `ChatResponse`/`SourceCitation`; `db.*` function names and the `sqlite3.Row` column names (`document_id`, `filename`, `file_path`, `uploaded_at`, `chunk_count`) are used identically in Tasks 6, 9, and 10.
- **No placeholders:** every step above contains complete, runnable code — verified interactively against the actual pinned package versions (LangChain 1.3.15, langchain-chroma 1.1.0, chromadb 1.5.9, langchain-google-genai 4.3.4) before writing this plan, including the `RunnableWithMessageHistory` deprecation discovery that shaped Task 11's design.
