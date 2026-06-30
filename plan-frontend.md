# AI Engineer Platform — Frontend Plan (Next.js)

A hybrid-rendered application using Next.js 15 App Router. Public marketing pages are server-rendered for SEO and fast first paint. The candidate app and admin sections use Server Components for initial data fetching and Client Components where interactivity is required. Auth is managed by NextAuth v5 (Auth.js).

---

## Pages and Features

### Public (unauthenticated)
- Landing page — hero, feature walkthrough, example question preview
- About, FAQ, Insights/blog articles
- Shareable certificate view (token-based, no login required, SSR for social preview)
- Cookie consent banner, privacy policy, terms of service

### Auth
- Register (email or Google OAuth)
- Email verification — post-registration holding page; `/verify-email/[token]` confirms and activates
- Login
- Forgot password (request reset email)
- Reset password (`/reset-password/[token]`)

### Candidate App (authenticated)
- **Dashboard** — recent sessions, overall percentile rank (hidden if population below threshold), per-technology strength chart (Exam sessions only)
- **Start Assessment** — mode selector (Trial / Practice / Exam), difficulty picker; Exam mode disabled with tooltip for unverified accounts
- **Exam Session**
  - Question display: scenario text, supporting code/logs/metrics panels
  - Response editor: rich text + code block input, autosaves on debounce
  - AI assistant panel: chat UI (guided, not answer-giving)
  - Timer countdown (server-derived, recoverable on refresh)
  - Inactivity warning dialog
  - Leave-page warning (browser `beforeunload`)
  - Progress indicator (question N of M)
- **Results** — polls until scoring completes; per-question score breakdown, four-dimension radar chart, feedback text; Trial/Practice shows submitted responses without score
- **Certificate** — download PNG (from S3), LinkedIn share button; page handles 403 gracefully if score threshold not met
- **Study List** — saved topics with study links, add/remove
- **Account Settings** — profile (name, avatar); email displayed as read-only; data export; account deletion

### Admin (`is_admin` users)
- Question bank: list, filter, vet, edit, soft-delete
- Pipeline trigger: generate questions batch; pipeline run history
- Session review: flagged sessions queue with SessionEvent log, flag resolution
- Platform stats dashboard
- User management: search, view, ban/promote, GDPR deletion

### Deferred
- Leaderboard page (backend endpoint exists; frontend page not in initial scope)

---

## Stack

| Concern | Choice | Rationale |
|---|---|---|
| Framework | Next.js 15 (App Router) | SSR/SSG for public pages, Server Components, file-based routing |
| Language | TypeScript | End-to-end type safety; shared types via OpenAPI codegen |
| Auth | NextAuth v5 (Auth.js) | Session management, Google OAuth, credentials provider for email/password |
| Data fetching | Server Components (RSC) for initial load; `fetch` for client mutations | No waterfall on first paint; reactive client state where needed |
| State | Zustand (client-only) | Active exam state only — timer, responses, AI chat history |
| Forms | React Hook Form + Zod | Performant uncontrolled forms, schema-driven validation |
| UI components | shadcn/ui + Radix UI | Accessible unstyled primitives, copy-in components, no lock-in |
| Styling | Tailwind CSS | Utility-first, dark mode via `class` strategy |
| Dark mode | `next-themes` | Eliminates flash-of-unstyled-content during SSR |
| Charts | Recharts (client component) | Composable, React-native, sufficient for radar + bar charts |
| Code editor | CodeMirror 6 (client component) | Lightweight syntax highlighting in response area |
| Deployment | Heroku (Node.js buildpack) | Standalone Next.js server; co-located with backend in a shared Heroku pipeline |

---

## Key Architecture Decisions

### Auth flow

NextAuth manages sessions between the browser and Next.js via a signed `httponly` session cookie. On login, the credentials provider calls `POST /auth/login` and reads `access_token` and `refresh_token` from the **JSON response body** — NextAuth cannot read `httponly` cookies set by a different origin. Both tokens are stored inside the NextAuth JWT (via the `jwt` callback) and never exposed to client-side JavaScript directly. All downstream FastAPI calls use the access token:

