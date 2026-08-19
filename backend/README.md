# Document Q&A API — Backend

FastAPI + LangChain backend for uploading PDFs and asking grounded,
multi-turn questions about them, using Google Gemini's free API tier for
both embeddings and chat generation.

## Setup

1. Create a virtual environment and install dependencies:

   macOS/Linux:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

   Windows (PowerShell):
   ```powershell
   python -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

   Always install into a virtual environment, not your global Python — this
   project's pinned versions can conflict with unrelated tools installed
   globally on your machine.

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
