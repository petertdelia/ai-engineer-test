# Frontend Plan Review — Errors and Omissions

---

## Actual Errors

**1. `client.ts` "auth header injection" contradicts the auth strategy**
([plan-frontend.md:63](plan-frontend.md#L63), [plan-frontend.md:113](plan-frontend.md#L113))

The plan specifies JWT in `httponly` cookies — the browser sends those automatically. There is no auth header to inject. The fetch wrapper should set `credentials: 'include'`, not inject a `Bearer` token. As written, the description is wrong and would mislead implementation.

**2. SSE vs `ReadableStream` conflation**
([plan-frontend.md:72-74](plan-frontend.md#L72-L74))

The plan says the backend "pipes Claude's streamed response as SSE" and the frontend "reads the stream with a `ReadableStream` reader." These are different protocols:

- SSE uses `Content-Type: text/event-stream` with `data: ...\n\n` framing, typically consumed via the `EventSource` API (or by manually parsing SSE framing from a `ReadableStream`)
- Raw chunked streaming uses `ReadableStream` directly without framing

The plan treats them as interchangeable. Either pick SSE (and call out that `EventSource` doesn't support POST, so you'd use `fetch` + manual SSE parsing) or pick raw streaming — but name it correctly and match the client handling to the backend output.

---

## Significant Omissions

**3. Exam session recovery on page refresh**

The timer runs entirely in client state (`useEffect` + `setInterval`). There's no mention of what happens if the user refreshes mid-exam. The server should be the source of truth for session start time — the client should derive remaining time from `session.started_at + session.duration_seconds - now` rather than maintaining its own countdown. This needs to be spelled out.

**4. Password reset routes missing from Approach B's project structure**
([plan-frontend.md:182-235](plan-frontend.md#L182-L235))

The features list includes a password reset flow (line 18), but there are no corresponding routes (`/forgot-password`, `/reset-password/[token]`) in Approach B's `app/` directory tree. Approach A's structure also only lists `Login.tsx, Register.tsx` with no reset pages.

**5. Session expiry during an active exam**

If the auth cookie expires mid-session (e.g., a long exam), API calls will start returning 401. The plan doesn't address this: does the session stay alive while the exam is open? Does the client detect 401s and prompt re-auth without losing responses? This needs a decision.

**6. No error boundaries**

The exam session is the most failure-prone surface (streaming AI, timed state, multiple concurrent mutations). There's no mention of error boundaries, fallback UI, or what happens when `POST /sessions/{id}/questions/{qid}/ai-chat` fails mid-stream.

**7. CORS for direct-to-FastAPI client calls**

Approach B recommends direct client → FastAPI for streaming to "avoid doubling latency" (line 169), but that requires FastAPI to allow CORS from the Next.js origin. This is a real configuration requirement that should be called out — it's often overlooked and causes issues in staging/prod when the frontend and backend domains differ.

---

## Minor Omissions

**8. Certificate generation strategy unspecified**

The Certificate page is listed as "download image" (line 32) but there's no description of how it's generated — frontend Canvas/`html2canvas`, a server-rendered image endpoint, or a PDF. This is a non-trivial implementation choice that should be captured.

**9. Email verification after registration**

Registration flow is listed but there's no mention of email verification — important for a platform where certificates need to be tied to a real identity.

**10. Redundant Zustand `store/auth.ts` in Approach B**
([plan-frontend.md:221](plan-frontend.md#L221))

NextAuth already provides session data via `useSession()`. The plan includes a Zustand auth slice that "mirrors NextAuth session" with no explanation of why. Either justify it (e.g., for use in non-React contexts like Zustand middleware) or remove it — as written it looks like an oversight.

**11. `vite-plugin-prerender` is poorly maintained**
([plan-frontend.md:76](plan-frontend.md#L76))

The plugin hasn't been updated in years and has known issues with dynamic routes. `vite-ssg` is the more actively maintained alternative, or this can be flagged as "use a CDN-level prerendering service."

**12. OpenAPI type generation requires a running FastAPI server in CI**
([plan-frontend.md:171](plan-frontend.md#L171))

Generating `types/api.ts` from `http://localhost:8000/openapi.json` means CI either needs to spin up FastAPI or the generated file needs to be committed. Neither option is mentioned — it's an operational gap.

**13. No testing strategy**

Neither approach mentions unit tests, integration tests, or e2e tests (Playwright/Cypress). For a platform where exam integrity matters this seems like a notable gap, even if just a one-line callout.

---

## Summary Table

| # | Issue | Severity |
|---|-------|----------|
| 1 | `auth header injection` contradicts httponly cookie auth | Error |
| 2 | SSE vs ReadableStream conflation | Error |
| 3 | No exam session recovery on refresh | Significant |
| 4 | Password reset routes missing from file structure | Significant |
| 5 | No handling for session expiry during exam | Significant |
| 6 | No error boundaries | Significant |
| 7 | CORS not mentioned for direct-to-FastAPI streaming | Significant |
| 8 | Certificate generation strategy unspecified | Minor |
| 9 | Email verification omitted | Minor |
| 10 | Redundant Zustand auth store in Approach B | Minor |
| 11 | `vite-plugin-prerender` is stale | Minor |
| 12 | OpenAPI codegen CI gap | Minor |
| 13 | No testing strategy | Minor |
