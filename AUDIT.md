# docqa-api — Senior Engineering Audit

**Scope:** full repository (`backend/` FastAPI + LangChain + Gemini + Chroma +
SQLite, `frontend/` React 19 + Vite).
**Date:** 2026-08-19
**Context that shapes every finding below:** this is an explicitly documented
single-user, no-auth, PDF-only **learning/portfolio project** ("Known Limitations
(by design)" in both root and backend `README.md`). Findings that fall inside that
declared scope (no auth, single shared collection, Chroma reopened per request)
are called out once, here, as accepted trade-offs — not repeated as Critical
findings throughout. Findings that are bugs *within* that scope (e.g. a real path
traversal vulnerability, or cross-session history leakage that goes beyond what
"no auth" already implies) are flagged at full severity, because they'd be bugs in
a single-user demo just as much as in a production system.

---

## Executive Summary

**Overall assessment:** For a project explicitly scoped as a two-weekend learning
exercise to pair FastAPI with LangChain, the code is unusually clean — small
files, no dead code, no TODO-litter, consistent patterns, and a genuinely good
instinct for using LangChain's LCEL chains rather than hand-rolling prompt
plumbing. The backend has real test coverage (12 test files covering config, DB,
DI, chunking, storage retry logic, chat service, and both API surfaces) and the
frontend has at least a tested API-parsing layer plus a manual smoke script. The
`README.md` files are honest about the project's limitations rather than
overselling it — that's rare and worth calling out.

**Strongest parts:**
- Clean separation of `main.py` (routes) / `services/` (business logic) /
  `dependencies.py` (DI) / `db.py` (persistence) — small, single-purpose modules.
- Rate-limit retry logic in `document_service.embed_and_store` is a thoughtful,
  tested response to a real problem (Gemini free-tier 429s).
- `.env` handling is correct everywhere: gitignored, never committed, secrets
  passed via `fly secrets set` rather than baked into `fly.toml`.
- Frontend error/loading/empty states are handled consistently across all three
  components, with real `role="alert"` usage (not just visual styling).
- The `ChatWindow.jsx` history-restore effect has a comment explaining a genuine
  bug the author hit and fixed — the right kind of comment (why, not what).

**Biggest weaknesses:**
- One confirmed, exploitable security bug: unsanitized upload filenames allow
  path traversal on file write (and later delete). See Critical Finding #1.
- Zero logging anywhere in the backend. Combined with blanket `except Exception`
  handling around every Gemini call, there is no way to tell — after the fact —
  whether a 503 was a bad API key, a quota exhaustion, a network blip, or a typo'd
  model name.
- No CI. Both test suites (`pytest`, `npm test`) exist and pass locally but
  nothing runs them automatically on push/PR.
- Chat retrieval is not scoped to a document or session even though the
  underlying Chroma `.get(where=...)` filter already proves metadata filtering
  works (it's used for deletion) — this is a one-line fix, not a design constraint.

**Biggest risks (if this project ever moves beyond solo/local use):**
1. The path-traversal upload bug (Critical #1) is a real vulnerability the moment
   this API is reachable by anyone other than its owner — which the Fly.io deploy
   config in the repo explicitly enables.
2. Session IDs are bearer tokens with no ownership check — anyone who obtains or
   guesses another session's ID gets that session's full chat history.
3. The Chroma-per-request + SQLite-file-history design will start throwing
   `database is locked` errors under any real concurrent load; this is
   self-documented but worth flagging as the top scalability blocker if traffic
   ever exceeds "one person testing it."

**Most important improvements, in order:** fix the path traversal bug, add
logging, scope chat retrieval by document/session, add basic session ownership (or
explicitly document why it's out of scope), wire up CI. Full reasoning for this
ordering is in the [Recommended Refactoring Plan](#recommended-refactoring-plan)
and [final ranked list](#if-you-were-taking-ownership-the-first-10-things)
at the end of this document.

---

## Architecture Assessment

```
Client (React SPA)
   │  fetch, VITE_API_URL
   ▼
FastAPI app (single main.py, 6 routes, no router split)
   │
   ├── POST /documents/upload ──► document_service.chunk_pdf (PyPDFLoader + splitter)
   │                          ──► document_service.embed_and_store (Chroma.add_documents, retried)
   │                          ──► db.insert_document (SQLite: documents table)
   │
   ├── GET/DELETE /documents ──► db.list_documents / db.delete_document + vectorstore delete
   │
   └── POST /chat ──► chat_service.answer_question
                        ├── contextualize (LCEL chain #1, only if history exists)
                        ├── retrieve (Chroma similarity search, k=4, unscoped)
                        ├── generate (LCEL chain #2)
                        └── persist to SQLChatMessageHistory (same SQLite file)

Storage: backend/data/{app.db (SQLite), chroma/ (Chroma+HNSW), uploads/ (raw PDFs)}
```

This is a textbook "modular monolith, small scale" layout and it's the right
architecture for what the project is — there is no case here for splitting into
services, adding a message queue, or introducing a real database server. The
separation of `main.py` / `services/` / `dependencies.py` / `db.py` is already
doing the useful part of "layered architecture" (routes stay thin, business logic
is testable in isolation) without adding framework weight.

Two structural choices are explicitly flagged by the project's own README as
scale limits, and I agree with both the diagnosis and the decision not to fix them
yet:
- **Chroma reconstructed per-request** (`app/dependencies.py:24-34`) rather than
  as an app-lifespan singleton. Simple, correct for one worker/one user, will
  degrade under concurrency (SQLite locking inside Chroma's own persistence).
- **No migrations framework** for the one SQLite table (`app/db.py`,
  `CREATE TABLE IF NOT EXISTS` on every connection). Fine at one table; would need
  Alembic (or similar) the moment a second migration is needed.

One structural gap *not* mentioned in the README: **all 6 routes live directly on
the `FastAPI()` instance in `main.py`** with no `APIRouter` split. At 153 lines
this is still readable, but the moment a second resource group is added (e.g.
session management beyond chat), an `APIRouter`-per-resource split
(`routers/documents.py`, `routers/chat.py`) would keep `main.py` from becoming a
dumping ground. Not urgent today — flagging as a Phase 3 item, not Phase 1.

---

## Critical Findings

### 🔴 Critical #1 — Path traversal on PDF upload → arbitrary file write/delete

**File:** [`backend/app/main.py:60`](backend/app/main.py#L60)

```python
file_path = upload_dir / f"{document_id}_{file.filename}"
file_path.write_bytes(await file.read())
```

**Why:** `file.filename` comes directly from the multipart upload's
client-supplied filename header and is never sanitized, validated, or reduced to
a basename. Python's `pathlib` `/` operator parses `/` characters *inside* the
right-hand string as path separators — it does not treat the string as one atomic
path component. A filename like `../../../../tmp/evil.pdf` (or, on the app's
actual deployment target, a path aimed at any writable location under the Fly.io
volume) produces a real path outside `upload_dir`. The written path is also
persisted verbatim into SQLite (`db.insert_document(..., str(file_path), ...)`)
and later reused unchanged for deletion
([`main.py:111`](backend/app/main.py#L111): `Path(row["file_path"]).unlink(...)`),
so the same primitive gives an attacker-controlled **arbitrary-path delete** as
well as write, once they know or can enumerate a `document_id`.

This is exploitable by anyone who can reach the `/documents/upload` endpoint —
which, per the project's own no-auth design, is anyone who can reach the API at
all. It is independent of the "no auth" scope decision: even a trusted single
user could accidentally trigger it via a browser upload of a file with an unusual
name, and a malicious actor could deliberately target it.

**Recommendation:** sanitize before building the path — take only the basename
and strip any remaining traversal sequences:
```python
from pathlib import PurePosixPath

safe_name = PurePosixPath(file.filename).name  # drops any directory components
file_path = upload_dir / f"{document_id}_{safe_name}"
```
Add a regression test with a crafted filename (e.g.
`"../../../../etc/evil.pdf"`) asserting the resulting file stays inside
`upload_dir`. This is a Quick Win — see that section.

**Priority:** Critical. **Effort:** ~15 minutes (fix + test). **Risk of
change:** none — this only narrows accepted input.

---

### 🟠 High #2 — Chat sessions have no ownership; any session_id can be read/continued

**File:** [`backend/app/main.py:127`](backend/app/main.py#L127),
[`backend/app/main.py:144-152`](backend/app/main.py#L144-L152)

**Why:** `POST /chat` accepts a client-supplied `session_id` and, if present,
appends to that session's history with no check that the caller "owns" it
(there's no concept of ownership at all — no cookie, no token, nothing binding a
session to a client). `GET /chat/{session_id}/history` will return any session's
full message history to anyone who supplies its ID. Session IDs are `uuid4().hex`
— not guessable in practice — but they are returned in every `/chat` response
body, logged nowhere, and would appear in browser history, proxy logs, or
`Referer` headers on any client that puts them in a URL. This is a step beyond
what "no auth" already implies: the README's "no auth" limitation reads as "no
login, single user," not "any two conversations happening against this instance
can read each other's history by ID."

**Recommendation:** either (a) explicitly document this as an accepted risk of
the single-user design (cheapest fix — one README line), or (b) if the project
ever adds a second concurrent user, bind sessions to a lightweight
per-browser identifier (e.g. an httpOnly cookie set on first `/chat` call,
checked against a `sessions` table) before trusting a client-supplied
`session_id`. Given the project's stated scope, (a) is the right call today —
I'd document it, not fix it, unless multi-user use is actually planned.

**Priority:** High if multi-user use is ever intended; otherwise a documentation
gap, not a code gap. **Effort:** 5 minutes (docs) or ~2 hours (real fix).

---

### 🟠 High #3 — Chat retrieval is not scoped per document, despite the vectorstore already supporting the filter

**File:** [`backend/app/services/chat_service.py:55`](backend/app/services/chat_service.py#L55)

```python
retriever = vectorstore.as_retriever(search_kwargs={"k": k})
```

**Why:** every chat question retrieves from the entire shared Chroma
`"documents"` collection across *all* uploaded PDFs, with no `where` filter. This
matters for two reasons: (1) relevance — if a user has uploaded 5 unrelated PDFs,
a question about PDF #1 can retrieve and get "grounded" in irrelevant chunks from
PDF #4; (2) it's not a hard problem here — `document_service.delete_document_vectors`
([`document_service.py:70`](backend/app/services/document_service.py#L70)) already
proves Chroma's metadata filter works (`vectorstore.get(where={"document_id":
document_id})`), so the retrieval path could use the identical filter mechanism
and currently just doesn't.

**Recommendation:** since the API has no concept of "which document is this
question about" today, the realistic fix is either (a) let `ChatRequest` accept
an optional `document_id` to scope retrieval when the frontend knows which doc is
active, or (b) accept the cross-document retrieval as intentional ("ask questions
across your whole library") and say so in the README — right now it reads as an
oversight rather than a decision, since nothing states it. I'd lean toward
documenting current behavior as intentional ("multi-document Q&A") since the
frontend's UI doesn't currently let a user pick "this document only" — but flag it
because it's currently ambiguous rather than decided.

**Priority:** High as a documentation/product-decision gap; Medium as a code
change once the decision is made.

---

## Code Quality Findings

- **`main.py` DB-connection boilerplate repeated 4×**: `with
  db.get_connection(settings.data_dir) as conn:` appears identically in upload,
  list, delete, and chat handlers
  ([`main.py:77`](backend/app/main.py#L77),
  [`85`](backend/app/main.py#L85),
  [`106`](backend/app/main.py#L106),
  [`122`](backend/app/main.py#L122)). Low severity — it's consistent, not
  buggy — but since the rest of the app is DI-based
  (`Depends(get_settings)`, `Depends(get_vectorstore)`), a matching `Depends(get_db_connection)`
  would fit the existing style and remove the duplication. **Quick win.**
- **LCEL chains rebuilt per-call**: both `_contextualize_question` and
  `answer_question` in `chat_service.py` construct a fresh `ChatPromptTemplate`
  and pipe a new chain on every invocation rather than building them once at
  module scope and reusing across calls. Minor inefficiency (prompt-template
  construction is cheap), not a bug — worth doing only opportunistically, not a
  dedicated task.
- **Bespoke string-matching for rate-limit detection**
  (`document_service._is_rate_limit_error`, checks `"RESOURCE_EXHAUSTED"`/`"429"`
  substrings in `str(exc)`): fragile if the Google SDK changes its error message
  format, since there's no typed exception being caught. Works today, tested
  today, but is the kind of thing that silently stops retrying if a dependency
  upgrade changes error text. Worth a comment noting the assumption, or catching
  the SDK's actual `google.api_core.exceptions.ResourceExhausted` type if
  `langchain-google-genai` surfaces it (would need to verify at the dependency
  version pinned).
- **`ChatWindow.jsx` (169 lines) mixes four concerns**: message-list rendering,
  composer/input handling, session persistence, and the source-citation modal are
  all in one component — the largest file in `frontend/src`. Splitting into
  `MessageList`, `Composer`, and `SourceCitationModal` would make the a11y fix in
  Finding #4 easier to land in one place and improve testability.
- **List keys use array index** (`ChatWindow.jsx:95,112` — `key={index}`): low
  risk today since messages/sources are append-only, never reordered, but still
  worth using a stable id (e.g. a counter or uuid assigned on message creation) if
  the list ever supports edit/delete/retry.
- **Duplicated localStorage read**: `sessionId` state is initialized from
  `localStorage.getItem(SESSION_STORAGE_KEY)` and the mount `useEffect` re-reads
  the same key again instead of reusing the already-initialized state value
  (`ChatWindow.jsx:11,24`). Harmless (the effect is intentionally one-time-only,
  well-commented), but a stray leftover worth tidying during the component split.

---

## Security Findings

**Confirmed:**
- Path traversal on upload — Critical #1 above.
- No authentication anywhere (`README.md`-documented, accepted for current scope;
  noted here for completeness, not re-flagged as a defect).
- No rate limiting / no request size limits on `/documents/upload` — any caller
  can upload arbitrarily large or numerous PDFs, consuming disk and Gemini quota.
  Acceptable for a solo demo; would need addressing before any public deployment.
- CORS is configured with a real origin allowlist (`allow_origins=settings.allowed_origins`,
  not `["*"]`) — this is done correctly, worth noting as a positive, not a gap.

**Potential / needs verification if this is ever deployed publicly:**
- Session-history read without ownership check — High #2 above.
- The pinned Gemini model names in `backend/app/config.py:9-10`
  (`gemini-3.6-flash`, `gemini-embedding-2-preview`) are past this review's
  knowledge cutoff to confirm against Google's current model catalog (today's
  date is 2026-08-19; my training data ends January 2026) — **verify these
  resolve to real, currently-available models before relying on `.env.example`'s
  defaults for a fresh deploy**, rather than assuming they're correct or
  assuming they're wrong.
- No `.dockerignore`-driven exclusion review was done beyond confirming `.env` is
  excluded from the Docker build context — worth a quick check that
  `backend/data/` (which can contain real uploaded PDFs locally, confirmed
  present on disk during this audit) is never accidentally included in a build
  context or committed.

**General improvements (not vulnerabilities):**
- Dockerfile runs as root (no `USER` directive) — standard hardening
  recommendation for any container, low urgency given no privileged operations
  occur inside it.

---

## Performance Findings

- **Blocking `time.sleep()` inside a request handler**
  (`document_service.embed_and_store`, up to 3 attempts, delay parsed from
  Gemini's own "retry in Ns" message + 1s buffer, or `10.0 × attempt` as
  fallback): under FastAPI's default sync-def threadpool execution this ties up
  one worker thread per retrying upload for up to ~30+ seconds. With the single
  `uvicorn` worker configured in the Dockerfile, a handful of concurrent
  rate-limited uploads could exhaust the threadpool and stall unrelated requests
  (including `/health`, which Fly's healthcheck polls every 30s). **Better
  approach:** if this project ever runs under real concurrent load, swap to an
  async sleep (`asyncio.sleep`) with an async-compatible embedding call, or move
  retry scheduling to a background task queue. **Expected benefit:** requests no
  longer block each other during Gemini rate-limit backoff. Not urgent for
  solo/local use — flagging for when/if concurrency becomes real.
- **Chroma reopened per request** (`dependencies.py:24-34`): each request pays
  the cost of re-initializing a `Chroma` client (opening its persistent SQLite
  file) rather than reusing a long-lived instance. Already self-documented in
  `backend/README.md` as a known limitation; the fix is a FastAPI `lifespan`-scoped
  singleton, which is a reasonable Phase 2 item once the path-traversal fix lands.
- No N+1 query patterns found — the SQLite access layer (`db.py`) does simple,
  single-table, single-query operations; no query loops.
- No frontend performance concerns worth flagging at this scale — no unnecessary
  re-renders identified, no large bundle-size red flags (React 19 + a handful of
  small deps, no heavy UI framework).

---

## Database Findings

- Single SQLite file (`data/app.db`) serves two purposes: the explicit
  `documents` table (`app/db.py`) and, separately, LangChain's
  `SQLChatMessageHistory`-managed message table (`app/services/chat_service.py:25`).
  These are two different code paths writing to the same file with no shared
  schema-ownership story — not currently a problem (LangChain manages its own
  table name/schema), but worth knowing if a migration tool is ever introduced,
  since it would need to account for a table it doesn't own.
- No indexes beyond the implicit `document_id` primary key — appropriate at
  current scale (a handful of rows in a demo project); would need revisiting only
  if this ever stored thousands of documents with frequent lookups.
- No migrations framework (`CREATE TABLE IF NOT EXISTS` inline in `db.py`) — fine
  for one table; the moment a second schema change is needed (e.g. adding a
  column), this becomes error-prone for anyone with an existing local `app.db`.
  Recommend introducing a minimal migration approach (even a manual
  `ALTER TABLE` guarded by a `PRAGMA user_version` check) before the second schema
  change, not before.
- Chroma's persistence (`data/chroma/`) is file-based and per-collection
  (hardcoded `"documents"` collection name) — appropriate for the project's
  scale; no networked vector DB is warranted here.

---

## API Findings

- Endpoint design is small, consistent, and RESTful enough for its size (6
  routes, correct HTTP methods, correct status codes — 204 on delete, 404 for
  missing resources, 422 for unparseable PDFs, 400 for missing required state).
- No pagination on `GET /documents` — a non-issue at current scale (a demo user
  uploads a handful of PDFs), would need addressing only if document counts grow
  large.
- No API versioning (no `/v1` prefix) — reasonable to skip for an unreleased
  learning project; worth adding before any public API contract is made.
- Response bodies are consistently typed via Pydantic models
  (`app/schemas.py`) — good practice, gives the Swagger docs real value.
- Error responses are consistent in shape (`{"detail": "..."}`, FastAPI's
  default) across both `HTTPException` paths and the custom
  `ProviderUnavailableError` handler — the frontend's `parseResponse()` correctly
  relies on this consistency.

---

## Frontend Findings

- **🟡 Medium — Source-citation modal lacks dialog accessibility semantics**
  ([`ChatWindow.jsx:146-166`](frontend/src/components/ChatWindow.jsx#L146-L166)):
  no `role="dialog"`, `aria-modal="true"`, `aria-labelledby`, focus trap, or
  `Escape`-key handler. Keyboard-only and screen-reader users can open the modal
  but have a materially worse experience closing/navigating it than mouse users.
  **Fix:** add the ARIA attributes, trap focus on open (move focus to the modal,
  restore on close), and add an `Escape` keydown listener. Worth doing as part of
  the `ChatWindow.jsx` split (see Code Quality) since it's the same code region.
- **🟡 Medium — Zero responsive/mobile styling**: `frontend/src/App.css` (614
  lines) contains no `@media` queries at all; the sidebar is a hardcoded
  `width: 296px` with no collapse behavior. The app will not adapt to narrow
  viewports. Reasonable to defer if this is desktop-only for now, but worth a
  README note if that's intentional.
- **🟢 Low — `ChatWindow.jsx` is doing too much** (see Code Quality above) —
  refactor candidate, not a bug.
- **🟢 Low — Dead asset**: `frontend/src/assets/vite.svg` (default Vite template
  logo) is never imported anywhere in `src/` — delete it.
- **🟢 Low — Playwright as a devDependency for one unwired manual script**:
  `smoke-test.mjs` is a real, useful smoke check (mocks Gemini calls, verifies
  upload→list, chat→sources, session persistence in `localStorage`), but it's not
  wired into CI (there is no CI) and one of its own assertions is silently
  swallowed (`smoke-test.mjs:50`, `.catch(() => {})` around the file-upload
  interaction) — meaning the actual click-to-upload flow is never really
  exercised even when the script runs. Either wire it into CI to justify the
  ~300MB Playwright dependency, or note in the README that it's a manual-only
  check by design.
- **Positive, worth keeping**: `react-markdown` + `remark-gfm` rather than
  `dangerouslySetInnerHTML` for rendering AI-generated answers
  ([`ChatWindow.jsx:104`](frontend/src/components/ChatWindow.jsx#L104)) — the
  right call for AI-generated content, avoids a raw-HTML/XSS footgun.
- **Positive, worth keeping**: consistent loading/error/empty-state handling
  across `DocumentList.jsx`, `UploadPanel.jsx`, and `ChatWindow.jsx`, with real
  `role="alert"` usage — this is a pattern worth preserving as the app grows, not
  something to refactor away.

---

## Backend Findings

Covered in depth above (Architecture, Critical/High Findings, Performance,
Database). Summary of what's *not* already covered elsewhere:

- **Zero logging anywhere** in `backend/app/*.py` — no `logging` module usage at
  all. Combined with the blanket `except Exception → 503` pattern in both
  `/documents/upload` and `/chat`
  ([`main.py:71-75`](backend/app/main.py#L71-L75),
  [`main.py:130-135`](backend/app/main.py#L130-L135)), there is currently no way
  to distinguish, after the fact, whether a given 503 was a bad API key, quota
  exhaustion, a network error, or a malformed model name — the README already
  acknowledges the *error-granularity* problem but the *observability* problem
  compounds it. **This is the single highest-leverage backend improvement**: even
  minimal `logging.exception(...)` calls at each broad `except Exception` site
  would make every other reliability issue in this report dramatically easier to
  diagnose in practice. **Quick win.**
- One custom exception (`ProviderUnavailableError`) with one global handler is a
  clean, idiomatic FastAPI pattern — no complaints, just noting there's no
  catch-all handler for genuinely unexpected exceptions (e.g. a bug in `db.py`),
  which would currently surface as a raw unhandled 500. Acceptable at this scale;
  add a catch-all only if unhandled 500s actually start occurring.

---

## AI/ML Findings

This project's "ML" surface is thin by design — it uses Gemini as a hosted
embedding + chat API via LangChain, with no local model training, no evaluation
pipeline, and no fine-tuning. The relevant checks from a RAG-pipeline perspective:

- **Preprocessing consistency between "training" and inference "**: N/A in the
  traditional ML sense (no training), but the equivalent concern —
  chunking-at-index-time vs. retrieval-at-query-time — is consistent: the same
  `RecursiveCharacterTextSplitter` config (`chunk_size`/`chunk_overlap` from
  `Settings`) is used once at upload time, and retrieval just queries the
  resulting embedded chunks with no separate/divergent preprocessing path. No
  train/inference skew risk here since there's no separate training step.
- **Grounding / hallucination control**: the QA system prompt explicitly
  instructs the model to answer "using only the provided context" and to say it
  doesn't know otherwise (`chat_service.py:16-19`) — a reasonable, standard
  RAG-grounding prompt. No verification step confirms the model actually
  complies (e.g. no citation-checking or context-overlap scoring on the
  answer) — acceptable for a demo project; would matter more if answer accuracy
  were a product requirement rather than a portfolio feature.
- **Retrieval quality**: fixed `k=4`, no reranking, no MMR (maximal marginal
  relevance) diversity, no dedup beyond the final `(filename, page)` source dedup
  (which dedupes *citations*, not retrieved chunks feeding the prompt) — standard
  "naive RAG" setup, appropriate for a learning project demonstrating the concept
  end-to-end rather than optimizing retrieval quality.
- **Retrieval scope** — see High Finding #3 (not scoped per document).
- **Error handling during inference**: broad `except Exception` around both
  embedding and generation calls (already covered under Backend Findings) —
  applies equally to the "ML" calls as to any other Gemini API call.

Nothing here suggests a scientifically or technically unsound approach — it's a
correctly-implemented, appropriately-scoped "naive RAG" pipeline for a learning
project.

---

## Testing Findings

**Backend (`backend/tests/`, 12 files)**: genuinely solid coverage for the
project's size — config, DB CRUD, DI wiring, chunking metadata, storage retry
logic (including rate-limit retry success/exhaustion paths), chat service
behavior (multi-turn, source dedup), both API surfaces (documents, chat), the
custom exception handler, and schema validation. A gated integration test
(`tests/integration/test_gemini_integration.py`, `@pytest.mark.integration`,
excluded by default) covers a real Gemini round-trip without requiring API
access for the default `pytest` run — a good pattern.

**What's missing:**
- No test exercises the 503 path **end-to-end through the real endpoint wiring**
  — `test_exceptions.py` only tests the handler in isolation against a throwaway
  app, not `/documents/upload` or `/chat` with a mocked-to-fail dependency.
- No regression test for the path-traversal bug (Critical #1) — add one alongside
  the fix.
- No test asserting the cross-session history read gap (High #2) — even just a
  test that documents current behavior would make the trade-off explicit and
  regression-proof if it's later "fixed" unintentionally.
- No CORS-behavior test.
- No concurrency/locking test for the "Chroma reopened per request" design — hard
  to test meaningfully without real load, reasonable to skip for now.

**Frontend**: `api.js`'s `parseResponse()` has 4 solid `node:test` cases (success,
JSON error, non-JSON error fallback, 204). That's the *only* automated frontend
test. `smoke-test.mjs` is a manual Playwright script, not wired into any test
runner's assertions (imperative `throw`/`process.exit(1)` rather than
`expect(...)`), and not run in CI.

**No CI exists in this repository at all** — no `.github/workflows/`. Both
`pytest` and `npm test` pass locally today but nothing prevents a future change
from silently breaking either suite. **This is the most practical testing
improvement available**: a minimal GitHub Actions workflow running `pytest` and
`npm test` (not the Playwright smoke script, which needs a live backend) on every
push would cost almost nothing to add and immediately close the "tests exist but
don't run automatically" gap.

**Recommended testing strategy for this project's actual scale**: keep doing
exactly what's being done (fast unit/integration split, fake embeddings for the
default suite, gated real-API integration test) — this is already right-sized.
Add: (1) CI wiring for the two existing suites, (2) the two missing security
regression tests above, (3) one end-to-end 503 test per broad-except site. Do
*not* add a frontend component-testing framework (React Testing Library, etc.)
unless the component tree grows meaningfully beyond its current 4 components —
would be premature infrastructure today.

---

## Dependency Findings

**Backend** (`backend/requirements.txt`) — Keep/Upgrade/Replace/Remove:

| Dependency | Verdict | Note |
|---|---|---|
| `fastapi`, `uvicorn[standard]` | Keep | Right tool for this API's size. |
| `pydantic-settings` | Keep | Correct idiomatic env-config pattern, already well used. |
| `langchain`, `langchain-community`, `langchain-text-splitters` | Keep | Used meaningfully (LCEL chains, PDF loader, splitter) — not superficial. |
| `langchain-google-genai` | Keep | Direct dependency on the chosen provider; verify pinned version still exposes the configured model names (see Security Findings). |
| `langchain-chroma`, `chromadb` | Keep | Appropriate local vector store for this scale — no case for a networked vector DB here. |
| `pypdf` | Keep | Standard, works, no issues found. |
| `python-dotenv` | Keep | Used transitively by `pydantic-settings`' `env_file` support. |
| `pytest`, `pytest-mock`, `httpx` | Keep | Well-used; `httpx` also required by FastAPI's `TestClient`. |

No unused, duplicate, or unnecessarily heavy backend dependencies found. I could
not fully verify from this review whether every pinned version resolves and is
free of known CVEs — recommend running `pip-audit` (or equivalent) before any
public deployment, since that's a point-in-time check this review can't
substitute for.

**Frontend** (`frontend/package.json`) — Keep/Upgrade/Replace/Remove:

| Dependency | Verdict | Note |
|---|---|---|
| `react`, `react-dom` | Keep | Current major version, no issues. |
| `react-markdown`, `remark-gfm` | Keep | Correctly used for safe markdown rendering (avoids `dangerouslySetInnerHTML`). |
| `vite`, `@vitejs/plugin-react` | Keep | Standard, minimal config, no issues. |
| `oxlint` | Keep | Fast, minimal-config linter; config is sparse but not wrong. |
| `@types/react`, `@types/react-dom` | Remove or clarify | Pure editor-hint packages in a JS-only project with no `tsconfig.json` — likely `npm create vite` scaffolding leftovers. Harmless but vestigial; remove if not actually improving editor experience, or add a `jsconfig.json`/`tsconfig.json` with `checkJs` if the intent is real type-checking value. |
| `playwright` | Reconsider | ~300MB+ devDependency for one manual, non-CI-wired smoke script. Either wire `npm run smoke` into CI to justify it, or accept it as a deliberate manual-verification tool and note that in the README. Not wrong, just currently underused for its weight. |

No duplicate or version-conflicting dependencies found in either package.

---

## Technical Debt

Ranked by (consequence × ease of accumulation), most important first:

1. **No logging** — debt exists because the project was built to demonstrate the
   happy path (FastAPI + LangChain integration) rather than production
   operability. Consequence: every other reliability issue in this report becomes
   much harder to diagnose in practice without it. Difficulty to fix: trivial
   (a few `logging.exception()` calls). **Fix now** — it's cheap and it's a
   force-multiplier for every future debugging session.
2. **No CI** — exists because this has been a solo, local-only project so far.
   Consequence: the two test suites can silently rot. Difficulty to fix: low (one
   GitHub Actions YAML file). **Fix now** — nearly free, immediately valuable.
3. **Chroma-per-request, no connection singleton** — exists because it's the
   simplest correct thing for one user. Consequence: won't scale past
   single-user/local use without SQLite locking errors. Difficulty to fix:
   moderate (FastAPI `lifespan` singleton + thread-safety check). **Fix later** —
   only matters if concurrent/hosted use is actually planned; the README already
   correctly scopes this as a known limitation.
4. **Unscoped chat retrieval** — exists because the API never grew a
   "which document is this about" concept. Consequence: ambiguous whether
   cross-document answers are a feature or an oversight. Difficulty to fix: low
   once a product decision is made. **Decide now, fix (or document) accordingly.**
5. **No `APIRouter` split in `main.py`** — exists because 6 routes fit fine in
   one file today. Consequence: will get messier if the API grows. Difficulty to
   fix: low, but genuinely not worth doing yet — **fix later, when a 7th route
   type is added**, not preemptively.

---

## Quick Wins

Ordered roughly by (impact ÷ effort), highest first:

1. **Fix the path-traversal upload bug** (Critical #1) — sanitize `file.filename`
   to a basename before building the file path. ~15 minutes including a
   regression test.
2. **Add logging** — wrap the two broad `except Exception` blocks in
   `main.py` (upload, chat) with `logging.exception(...)` before re-raising as
   `ProviderUnavailableError`, and add a basic `logging.basicConfig(...)` at
   startup. ~20 minutes, dramatically improves diagnosability of every other
   issue in this report.
3. **Delete the dead `vite.svg` asset** and the untracked root-level
   `_to_delete/` directory (stray `_sync.zip` + two empty stale lock files — not
   part of the app, not gitignored, looks like leftover sync-tool debris; confirm
   with whoever/whatever created it before deleting, since it's untracked and
   this audit can't tell you why it exists). 2 minutes.
4. **Wire a minimal CI workflow** running `pytest` and `npm test` on push. ~30
   minutes.
5. **Factor the repeated `with db.get_connection(...)` block** in `main.py` into
   a `Depends(get_db_connection)` provider, matching the app's existing DI style.
   ~15 minutes.
6. **Document (don't necessarily fix) the cross-document retrieval and
   cross-session history behaviors** explicitly in the README's "Known
   Limitations" section, since they currently read as oversights rather than
   decisions. ~10 minutes.

---

## Recommended Refactoring Plan

### Phase 1 — Critical Fixes
- Sanitize upload filenames (Critical #1) + regression test.
- Add logging around both broad `except Exception` sites.

### Phase 2 — High-Impact Improvements
- Decide and document (or implement) chat retrieval scoping (High #3).
- Decide and document the session-ownership trade-off (High #2).
- Wire up CI for the existing `pytest` / `npm test` suites.

### Phase 3 — Refactoring
- Split `ChatWindow.jsx` into `MessageList` / `Composer` / `SourceCitationModal`;
  fix modal accessibility (`role="dialog"`, focus trap, `Escape` handler) as part
  of that split.
- Factor `main.py`'s repeated DB-connection pattern into a `Depends(...)`
  provider.
- Delete dead frontend asset and the untracked `_to_delete/` directory.

### Phase 4 — Long-Term Improvements
- Chroma-as-singleton via FastAPI `lifespan`, if/when concurrent or hosted use is
  actually planned.
- `APIRouter` split in the backend, if/when the API grows past its current 6
  routes.
- Responsive/mobile CSS for the frontend, if mobile use is ever a goal.
- Reconsider the Playwright devDependency's cost/benefit — wire `npm run smoke`
  into CI or drop it in favor of a lighter check.

---

## Implementation Guidance — Top Items

**Critical #1 fix**, in full:
```python
# backend/app/main.py
from pathlib import Path, PurePosixPath

...

is_pdf = (file.content_type == "application/pdf") or file.filename.lower().endswith(".pdf")
if not is_pdf:
    raise HTTPException(status_code=400, detail="Only PDF files are supported.")

document_id = uuid.uuid4().hex
safe_filename = PurePosixPath(file.filename).name  # strip any directory components
upload_dir = settings.data_dir / "uploads"
upload_dir.mkdir(parents=True, exist_ok=True)
file_path = upload_dir / f"{document_id}_{safe_filename}"
file_path.write_bytes(await file.read())
```
Use `safe_filename` (not the raw `file.filename`) everywhere downstream that
currently reads `file.filename` for storage/response purposes (the DB insert and
the response's `filename` field can keep using the original `file.filename` for
*display* if preserving the user-visible name matters — just never let the raw
value reach a filesystem path).

Suggested regression test (`backend/tests/test_documents_api.py`):
```python
def test_upload_rejects_path_traversal_filename(client, sample_pdf_path):
    with open(sample_pdf_path, "rb") as f:
        response = client.post(
            "/documents/upload",
            files={"file": ("../../../../tmp/evil.pdf", f, "application/pdf")},
        )
    assert response.status_code in (200, 422)  # whatever the happy path returns
    # assert no file was written outside backend/data/uploads/
```

**Logging quick win**, in full:
```python
# backend/app/main.py
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

...

try:
    chunk_count = document_service.embed_and_store(vectorstore, chunks)
except Exception as exc:
    logger.exception("Embedding failed for document_id=%s", document_id)
    file_path.unlink(missing_ok=True)
    raise ProviderUnavailableError("Gemini", str(exc)) from exc
```
Mirror the same `logger.exception(...)` call at the `/chat` endpoint's broad
`except Exception` site.

No further code changes are included in this report per the audit's scope — the
items above are illustrative starting points, not applied changes. Nothing in
this repository has been modified.

---

## If you were taking ownership: the first 10 things

1. **Fix the path-traversal upload bug.** It's a real, confirmed vulnerability
   with a 15-minute fix — there's no reason to leave a security bug live while
   doing anything else first.
2. **Add logging around the two broad `except Exception` sites.** Nearly free,
   and it turns every other debugging task on this list from guesswork into
   evidence-based diagnosis.
3. **Wire up CI for the two existing test suites.** They're already good; making
   them run automatically is the highest-leverage, lowest-effort reliability
   improvement available.
4. **Decide (and document) whether chat retrieval should be scoped per document.**
   Right now it reads as an oversight, not a decision — a five-minute product
   call turns it into either an intentional feature or a tracked fix.
5. **Decide (and document) the session-ownership trade-off.** Same reasoning as
   #4 — cheap to resolve, currently ambiguous.
6. **Delete the dead asset and the untracked `_to_delete/` directory.** Trivial,
   but a codebase that's this clean elsewhere deserves to stay that way.
7. **Split `ChatWindow.jsx` and fix the source-modal's accessibility gaps.** The
   component is the most complex piece of frontend code and the a11y gap is real
   (keyboard/screen-reader users genuinely can't close the modal without a
   mouse) — worth doing together since they touch the same code.
8. **Factor the repeated DB-connection block into a `Depends(...)` provider.**
   Small, but it finishes the DI pattern the rest of the app already commits to.
9. **Add a `logging.exception` regression test and a path-traversal regression
   test to the backend suite.** Locks in fixes #1 and #2 so they can't silently
   regress.
10. **Only then**, if concurrent or hosted use actually becomes a goal: move
    Chroma to a `lifespan`-scoped singleton and revisit the single-worker deploy
    config. This is explicitly last because the project's own README correctly
    scopes it as "fine for local/demo use" — doing it earlier would be solving a
    problem this project doesn't have yet.

**Reasoning for the ordering:** items 1–3 are cheap, high-leverage, and
security/reliability-critical — they come first regardless of the project's
scope. Items 4–5 are decisions, not code, and resolving ambiguity early makes
every later change easier to reason about. Items 6–9 are real but bounded
cleanup, appropriately mid-list. Item 10 is deliberately last because it's the
one item on this list that the project's own documentation already says isn't
needed yet — matching effort to the project's actual, stated scope rather than
to a hypothetical production future is itself the senior-engineer judgment call
here.
