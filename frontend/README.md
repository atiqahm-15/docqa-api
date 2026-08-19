# Document Q&A API — Frontend

Vite + React single-page app for the Document Q&A API. Upload a PDF, see it
indexed, then ask questions about it with source citations.

## Setup

1. Install dependencies:
   ```bash
   npm install
   ```

2. Copy `.env.example` to `.env` (defaults already point at the Phase 1
   backend's default local address, so this step is optional unless you're
   running the backend somewhere else):
   ```bash
   cp .env.example .env
   ```

3. Make sure the backend is running (see `../backend/README.md`), then start
   the dev server:
   ```bash
   npm run dev
   ```

4. Open http://localhost:5173.

## Testing

`api.js`'s response-parsing logic has a small `node:test` suite:
```bash
npm test
```

There's no automated component test suite in this phase (by design — see the
project's design spec). Verify the UI manually, or run the scripted Playwright
smoke pass (mocks the Gemini-dependent calls, so it works without a real API
key):
```bash
npm run smoke
```