- **Server Components:** call `getServerSession()` → extract `session.accessToken` → `Authorization: Bearer <token>` header on FastAPI requests
- **Client Components:** call `useSession()` → extract `session.accessToken` → `Authorization: Bearer <token>` header on FastAPI requests

There is no separate client-side auth store. `useSession()` is the single source of truth for client components. Zustand holds only exam session state.

**Token refresh:** FastAPI access tokens have a 15-minute lifetime. The NextAuth `jwt` callback checks whether the access token is within 60 seconds of expiry on every session read. If so, it calls `POST /auth/refresh` with the stored `refreshToken` and replaces `accessToken` in the NextAuth JWT before returning. If the refresh call fails (expired or rotated refresh token), the callback clears the session and the user is redirected to login.

**Session lifetime:** NextAuth is configured with `session: { maxAge: 8 * 60 * 60 }` (8 hours), exceeding the longest possible exam. The refresh loop above keeps the FastAPI access token valid for the full session duration.

**Session expiry mid-exam:** If a 401 is returned from FastAPI despite the refresh loop (e.g., the refresh token was invalidated server-side), the client saves the current Zustand exam state to `sessionStorage` and redirects to `/login?resume=<sessionId>`. After re-authentication, the resume param triggers state restoration before continuing.

### Protected routes

`middleware.ts` protects `/app/*` and `/admin/*` before any page component renders. Admin routes additionally check `session.user.is_admin`. Unauthenticated requests are redirected to `/login` with a `?callbackUrl` param.

### Email verification

After registration, the user is redirected to `/verify-email` (a holding page). The dashboard shows a dismissible verification banner for unverified users. Trial and Practice sessions remain available to unverified accounts; only Exam mode is blocked. The Start Assessment page disables the Exam option with a tooltip: "Verify your email to unlock Exam mode." The backend enforces this at `POST /sessions/{id}/start` with `UnverifiedEmailRequired`.

`/verify-email/[token]` validates the token, activates the account, and redirects to the dashboard.

### Exam session state

The active session lives in a Zustand slice: question list, current index, AI chat history per question, draft and submitted responses. On mount, `useExamSession` fetches `GET /sessions/{id}` from FastAPI to hydrate this state — including per-question draft `response_text` and `ai_interactions` — enabling full recovery after a page refresh.

**Timer:** `useExamTimer` derives remaining time from server data, not a local accumulator:

```ts
const remaining = Math.max(
  0,
  new Date(session.started_at).getTime() + session.time_limit_seconds * 1000 - Date.now()
)
```

The hook runs `setInterval` to decrement the display, but re-derives from `session.started_at` on mount and on `visibilitychange` (tab refocus) to correct for clock drift or time spent inactive. When remaining hits zero the hook auto-submits via the submit mutation.

**Autosave:** The `ResponseEditor` debounces a `PATCH /sessions/{id}/questions/{qid}/autosave` call on a 2-second delay after every keystroke. This persists draft responses server-side so they survive a page crash or refresh. On session recovery, `GET /sessions/{id}` returns the current `response_text` for each question, which rehydrates Zustand alongside the question list and AI chat history.

**Periodic server sync:** The exam page polls `GET /sessions/{id}` every 60 seconds. This keeps the NextAuth session alive, confirms the session is still open server-side, and provides a recovery point if client state diverges.

**Leave-page protection:** A `useEffect` attaches a `beforeunload` handler for the duration of the exam. Navigation within the app is guarded by a `useBlocker` hook that shows a confirmation dialog.

When the candidate confirms leaving via the `useBlocker` dialog, `POST /sessions/{id}/abandon` is called before navigation proceeds. In the `beforeunload` handler (browser close, reload, or hard navigation), `navigator.sendBeacon` is used to fire the abandon endpoint — regular `fetch` calls are not guaranteed to complete during page unload.

**Integrity events:** The exam session emits `POST /sessions/{id}/events` for every integrity signal. These are fire-and-forget (no retry, no awaiting):

