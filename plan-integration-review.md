# Frontend / Backend Integration Review

Comparison of plan-frontend.md (Next.js) and plan-backend.md (FastAPI). Issues are grouped by severity. Each entry identifies which plan(s) need to change and what the resolution is.

---

## Critical Issues

These are direct conflicts or missing pieces that would cause runtime bugs or broken flows.

---

### 1. Token lifetime mismatch — no refresh flow described

**Conflict:** The backend issues 15-minute access tokens. The frontend's NextAuth session is configured with an 8-hour `maxAge`. After 15 minutes, every FastAPI call from the frontend will return `401` because the stored `accessToken` is expired — but the NextAuth session itself is still alive, so the user appears authenticated.

**Neither plan describes how the access token is refreshed.** The backend exposes `POST /auth/refresh`, and NextAuth supports token rotation via the `jwt` callback, but no connection is drawn between the two.

**Resolution (frontend plan):** The NextAuth `jwt` callback must detect access token expiry and call `POST /auth/refresh` with the stored `refreshToken` before returning. The NextAuth session should store both `accessToken` and `refreshToken` (returned by `POST /auth/login`). The backend already supports this; the frontend plan needs to describe the rotation loop explicitly.

---

### 2. Cookie ownership conflict — token delivery model is incompatible

**Conflict:** The backend auth design states that tokens are stored in `httponly`, `SameSite=Strict` cookies. The frontend's NextAuth credentials provider calls `POST /auth/login` and stores the returned tokens inside the NextAuth session. These are two fundamentally different token delivery models.

NextAuth's credentials provider calls the backend over HTTP. It reads the JSON response body to extract tokens — it cannot read `httponly` cookies set by a different origin (the browser never exposes them to JS, and CORS prevents cross-origin cookie reads). If the backend only returns tokens in cookies and not in the response body, NextAuth cannot extract them.

**Resolution (backend plan):** `POST /auth/login` must return the `access_token` and `refresh_token` in the JSON response body in addition to (or instead of) setting cookies. The cookie-based approach is appropriate for same-origin browser clients; for the Next.js integration specifically, the body tokens are required. The backend plan should note this dual-delivery requirement.

---

### 3. Certificate generation conflict — backend and frontend use incompatible approaches

**Conflict:** The backend generates a certificate image server-side using Pillow, uploads it to S3, and stores the resulting `image_url` on the `Certificate` record. The frontend plan generates the certificate client-side using `html2canvas` on a React `<CertificateCard>` component.

These two approaches produce different outputs and serve different purposes. As written they are completely disconnected: the backend stores an S3 URL the frontend never uses, and the frontend generates a local image the backend never sees.

This matters most for the public share view and LinkedIn/OpenGraph previews — those require a stable, crawlable image URL (the S3 one). A client-rendered `html2canvas` export cannot serve as an OpenGraph image.

**Resolution:** Establish a single source of truth. The recommended split:

- **Backend (Pillow/S3):** Generates the canonical certificate image. This image URL is the one used in the public share view (`/certificate/[token]`), the `<meta og:image>` tag, and LinkedIn sharing. It is the permanent, stable record.
- **Frontend (html2canvas):** Can be used as an optional "high-quality download" that matches the live page styling, but should not be presented as the primary download. Alternatively, remove `html2canvas` entirely and have the "Download PNG" button download the S3 image directly via a signed URL.

Both plans need to be updated to agree on this split.

---

### 4. Field name mismatch — `time_limit_seconds` vs. `duration_seconds`

**Conflict:** The backend data model defines the field as `time_limit_seconds` on `AssessmentSession`. The frontend timer code references `session.duration_seconds`:

```ts
// Frontend plan (plan-frontend.md:97):
new Date(session.started_at).getTime() + session.duration_seconds * 1000 - Date.now()
```

This is a direct runtime bug. The field would be `undefined` and the timer would compute `NaN`, breaking the exam session.

**Resolution (frontend plan):** Replace `session.duration_seconds` with `session.time_limit_seconds` to match the backend schema. The OpenAPI-generated types (`types/api.ts`) would catch this at compile time once the codegen is in place.

---

### 5. Results page polling — Server Component cannot poll

**Conflict:** The backend requires polling `GET /sessions/{id}/results` because scoring runs asynchronously (~10–30 seconds). The backend plan explicitly notes: "The frontend polls this endpoint (e.g., every 3 seconds) until status is `completed` or `failed`."

