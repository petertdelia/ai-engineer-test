# Crucible — Frontend

Next.js 15 (App Router) frontend for the Crucible AI engineering assessment platform. Hybrid-rendered: public pages are SSR/SSG for SEO; the candidate app and admin sections use Server Components for initial data fetching with Client Components for interactive surfaces.

---

## Setup

**Prerequisites:** Node.js 20+, a running instance of the [backend API](../README.md).

```bash
cp .env.local.example .env.local   # fill in required values
npm install
npm run sync-schema                # pull OpenAPI schema from backend
npm run dev                        # http://localhost:3000
```

To regenerate TypeScript types from the backend schema at any time:

```bash
npm run sync-schema       # fetches openapi.json from FASTAPI_BASE_URL
npm run generate-types    # writes types/api.ts from openapi.json
```

Types are regenerated automatically as part of `npm run build`.

---

## Environment Variables

Copy `.env.local.example` to `.env.local`:

| Variable | Description |
|---|---|
| `NEXTAUTH_URL` | Public URL of this app (e.g. `http://localhost:3000`) |
| `NEXTAUTH_SECRET` | Random 32-byte secret for NextAuth session encryption |
| `FASTAPI_BASE_URL` | Backend API URL (e.g. `http://localhost:8000`) |
| `GOOGLE_CLIENT_ID` | Google OAuth app client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth app client secret |

`NEXTAUTH_URL` must match the OAuth callback URL registered in the Google Cloud Console. In production, set it to the Heroku app URL.

---

## Scripts

| Command | Description |
|---|---|
| `npm run dev` | Start dev server with HMR at `http://localhost:3000` |
| `npm run build` | Production build (generates types, then `next build`, then copies standalone assets) |
| `npm run start` | Start the standalone production server |
| `npm run lint` | ESLint |
| `npm run type-check` | TypeScript compiler check (no emit) |
| `npm run sync-schema` | Fetch `openapi.json` from the running backend |
| `npm run generate-types` | Generate `types/api.ts` from the committed `openapi.json` |

---

## Project Structure

```
app/                          — Next.js App Router pages
  layout.tsx                  — Root layout: ThemeProvider, SessionProvider
  page.tsx                    — Landing page (SSG)
  about/, faq/, privacy/      — Static marketing pages
  insights/                   — Blog/insights (SSG from content/insights/*.md)
  certificate/[token]/        — Public certificate share view (SSR)

  login/, register/           — Auth pages
  verify-email/               — Email verification holding page + [token] confirm
  forgot-password/            — Password reset request
  reset-password/[token]/     — Password reset form

  app/                        — Authenticated candidate area
    dashboard/                — Score history, per-technology strength chart
    start/                    — Mode and difficulty selector
    session/[id]/             — Exam session (client component)
      results/                — Score breakdown with async polling
      certificate/            — Certificate view + download
    topics/                   — Saved study topics
    settings/                 — Profile, data export, account deletion

  admin/                      — Admin area (is_admin required)
    questions/                — Question bank management
    sessions/                 — Flagged session review queue
    pipeline/                 — Question generation trigger + run history
    stats/                    — Platform-wide stats
    users/                    — User search, ban/promote, GDPR deletion

components/
  ui/                         — shadcn/ui base components
  exam/                       — QuestionPanel, AIAssistant, Timer, ResponseEditor
  results/                    — ScoreRadar, QuestionBreakdown, ResultsPoller
  certificate/                — CertificateCard
  layout/                     — Navbar, Sidebar, Footer, AppShell

hooks/
  useAIChat.ts                — fetch + ReadableStream SSE parser
  useExamTimer.ts             — Server-derived countdown, re-syncs on tab refocus
  useExamSession.ts           — Hydrates Zustand from GET /sessions/{id}, autosave debounce

store/
  session.ts                  — Zustand: active exam state (timer, responses, AI chat)

lib/
  api.ts                      — Server-side fetch wrapper (Bearer token from session)
  api-client.ts               — Client-side fetch wrapper (Bearer token from useSession)
  auth.ts                     — NextAuth config: providers, jwt callback, token refresh loop

content/
  insights/*.md               — Blog articles (SSG at build time)

types/
  api.ts                      — Auto-generated from openapi.json (gitignored)

openapi.json                  — Committed backend schema (source for type generation)
middleware.ts                 — Auth route protection (/app/*, /admin/*)
```

---

## Key Architecture Decisions

### Auth

NextAuth manages the session between the browser and Next.js via a signed `httponly` cookie. On login, the credentials provider calls `POST /auth/login` on the FastAPI backend and stores the returned `access_token` and `refresh_token` in the NextAuth JWT. All FastAPI calls use the access token as a Bearer header.

**Token refresh:** FastAPI access tokens expire in 15 minutes. The NextAuth `jwt` callback in `lib/auth.ts` detects expiry and calls `POST /auth/refresh` automatically before returning the session to the caller.

### Exam session

The active exam lives in a Zustand store (`store/session.ts`). On mount, `useExamSession` fetches `GET /sessions/{id}` to hydrate the store from the server — including draft responses and AI chat history — so the session survives a page refresh.

The timer is derived from server data (`session.started_at + session.time_limit_seconds - now`), not a local accumulator. It re-syncs from the server on tab refocus.

The `ResponseEditor` debounces a `PATCH .../autosave` call on a 2-second delay to persist drafts without waiting for explicit submission.

### AI assistant streaming

The AI chat endpoint returns `text/event-stream`. Because `EventSource` doesn't support POST, `useAIChat` uses `fetch` with `ReadableStream` and manually parses SSE framing. A 429 response from a turn-limit exhaustion disables the input with a message; a 429 from the hourly rate limit shows a retry option with the wait time.

### Results polling

Scoring runs asynchronously on the backend (~10–30 seconds). The results page renders a Server Component skeleton on first load, then `ResultsPoller` (a client component) polls `GET /sessions/{id}/results` every 3 seconds until `status` transitions from `"pending"` to `"completed"` or `"failed"`.

### Type safety

`openapi-typescript` generates `types/api.ts` from the committed `openapi.json`. Both Server Components and client fetches import from this file. Run `npm run sync-schema` whenever the backend API changes, then commit the updated `openapi.json`.

---

## Deployment (Heroku)

The app is configured for Heroku's Node.js buildpack with standalone output.

### Build

`next.config.ts` sets `output: 'standalone'`. The `build` script copies static assets into the standalone bundle after `next build` — this step is required or all CSS and JS chunks will 404:

```bash
next build && cp -r .next/static .next/standalone/.next/static && cp -r public .next/standalone/public
```

### Procfile

```
web: node .next/standalone/server.js
```

### Required Heroku config vars

```
NEXTAUTH_URL        https://your-app.herokuapp.com
NEXTAUTH_SECRET     <random 32-byte secret>
FASTAPI_BASE_URL    https://your-backend.herokuapp.com
GOOGLE_CLIENT_ID    <OAuth client id>
GOOGLE_CLIENT_SECRET <OAuth client secret>
```

---

## Testing

```bash
npm run type-check          # TypeScript — no services required
npm run lint                # ESLint

npx vitest run              # unit + component tests
npx vitest                  # watch mode
```

E2E tests (Playwright) are run separately against a live dev server — see `plan-frontend.md` for the full testing strategy.