| Event | Trigger |
|---|---|
| `tab_blur` | `document.visibilitychange` → hidden |
| `return_to_page` | `document.visibilitychange` → visible |
| `leave_page` | `beforeunload` (via `sendBeacon`) |
| `inactivity_warning` | When the inactivity warning dialog is displayed |
| `copy_paste` | `paste` event on the `ResponseEditor` |

The admin review queue reads these events alongside the candidate's responses when evaluating a flagged session.

### Streaming AI responses

The FastAPI endpoint returns `Content-Type: text/event-stream` (SSE format) in response to `POST /sessions/{id}/questions/{qid}/ai-chat`. Because `EventSource` does not support POST requests, the client uses `fetch` and reads the response as a `ReadableStream`, manually parsing SSE framing:

```ts
const res = await fetch(url, { method: 'POST', body: ..., headers: { Authorization: ... } })
const reader = res.body.getReader()
const decoder = new TextDecoder()
let buffer = ''

while (true) {
  const { done, value } = await reader.read()
  if (done) break
  buffer += decoder.decode(value, { stream: true })
  const lines = buffer.split('\n\n')
  buffer = lines.pop() ?? ''
  for (const block of lines) {
    const data = block.replace(/^data: /, '').trim()
    if (data && data !== '[DONE]') appendToken(data)
  }
}
```

**Error handling:** A `429` response is handled based on context:
- If the response body indicates the per-question turn limit (15 turns) was reached, the AI input is disabled and a "You've reached the AI assistant limit for this question" message is shown — no retry option.
- If the `429` is from the hourly rate limit, a retry option is shown with the `Retry-After` time.
- Any other stream error shows a retry option inline; the partial response is preserved in state.

**CORS:** FastAPI must be configured to allow the Next.js origin (`CORS_ORIGINS` env var) for the AI chat endpoint and any other endpoints called directly from the client. This must be set per environment (dev, staging, prod).

### Results page

Scoring runs asynchronously after session completion (~10–30 seconds). The results page uses a hybrid approach: the Server Component renders an initial skeleton with the session metadata, then a `<ResultsPoller>` client component polls `GET /sessions/{id}/results` every 3 seconds until `status` transitions from `"pending"` to `"completed"` or `"failed"`.

**Trial/Practice sessions:** These are never scored. For completed Trial/Practice sessions, the results page shows the submitted responses and AI interactions without a score breakdown, percentile rank, or certificate prompt.

**Scoring failure:** If `status` becomes `"failed"`, the page renders the `failure_reason` and a "Contact support" prompt. Admins can re-queue scoring via `POST /admin/sessions/{id}/rescore`.

### Error boundaries

Next.js `error.tsx` files are colocated at the segment level. The exam session has a dedicated error boundary at `app/app/session/[id]/error.tsx`. On render error, it:
1. Reads current Zustand state and persists it to `sessionStorage`
2. Renders a recovery UI with "Try to resume" and "Submit current answers" options

### Certificate

The backend generates the canonical certificate image using Pillow, uploads it to S3, and stores the resulting `image_url` on the `Certificate` record. This S3 URL is the source of truth for all sharing:

- The public view at `/certificate/[token]` displays the S3 image directly (SSR, no auth required)
- The `<meta og:image>` tag points to the S3 URL so LinkedIn and Twitter previews render consistently
- The "Download PNG" button fetches the S3 image URL from the `Certificate` record and triggers a browser download

The `<CertificateCard>` React component renders the certificate in the authenticated view for display purposes. It may optionally be used with `html2canvas` to offer a locally-rendered download that matches the live page styling, but the S3 image is the primary download path.

**403 handling:** `GET /sessions/{id}/certificate` returns `403` if `total_score < 75` or if the session mode is Trial/Practice. The certificate page handles this by redirecting to the results page with an inline "Certificate not available" message rather than rendering an error boundary.

### Insights/blog content

Stored as Markdown files in `content/insights/`. Next.js reads and renders them at build time (SSG) — no database needed for editorial content. Updates deploy as a new build.

### OpenAPI type sharing