The frontend plan lists `results/page.tsx` as a Server Component. Server Components render once at request time — they cannot poll. A user who lands on the results page before scoring completes will see a "pending" state with no way to update it without a full page refresh.

**Resolution (frontend plan):** The results page needs a client-side polling layer. The simplest approach: a `<ResultsPoller>` client component that calls `GET /sessions/{id}/results` on an interval and renders the score UI when status transitions to `"completed"`, or an error state when it becomes `"failed"`. The Server Component can handle the initial render and pass the initial status; the client component takes over from there.

---

## Significant Gaps

These issues won't cause immediate crashes but represent incomplete integration that will surface during implementation.

---

### 6. Autosave endpoint not wired to the frontend editor

**Backend:** `PATCH /sessions/{id}/questions/{qid}/autosave` accepts draft responses on a debounce from the editor.

**Frontend:** The response editor (`ResponseEditor`) is described in the exam session, but no autosave behavior is described. Responses live in Zustand until the candidate manually submits. If the browser crashes before submission, unsaved work is lost.

**Resolution (frontend plan):** Describe the autosave debounce: on every keystroke in the `ResponseEditor`, debounce a `PATCH /sessions/{id}/questions/{qid}/autosave` call (e.g., 2-second debounce). On session recovery (page refresh), `GET /sessions/{id}` should return the draft `response_text` for each question so Zustand can be rehydrated with in-progress responses.

**Note:** This also means `GET /sessions/{id}` must return per-question draft responses in its payload for in-progress sessions. The backend plan should confirm this is included in the response schema.

---

### 7. `POST /sessions/{id}/abandon` never called from the frontend

**Backend:** `POST /sessions/{id}/abandon` marks a session abandoned on explicit leave or inactivity. The backend's Redis-based inactivity tracker is a fallback, not the primary mechanism.

**Frontend:** The `beforeunload` handler and `useBlocker` hook prevent accidental navigation, but neither description mentions calling `POST /sessions/{id}/abandon` when the candidate confirms they want to leave.

**Note on `beforeunload`:** `fetch` calls are not guaranteed to complete during `beforeunload`. The correct mechanism for firing a reliable request at page unload is `navigator.sendBeacon`, which queues a request that completes even as the page tears down.

**Resolution (frontend plan):** When the candidate confirms leaving via the `useBlocker` dialog, call `POST /sessions/{id}/abandon` before navigation. In the `beforeunload` handler (for browser close/crash scenarios), use `navigator.sendBeacon` to fire the abandon endpoint.

---

### 8. Integrity events never emitted from the frontend

**Backend:** `POST /sessions/{id}/events` records integrity signals: `leave_page`, `return_to_page`, `inactivity_warning`, `tab_blur`, `copy_paste`. The admin review queue reads these alongside `flag_reason`. Without them, the flagging and review system has no supporting evidence.

**Frontend:** The exam session describes the inactivity warning dialog and `beforeunload` protection, but nowhere does it describe emitting `POST /sessions/{id}/events` for any of these signals.

**Resolution (frontend plan):** Add an integrity event emission layer to the exam session page. Signals to capture and their triggers:

| Event | Trigger |
|---|---|
| `tab_blur` | `document.visibilitychange` → hidden |
| `return_to_page` | `document.visibilitychange` → visible |
| `leave_page` | `beforeunload` (via `sendBeacon`) |
| `inactivity_warning` | When inactivity warning dialog is shown |
| `copy_paste` | `paste` event on the response editor |

These calls should be fire-and-forget (no awaiting, no retry).

---

### 9. Email verification — frontend blocks too broadly

**Backend:** Unverified users can log in and take Trial/Practice sessions. Only Exam sessions are blocked for unverified accounts. The `UnverifiedEmailRequired` exception applies specifically to `POST /sessions/{id}/start` when `mode="exam"`.

**Frontend:** "Until the email is verified, the dashboard renders a dismissible banner and exam start is blocked." The phrase "exam start is blocked" implies all assessment modes are blocked — inconsistent with the backend's more nuanced rule.

**Resolution (frontend plan):** The verification banner should appear on the dashboard. The Start Assessment flow should allow Trial and Practice modes for unverified users, but disable or hide the Exam mode option with a tooltip explaining verification is required.

---

