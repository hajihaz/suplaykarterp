# HajiHaz AI Handover

## 1. Product Summary

HajiHaz AI is a personal AI system built to represent Haji first, use Haji's uploaded knowledge as the main source of truth, and fall back to live web context only when the question is genuinely generic or current.

The product is live publicly and supports:

- conversational replies for casual chat
- persona-first answers for Haji, HajiHaz AI, business, education, and qualifications
- RAG-backed answers from uploaded documents
- web-backed answers for broader world knowledge
- admin-managed document ingestion, editing, exports, monitoring, and source controls

## 2. Live URLs

- Public app: [https://hajihazai.allbeesolutions.com](https://hajihazai.allbeesolutions.com)
- Public admin: [https://hajihazai.allbeesolutions.com/admin](https://hajihazai.allbeesolutions.com/admin)
- Health check: [https://hajihazai.allbeesolutions.com/health](https://hajihazai.allbeesolutions.com/health)

## 3. Core Product Behavior

### Conversational mode

Short casual prompts are handled as normal conversation, not as web search.

Examples:

- `how are you macha`
- `hello`
- `thanks`

Expected behavior:

- warm human reply
- no web lookup
- no citations

### Persona-first mode

Questions about Haji should prefer saved knowledge first.

Examples:

- `Who is Haji?`
- `What businesses does Haji own?`
- `What are Haji's education and qualifications?`
- `What is HajiHaz AI and what can it do?`

Expected behavior:

- answer from saved knowledge
- synthesize naturally
- avoid copy-paste chunk dumping
- avoid drifting to similarly named public people

### Knowledge-first operational mode

Internal or business workflow questions use uploaded knowledge first.

Examples:

- SOPs
- pricing notes
- policies
- uploads
- workflow questions

### Web-backed mode

Generic world questions use web fallback when local relevance is weak.

Examples:

- `What is the capital of France?`
- `What is business strategy?`

## 4. Key Features Delivered

### Chat experience

- live public chat UI
- prompt deck
- animated thinking/loading state
- prompt-card auto-scroll to answer area
- cleaner response notices
- copy response action
- desktop and mobile responsive behavior

### Persona handling

- persona-first routing
- core persona document priority
- cleaner persona answer synthesis
- conversational lane for human prompts

### Admin workspace

- login/logout
- change password
- add additional admin users
- guest-lock state before login
- clean admin reveal after unlock
- document create, edit, delete
- file import
- URL import
- export knowledge base
- source controls
- backups
- monitoring panels
- diagnostics and logs

### Ingestion

- `.txt`
- `.md`
- `.json`
- `.csv`
- `.pdf`
- `.docx`
- image OCR
- website/page import
- Google Docs import
- Google Sheets import
- public Google Drive import
- public Notion import

### Operations

- public VPS deployment
- HTTPS on branded subdomain
- health check route
- monitoring endpoints
- backups and maintenance routes
- deploy/rollback helper scripts

## 5. Current UX Rules

### Prompt deck

Current prompt deck questions:

1. `Who is Haji?`
2. `What is HajiHaz AI and what can it do?`
3. `What businesses does Haji own?`
4. `What are Haji’s education and qualifications?`

Clicking a prompt deck card:

- injects/submits the question
- auto-scrolls to the answer area
- works on desktop and mobile

### Admin guest state

Before login, the admin page should show only:

- `Admin workspace`
- `Admin access`

After login, the rest of the admin panels become visible.

## 6. Core Persona Source

Documents can be marked as `Core persona source`.

Use this for:

- identity
- profile
- business ownership
- education
- qualifications
- HajiHaz AI purpose and personality

Effect:

- these documents get boosted during retrieval
- they should dominate owner/profile questions even when the library grows larger

## 7. Architecture

### Backend

- FastAPI
- Python
- SQLite
- local RAG pipeline
- hybrid answer routing

Main backend areas:

- `backend/app/routes`
- `backend/app/services`
- `backend/app/core`

### Frontend

Two frontend paths exist:

1. Stable backend-served UI
   - `preview/`
   - this is the main live product path

2. Next.js frontend
   - `frontend/`
   - optional path, not the primary live experience

### Data

- SQLite-backed document storage
- chunked retrieval records
- admin users and sessions
- monitoring and operations data

## 8. Important Files

### Product logic

- [backend/app/services/anthropic_client.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/app/services/anthropic_client.py)
- [backend/app/services/response_builder.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/app/services/response_builder.py)
- [backend/app/services/rag.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/app/services/rag.py)

### Admin and schema

- [backend/app/routes/admin.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/app/routes/admin.py)
- [backend/app/schemas.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/app/schemas.py)
- [backend/app/db.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/app/db.py)

### Live UI

- [preview/index.html](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/preview/index.html)
- [preview/admin.html](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/preview/admin.html)
- [preview/app.js](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/preview/app.js)
- [preview/styles.css](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/preview/styles.css)

### Tests

- [backend/tests/test_api.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/tests/test_api.py)
- [backend/tests/test_e2e_smoke.py](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/backend/tests/test_e2e_smoke.py)

### Ops and deployment

- [docs/production-ops.md](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docs/production-ops.md)
- [docs/deploy-hostinger-vps.md](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/docs/deploy-hostinger-vps.md)
- [ops/vps](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/ops/vps)

## 9. Local Validation Status

Recently verified locally:

- backend compile checks passing
- `preview/app.js` syntax checks passing
- backend test suite passing

Latest known local status:

- `19/19` tests passing

## 10. Known Good Behaviors

- `Who is Haji?` should return `mode: knowledge`
- `how are you macha` should return `mode: conversation`
- `What is the capital of France?` should return `mode: web`
- prompt deck click should auto-scroll to answer area
- admin guest page should stay minimal until login

## 11. Operational Notes

- Main branded public URL should be used everywhere
- The deleted older `sslip.io` fallback is no longer the public route
- The server hostname change to `hajihaz.server` is not itself a product problem
- If the app shows a `502`, the usual issue is the backend process on `127.0.0.1:8091` being down, not the domain itself

## 12. Android / Play Status

Android wrapper work is already prepared in the repo:

- [android-app](/Users/hajihaz/Documents/Rkn associates/Hostinger management/developer/android-app)

Play Console flow has progressed, but production release depends on Google's testing requirements before final publish.

## 13. Recommended Next Steps

### High-value next improvements

1. Streaming responses
2. Better multi-turn memory
3. Stronger answer synthesis across overlapping documents
4. More human conversational style variations
5. Better citation/source preview UI

### Ops cleanup later

1. Rebuild a cleaner Python environment on the VPS
2. Fix the VPS `apt` mirror properly
3. Tighten process supervision further
4. Confirm backup restore drills on a fresh failure simulation

## 14. Short Summary

HajiHaz AI is now a live branded personal AI system that:

- represents Haji first
- answers from Haji's saved knowledge first
- handles casual chat naturally
- uses live web for real generic questions
- includes a working admin workspace for managing the whole knowledge base
- is publicly deployed and actively usable