`openapi.json` is committed to the repository and updated by running `npm run sync-schema` against a live FastAPI instance. `openapi-typescript` generates `types/api.ts` as a prebuild step:

```json
"prebuild": "openapi-typescript openapi.json -o types/api.ts"
```

`types/api.ts` is gitignored (always generated from the committed schema). Both Server Components and client fetches import from this file — the FastAPI schema is the single source of truth for request/response types.

### Server Actions for non-exam mutations

Account settings updates, saving/removing study topics, and other low-stakes mutations use Next.js Server Actions. The Server Action calls FastAPI with the session token server-side — no client-side API call needed. This is not used for exam flows, which are client-driven.

### Dark mode

Tailwind's `class` strategy. `next-themes` wraps the root layout and avoids the flash-of-unstyled-content (FOUC) that `localStorage` alone causes during SSR. The toggle writes `"dark"` to `<html>` and persists to a cookie so Server Components render the correct theme on first load.

---

## Project Structure

```
app/
  layout.tsx                    — root layout: ThemeProvider, SessionProvider
  page.tsx                      — Landing (Server Component, SSG)
  about/page.tsx
  faq/page.tsx
  privacy/page.tsx
  insights/
    page.tsx                    — article list (SSG)
    [slug]/page.tsx             — individual article (SSG from markdown)
  certificate/[token]/page.tsx  — public share view (SSR, S3 image + OpenGraph tags)

  login/page.tsx
  register/page.tsx
  verify-email/
    page.tsx                    — post-registration holding page
    [token]/page.tsx            — token confirmation + account activation
  forgot-password/page.tsx
  reset-password/[token]/page.tsx

  app/                          — authenticated candidate area
    layout.tsx                  — auth guard via middleware, AppShell
    dashboard/page.tsx          — Server Component, fetches sessions + stats
    start/page.tsx              — mode/difficulty picker; Exam disabled for unverified
    session/[id]/
      page.tsx                  — "use client", exam experience
      error.tsx                 — exam error boundary with state recovery
      results/page.tsx          — Server Component skeleton + ResultsPoller client component
      certificate/page.tsx      — certificate view + download; handles 403
    topics/page.tsx
    settings/page.tsx           — name/avatar editable; email read-only

  admin/
    layout.tsx                  — requires is_admin
    questions/page.tsx          — question bank with vet/edit/soft-delete
    sessions/page.tsx           — flagged session queue with event log viewer
    pipeline/page.tsx           — trigger generation + run history
    stats/page.tsx              — platform-wide stats
    users/page.tsx              — search, view, ban/promote, GDPR deletion

components/
  ui/                           — shadcn/ui (Button, Dialog, etc.)
  exam/                         — QuestionPanel, AIAssistant, Timer, ResponseEditor
  results/                      — ScoreRadar, QuestionBreakdown, ResultsPoller
  certificate/                  — CertificateCard (authenticated view)
  layout/                       — Navbar, Sidebar, Footer, AppShell

lib/
  api.ts                        — server-side fetch wrapper (injects Bearer from session)
  api-client.ts                 — client-side fetch wrapper (injects Bearer from useSession)
  auth.ts                       — NextAuth config (providers, jwt/session callbacks, refresh loop)
  zod-schemas.ts
  utils.ts

store/
  session.ts                    — Zustand: active exam state (timer, responses, AI chat)

hooks/
  useAIChat.ts                  — fetch + ReadableStream SSE parser; 429 turn-limit vs rate-limit handling
  useExamTimer.ts               — server-derived countdown, re-syncs on visibilitychange
  useExamSession.ts             — hydrates Zustand from GET /sessions/{id}, periodic sync, autosave debounce

content/
  insights/
    *.md                        — blog/insights articles

types/
  api.ts                        — generated from openapi.json (gitignored)

openapi.json                    — committed FastAPI schema (source for type generation)
middleware.ts                   — auth route protection, admin guard
next.config.ts
```

---

## Deployment (Heroku)

The frontend runs as a standalone Next.js Node.js server on a Heroku web dyno, deployed alongside the FastAPI backend in a shared Heroku pipeline.

### Build configuration