### 10. AI chat 429 (turn limit) needs a distinct UI treatment

**Backend:** The `ai-chat` endpoint returns `429` when the 15-turn-per-question limit is reached, with a message explaining the cap. This is a business rule, not a transient error.

**Frontend:** The `useAIChat` hook handles stream errors with a retry option. A 429 from a turn-limit exhaustion should not show a retry button — retrying is pointless and would confuse the candidate. The UI should instead surface the "You've reached the AI assistant limit for this question" message and disable the input.

**Resolution (frontend plan):** `useAIChat` should distinguish between `429` (turn limit — disable input, show limit message) and other errors (network failure — show retry option).

---

### 11. AI chat history not confirmed in `GET /sessions/{id}` response

**Backend:** `ai_interactions` is stored as JSONB on `SessionQuestion`. The frontend uses this history to restore the AI chat panel after a page refresh. However, the backend plan's description of `GET /sessions/{id}` says "question content omitted until status='in_progress', full content included after status='completed'" — it does not explicitly confirm that `ai_interactions` is included in the in-progress response.

**Resolution (backend plan):** Confirm that `GET /sessions/{id}` (in-progress) includes the current `ai_interactions` array for each `SessionQuestion`. If it doesn't, the AI chat panel will be empty after a refresh, which is disorienting and a poor exam experience.

---

### 12. Trial/Practice sessions reach a results page with no score

**Backend:** Trial/Practice sessions are never scored — no `SessionScore` is written.

**Frontend:** `GET /sessions/{id}/results` is called by the results page. For Trial/Practice, the backend returns `{"status": "pending"|"failed"}` or a `409` — the behavior for unscored modes isn't specified in either plan. The frontend results page has no logic for handling the absence of a score.

**Resolution (both plans):**
- **Backend:** Specify what `GET /sessions/{id}/results` returns for a completed Trial/Practice session (e.g., `{"status": "not_scored", "mode": "practice"}`).
- **Frontend:** The results page should render a mode-appropriate view for Trial/Practice — showing the submitted responses and AI interactions without a score breakdown or certificate prompt.

---

## Minor Discrepancies

---

### 13. Leaderboard endpoint exists but no frontend page

The backend exposes `GET /leaderboard` (authenticated, opt-in, minimum population threshold). No corresponding frontend page is described. This may be an intentional deferral, but it should be noted as out-of-scope so the backend route isn't built without a consumer.

---

### 14. Admin interface is narrower than the backend exposes

The backend exposes several admin endpoints with no corresponding frontend pages:

| Backend endpoint | Missing frontend page |
|---|---|
| `GET /admin/stats` | Platform-wide stats dashboard |
| `POST /admin/sessions/{id}/rescore` | Rescore action on the session review page |
| `GET /admin/sessions/{id}/events` | SessionEvent log viewer for flagged sessions |
| `GET /admin/pipeline/runs` | Pipeline run history |
| `GET /admin/users`, `PATCH /admin/users/{id}` | User management page |

If these endpoints are in scope, the frontend admin section needs additional pages. If they are deferred, the backend plan should note them as backend-only for now.

---

### 15. Certificate 403 handling not described in the frontend

**Backend:** `GET /sessions/{id}/certificate` returns `403` if `total_score < 75`, or if the session mode is Trial/Practice (never scored).

**Frontend:** The certificate route exists at `app/app/session/[id]/certificate/page.tsx` but the plan doesn't describe how a `403` is handled — does the page redirect to results, show an inline message, or throw an error? This should be specified to avoid an unhandled error page.

---

### 16. Percentile rank may be null — dashboard needs to handle it

**Backend:** `percentile_rank` on `SessionScore` is nullable, set only once the population exceeds a minimum threshold.

**Frontend:** The dashboard shows "overall percentile rank." If the rank is null (early platform, small population), the frontend needs a fallback UI — e.g., "Percentile rank available once more candidates complete exams."

---

### 17. `PATCH /users/me` rejects email changes — frontend form should not offer the field

**Backend:** The `PATCH /users/me` endpoint explicitly rejects any `email` field with a `422`. Email change is not yet designed.

**Frontend:** The Account Settings page is described as "profile" but doesn't specify which fields are editable. If the settings form includes an email field, users will get a confusing `422` error when they try to change it.

**Resolution (frontend plan):** The Account Settings form should display the current email as read-only, with a note that email change is not yet supported.
