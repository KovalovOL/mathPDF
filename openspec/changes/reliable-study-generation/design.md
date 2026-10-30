# Design

## Context

The service currently makes one provider call, prompts for "up to" N items, caps all schemas/UI at 10, and accepts any smaller response. Formula checks run only after the whole response and expose internal validation messages. Home lists owned files as text rows. PDF.js, private file endpoints, and account-aware requests are already available.

## Goals / Non-Goals

Goals: enforce the requested count across API, provider schema, generation orchestration, saved results, and UI; recover from individual invalid items without weakening formula/source requirements; add useful previews and waiting feedback.

Non-goals: verifying mathematical truth or universal PDF typography, inventing formulas to meet counts, semantic duplicate detection, background job infrastructure, persistent thumbnail storage, or changing authentication.

## Decisions

### Exact batches with an explicit insufficiency branch

Accept counts 1–50 and request batches of at most 5 to avoid long responses hitting output limits. Extend the provider interface with the expected batch count. Build a strict Pydantic response envelope containing a nested union: completed batch with equal min/max array size, or insufficient-source reason. This permits honest failure while constraining successful provider output. The final canonical set retains the existing items/notes layout and adds requested-count and attempt metadata.

Structured Outputs supports array bounds and nested `anyOf`; refusals/incomplete outputs still need handling. See [official OpenAI documentation](https://developers.openai.com/api/docs/guides/structured-outputs). Keep the configured model unchanged. Prefer this over merely changing "up to" in the prompt, which would not enforce output length.

### Validate, retain, and top up

Validate each candidate's required formula and selected-page citations. Retain valid items, reject exact repeated question content using a stable fingerprint, and request replacements with an external continuation/repair prompt containing accepted content and machine-readable rejection codes. Allow at most ceil(N/5)+3 provider calls and a 600-second overall generation deadline. Treat incomplete/schema errors as repairable; credentials, quota, and other API failures remain actionable errors. Insufficient-source responses and exhausted recovery return no partial success. Do not repeat accepted items or drop formula checks to reach N.

All natural-language LLM instructions remain under `formula_lab/prompts/`. The continuation prompt explains distinct learning angles on source formulas and forbids unrelated formulas, fabricated citations, or duplicates. Final validation checks exact count and existing ownership boundaries before returning the set.

### Lazy browser previews

Render first PDF pages using the existing vendored PDF.js at thumbnail resolution. Use an IntersectionObserver and at most two concurrent preview jobs; destroy loading/document resources after rendering or when the library reloads. Reuse the private file URL and account header, handle expired/switched sessions through the shared session helper, and leave open/download links intact on failure. Images use contained thumbnails; TXT/Markdown show escaped plain-text excerpts. This avoids adding a server imaging dependency or another private asset cache.

### Waiting status

Add a status panel inside the study pane with a CSS spinner, requested count/type, and elapsed time. Preserve existing sets and keep the PDF readable. No percentage is shown because batching progress is not streamed. Use reduced-motion styles and cleanup in `finally`, including timer and buttons. Warn before leaving an active generation as for other unsaved work.

## Risks / Trade-offs

- More calls increase latency and cost → small bounded batches, finite repair budget, overall deadline, and visible waiting state.
- Source content may not support enough distinct items → explicit insufficiency branch and no successful short set.
- Exact-question fingerprints cannot detect paraphrased duplicates → include accepted items in continuation prompts and document the limit.
- Client previews load original bytes → lazy loading, two-job concurrency, small canvases, and prompt resource destruction.
- Existing saved sets can have fewer items → enforce requested count for new generation; keep old canonical sets readable and exportable.

## Migration Plan

No database migration or data deletion. Deploy code, prompt, and frontend changes together. Existing saved sets remain supported up to the raised maximum. Rollback restores previous generation limits without changing stored data.

## FIFO queue follow-up
Use the existing fair asyncio lock with at most 20 unfinished jobs and one per owner. Keep status running for older polling clients and add phase queued plus queue_position. Cancel waiting tasks without releasing another job's lock. New clients refresh their waiting deadline while queued. Queue jobs remain process-local; restarts interrupt unfinished jobs. Existing sessions, storage and daily allowances remain unchanged. Deployment retains the existing brief restart; zero downtime is not guaranteed.
