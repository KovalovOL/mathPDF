# Design

## Context

See proposal.md for motivation. The reader uses vendored PDF.js 6.4.299 and retains the old canvas during resize renders. Generation uses one request for the complete set, validates counts and source ownership locally, and enforces the requested count. KaTeX is shared by the UI and Chromium PDF export. Prompts live in separate English files.

## Goals / Non-Goals

**Goals:** Preserve the stable reader geometry; make citations useful when model line numbers are unavailable; request varied progression within the single response; keep complete sets usable even when formatting is imperfect.

**Non-Goals:** OCR, arbitrary PDF editing, proof of mathematical correctness, and a guarantee of pixel-identical reconstructed formulas. Older corrupted mixed prose/math blocks cannot always be reconstructed automatically.

## Decisions

1. Add the PDF.js TextLayer above each canvas, with its matching CSS scale and rotation rules. Render text independently and cancel obsolete text work during resize/pruning. Retain the old canvas until replacement is ready. Preserve pages participating in an active selection. A canvas alone cannot provide selection.
2. Use source-page citations with a viewer-ready handshake and settled viewport measurement. Following the user's revised preference, remove quotation matching and row highlighting. Keep the text layer for selection/copying, independently of source navigation.
3. Use a short cancellable animation for explicit citation jumps, respecting reduced motion. Resize anchor restoration remains immediate. A global smooth-scroll rule would interfere with resizing.
4. Call the provider exactly once for the whole requested set. Remove separate plan models/prompts, batch loops, continuation prompts, and automatic repair calls. Ask for varied reasoning and easier-to-harder order within the generation prompt. Keep optional persisted goal identifiers readable and assign new sequence identifiers locally.
5. Use a compact provider response: a required central formula for every item, prose strings and additional formula objects with TeX, original page, and an optional variant description. Fill canonical citation document IDs, null line/quote fields, and display defaults in the adapter. This reduces generated syntax without changing saved sets, the renderer, or export.
6. Load the external formula guide and normalize common encoding errors locally. Validate counts, required formula presence, citations and exact duplicates. Do not preflight mathematical syntax or launch Chromium during generation. The UI and export typeset supported expressions and preserve unsupported TeX as readable text; no extra provider request is made.
7. Add a conservative legacy renderer for standalone TeX lines; retain ordinary paragraphs and escape all generated prose. No arbitrary provider HTML is executed.

## Risks / Trade-offs

- [Text extraction order and glyph mappings vary] → Retain the original page canvas and use the text layer for selection; source navigation requires only the original page number.
- [One response can still be slow or invalid] → Compact output, concise complete answers, one provider request with SDK retries disabled, a 150-second overall deadline, and explicit terminal errors. Record measured latency; do not promise a universal 20-second bound.
- [Difficulty and variety are model assessments] → Guide whole-set variety/progression and reject exact duplicates locally, without claiming semantic uniqueness or mathematically proven difficulty.
- [Some model output may not typeset] → Show escaped raw text for that expression instead of blocking the set. Chromium is needed only for PDF export.
- [Text overlays consume memory] → Prune distant pages except active selections and cancel stale render work.

## Migration Plan

Deploy with the existing workflow. No database migration is required: new goal identifiers are optional for persisted sets. Rollback restores the previous assets and generator; new metadata is backward compatible.

## Historical production recovery (superseded by single-request generation)

The VPS container remained running without OOM/restarts, while generation exhausted recovery and its log showed truncated JSON. Existing logs did not record item rejection codes. Inspect provider completion status before schema parsing, keep plans concise, and use two-item batches (one after truncation). Replacements receive the actual rejected candidate and renderer diagnostic, rather than a generic code alone. Log phases, counts and rejection codes without source content or secrets.

The plan's supporting pages are guidance within the user's selected primary pages, not a narrower authorization boundary. Validate citations against the full selected primary scope. Correctly delimited prose mathematics already supported by the shared renderer can pass the same strict preflight. Near-duplicate wording checks apply within the same planned activity; exact duplicates remain prohibited across all activities.

Keep job state in memory for this single-process deployment: reserve the existing global generation lock at creation, bind jobs to their owner, expose short create/status/cancel endpoints, and expire completed results after 15 minutes. Cancel pending tasks on shutdown. Restarted jobs are lost explicitly, never shown as successful. No queue service, worker, migration, or new dependency is needed. Keep the synchronous endpoint for compatibility; the workspace uses jobs with per-request and overall deadlines.

The affected user requested ten flashcards. They explicitly revised source navigation to page references with smooth scrolling, without fragment highlighting. New generation sets quotation and line fields to null, reducing output overhead while retaining old-set compatibility.

## API diagnostics

A later unreadable-response report had no generation entries in VPS logs. Deployed code hashes matched the repository; a public unauthenticated API read returned JSON, and JavaScript assets lacked cache-control headers. The exact failing response is not known. Add request/build identifiers, route/status/content-type/duration logs, safe stack locations for unhandled errors, and context propagation into generation jobs/provider calls. Keep polling success logs at DEBUG to avoid flooding logs.

The browser records status, content type, redirect state, route and correlation ID for failed JSON responses. A bounded authenticated diagnostic endpoint receives only allowlisted metadata, never response bodies, cookies, headers, prompts or PDF content. Serve primary HTML with content-versioned local JS/CSS URLs and require asset revalidation to prevent stale UI code after deployment. API errors remain English and display a reference for log lookup. No external logging service or new dependency is required.

## Renderer regression recovery

Production logs showed every candidate rejected as invalid math. A real local Chromium reproduction rejected even `x+1` with KaTeX's quirks-mode error: the validator used an `about:blank` document without a doctype. Initialize a standards-mode HTML document before loading the renderer, matching the UI and export. Run a known-valid expression self-check before any provider request and treat a failed self-check as an operational error with bounded cleanup. Preserve strict candidate validation. Regression tests must use the actual bundled KaTeX and Chromium; the user now explicitly authorized real provider, API and browser verification.

## Single-request latency revision

The user explicitly prioritizes latency and replaces the previous planning/batch/repair policy. Generate flashcards and problems in one request, without retrying invalid or incomplete content. The formula guide replaces repair instructions and includes JSON escaping, block boundaries, mathematical environments, source notation, and variants. Keep the configured model and original selected PDF inputs. Retain exact-count validation and page ownership; never silently discard invalid items or manufacture missing content. Measure real provider calls and end-to-end durations for both modes before deployment.

## Non-blocking formatting revision (current policy)

The user explicitly accepts raw formulas and prioritizes speed/usability. Request c7f8c8ee266b400a87fefa2c6004238c returned five problems in about 13 seconds, but the service rejected the complete set for math in prose. This supersedes strict generation-time math rejection and renderer startup checks described above. Remove Chromium validation from generation and treat formatting solely as a local display concern. Keep the external guide and deterministic normalization. Render supported expressions with KaTeX; render unsupported expressions as escaped raw text in the workspace and export. Do not require plain titles/change descriptions to pass a TeX-free schema. Preserve exact counts, source/owner validation, and one provider request.