`next.config.ts` must set `output: 'standalone'` to produce a self-contained server bundle Heroku can run without the full `node_modules` tree:

```ts
const nextConfig: NextConfig = {
  output: 'standalone',
}
```

The standalone output only includes the server bundle — static assets and the `public` directory must be copied in manually. Add this to the `build` script in `package.json`:

```json
"build": "next build && cp -r .next/static .next/standalone/.next/static && cp -r public .next/standalone/public"
```

Without this step, all CSS, JS chunks, fonts, and public assets return 404 in production.

Pin the Node.js version in `package.json` so Heroku uses the same version across deployments:

```json
"engines": { "node": "20.x" }
```

### Procfile

```
web: node .next/standalone/server.js
```

### Required config vars

| Variable | Value |
|---|---|
| `NEXTAUTH_URL` | Public Heroku URL (e.g. `https://crucible-frontend.herokuapp.com`) |
| `NEXTAUTH_SECRET` | Random 32-byte secret |
| `FASTAPI_BASE_URL` | Backend Heroku app URL |
| `GOOGLE_CLIENT_ID` | Google OAuth app credentials |
| `GOOGLE_CLIENT_SECRET` | Google OAuth app credentials |

`NEXTAUTH_URL` must match the callback URL registered in the Google Cloud Console — OAuth redirects will fail if these differ between environments.

### Next.js Image Optimization

Heroku dynos have an ephemeral filesystem — the Next.js image optimization cache is lost on every dyno restart, causing re-optimization on cold starts. Two options:

- **Preferred:** Configure a [Cloudinary loader](https://next.js.org/docs/app/api-reference/components/image#loader) in `next.config.ts` to offload optimization to a CDN.
- **Simpler:** Set `images: { unoptimized: true }` for the initial launch and revisit when image-heavy pages are built.

### Middleware

`middleware.ts` runs on the Node.js server process, not at the edge. Auth route protection and admin guards work identically; the only difference vs. Vercel is slightly higher redirect latency on a cold dyno.

### CI/CD

Use Heroku's GitHub integration (auto-deploy on push to `main`) or GitHub Actions:

```yaml
- uses: akhileshns/heroku-deploy@v3.13.15
  with:
    heroku_api_key: ${{ secrets.HEROKU_API_KEY }}
    heroku_app_name: "crucible-frontend"
    heroku_email: ${{ secrets.HEROKU_EMAIL }}
```

Enable **Review Apps** in the Heroku pipeline for per-PR preview environments. Review Apps require an `app.json` file in the repository root describing add-ons and config var defaults — without it, Heroku cannot provision a review environment.

---

## Testing Strategy

| Layer | Tool | Coverage |
|---|---|---|
| Unit | Vitest | Hooks (`useExamTimer`, `useAIChat`), Zod schemas, utility functions |
| Component | React Testing Library + Vitest | Exam session state machine, form validation, error boundary recovery |
| E2E | Playwright | Registration → verify email → start exam → submit → view results |
| E2E | Playwright | Exam → certificate download; certificate 403 redirect |
| E2E | Playwright | Admin: create question → publish → appears in exam |

E2E tests run against a local Next.js dev server with a test FastAPI instance (or mocked API routes). CI runs unit and component tests on every PR; E2E tests run on merge to main.

---

## Tradeoffs

**Pros:**
- Landing, FAQ, Insights, and certificate pages are SEO-friendly with real HTML on first load
- `next-themes` eliminates dark mode flash during SSR
- Server Components remove client-side data waterfalls for most pages
- NextAuth handles token refresh transparently via the `jwt` callback
- NextAuth simplifies Google OAuth significantly
- Unified TypeScript project; OpenAPI codegen is the single type source of truth
- Heroku pipeline with Review Apps provides per-PR preview environments

**Cons:**
- More complex mental model: developers must know which components are Server vs Client
- Next.js App Router caching behavior (revalidation, stale data) requires deliberate attention
- Node.js server required at runtime (not purely static)
- Tighter coupling to Next.js conventions makes a future framework swap harder
- `"use client"` boundary mistakes are easy to make and can silently degrade performance
