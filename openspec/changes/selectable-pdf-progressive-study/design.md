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
8. Flashcards use recall questions written without the answer or hints. Put the central formula and any question-array formula objects on the answer side in the provider adapter. The shared display helper also relocates formula blocks in older cards without changing stored records. Show titles, citations and variant explanations only on the back; use neutral accessible card labels. Apply the same separation to exported questions/answers. Problems retain their question inputs. This is local processing, with no additional provider request.
9. Add compact paragraphs with ordered prose/inline-math parts. The adapter supplies math delimiters; the model does not need to manage delimiters inside explanations. Constrain prose in the generation schema while keeping local parsing permissive for formatting errors. Retain canonical saved text/math blocks. Load reusable English examples of layout structures, with explicit instructions to copy symbols, rows and source notation rather than substitute equivalent formulas. Remove only exactly repeated standalone expressions on each side; preserve inline explanatory uses, variant metadata and distinct source citations.
10. Recover complete supported bare environments before scanning legacy prose. Recognize bounded unambiguous TeX fragments with balanced arguments and adjacent mathematical operands, keeping English outside math. Do not guess a missing right-hand side, change logical operators, decode HTML entities as mathematical corrections, or convert a diagram into an invented equation. These changes are local display improvements, not proof of source fidelity or mathematical correctness.
11. Allow a page-only central reference for material expressed only in prose or a diagram. Expand it into an optional canonical item citation and require that citation to be in the selected primary source scope. The answer displays the citation in both workspace and export. This removes the artificial requirement to fabricate a mathematical equation for a vector definition. Existing items without the optional citation remain compatible.
12. Escape literal raw ampersands locally before typesetting. Keep structural column separators in arrays, matrices and cases, and alignment markers in aligned equations. Recover the reported single-letter Boolean conjunction before a logical relation in an aligned row; keep the ampersand glyph rather than substituting a wedge. Recognize the same operator in legacy prose. Recovery affects display only, is shared with export and makes no model request. It cannot recover a negation or other source symbol omitted by the model.
13. Version the canonical study-set payload with `schema_version: 1`, defaulting missing markers to version 1 for every existing record and browser draft. Freeze representative historical payloads as compatibility fixtures. New readers must retain every previously supported persisted format through defaults or explicit non-destructive upgrades; do not remove old readers or change field meaning silently. An incompatible change is allowed only for a major change with the project owner's explicit approval. Older releases are not required to read newer payloads.
14. Reuse one text/math fragment parser for rendering and flashcard projection. Move explicit inline/display math and recognizable legacy TeX in question text to the answer, preserving the surrounding question and original stored payload. Retain unsupported expressions on the answer as raw text, preserve standalone citations/variants, and avoid repeating an inline expression already present as an answer formula. This shared UI/export rule applies to every provider and old sets. It is not a semantic detector for answer hints written entirely in ordinary prose.

## Risks / Trade-offs

- [Text extraction order and glyph mappings vary] → Retain the original page canvas and use the text layer for selection; source navigation requires only the original page number.
- [One response can still be slow or invalid] → Compact output, concise complete answers, one provider request with SDK retries disabled, a 150-second overall deadline, and explicit terminal errors. Record measured latency; do not promise a universal 20-second bound.
- [Difficulty and variety are model assessments] → Guide whole-set variety/progression and reject exact duplicates locally, without claiming semantic uniqueness or mathematically proven difficulty.
- [Some model output may not typeset] → Show escaped raw text for that expression instead of blocking the set. Chromium is needed only for PDF export.
- [Text overlays consume memory] → Prune distant pages except active selections and cancel stale render work.

## Migration Plan

Deploy with the existing workflow. No database schema migration is required: new goal identifiers, item citations and the version marker have backwards-compatible defaults, and the new reader accepts old saved sets without rewriting their stored JSON. Compatibility is required from old data to new readers. Older readers are not required to accept new payloads; an operational rollback must retain the newer reader support for records already written. Do not rewrite or delete owned saved sets as part of deployment.

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
