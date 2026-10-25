# Implementation review

## Completed checks

- `node --check` passed for `app.js` and `math-renderer.js`.
- `node --input-type=module --check` passed for `pdf-viewer.js` and `pdf-source.js`.
- Python compilation passed for `study.py`, `providers.py`, and `math_validation.py`.
- `git diff --check` passed.
- `openspec validate selectable-pdf-progressive-study --strict` passed.
- Reviewed iframe origin/window checks, readiness messaging, text-layer cancellation, resize anchoring, selection-aware pruning, interrupted navigation, goal-slot ordering, bounded repairs, source scope, old-set defaults, renderer reuse, and browser cleanup.

No automated tests or paid OpenAI requests were run. The authenticated reader and generation flow were not exercised in this pass. Static checks do not establish visual alignment for every PDF or semantic correctness/diversity of generated material.

## Limits

- Selection/copying depends on the digital PDF's text layer; no OCR is added.
- Citation navigation uses source pages only, following the user's revised preference. Individual fragments are not highlighted.
- Difficulty is model-assessed, and near-duplicate detection is conservative.
- KaTeX preflight validates rendering syntax, not mathematical correctness or exact source typography.
- Older flattened prose/formula blocks may require regeneration.

## Deployment

Code commit `73be534` was pushed to `main`. The existing [Deploy run 40202427132](https://github.com/KovalovOL/mathPDF/actions/runs/40202427132) completed successfully, including its `/opt/mathPDF` build/restart step. The local development server was also restarted with the updated imports.

A follow-up commit records completion and ensures that interrupted citation navigation still expires its highlight. This does not establish authenticated end-to-end behavior or model output quality.

## Production recovery after the reported failure

The user reported failure to generate ten flashcards. SSH inspection found the application container running, `oom=false`, and `restarts=0`. Its log contained a JSON EOF parsing error; the user-facing error showed exhaustion of item recovery. Previous logs did not retain the item rejection mix, so the exact historical combination cannot be reconstructed.

The recovery change checks response completion before JSON parsing, shortens plans and batches, includes rejected candidates/renderer diagnostics in repair prompts, accepts preflighted delimited prose math, validates citations against the whole selected primary range, and narrows heuristic paraphrase rejection to the same planned activity. In-process owner-scoped jobs expose progress and cancellation with bounded browser requests and cleanup. New application logs record phases, counts, and safe rejection codes. Fragment matching, row highlighting, and precise quotation requests have been removed at the user's request; selectable PDF text and brief animated page navigation remain.

Static Python/JavaScript syntax checks and strict OpenSpec validation cover the recovery changes. No automated tests or paid model requests were run. Production deployment/startup inspection is recorded after the recovery push; successful deployment alone does not establish the quality of a fresh model-generated set.

Recovery code commit `38a36c8` deployed successfully in [Deploy run 40204801519](https://github.com/KovalovOL/mathPDF/actions/runs/40204801519). SSH inspection confirmed the newly created container was running with `oom=false`, `restarts=0`, and clean application startup logs. The local server also started successfully. The user chose to try the new ten-flashcard generation later; successful generation of that exact case remains unconfirmed.

## Unreadable-response diagnostics

The later screenshot reported an unreadable API response. VPS logs still contained only startup entries. Deployed Python and public JavaScript hashes matched local files. A public unauthenticated `/api/me` read returned 401 JSON; the JS response had no cache-control header. The exact failing authenticated response was not captured, so neither a redirect nor a cache problem is established as its cause.

Added correlated HTTP/job/provider events, build/reference headers, sanitized exception stack locations, browser content-type/JSON diagnostics and bounded authenticated metadata reports. Primary HTML versions its local scripts/styles, while JS/CSS require revalidation. Docker log rotation is configured and operational commands are documented in `docs/diagnostics.md`.

Python compilation, JavaScript syntax, strict OpenSpec validation and `git diff --check` passed. The local server started and emitted its diagnostics-enabled startup event. No automated tests, fabricated authenticated sessions, or paid generation requests were run. Deployment/header/log observations follow after the diagnostics push.

Diagnostics commit `06c0bae` deployed successfully in [Deploy run 40206901154](https://github.com/KovalovOL/mathPDF/actions/runs/40206901154), build `d6930c11afdb`. Read-only live inspection confirmed `/api/me` returns 401 JSON without a session, echoes the supplied reference `a3a31c8ecc854b60993c161c253fb0f1`, and emits matching HTTP started/finished log entries. `/login` returns versioned script URLs with no-store caching; `/static/account.js` returns no-cache and the same build header. The container's diagnostics-enabled startup event is visible in Docker logs. These observations confirm logging/header delivery, not successful authenticated generation or reproduction of the original unreadable response.

## Real renderer and generation verification — October 25

This pass supersedes the earlier static-only verification limits for the generation path. The user explicitly requested local API and browser testing.

- Reproduced the production rejection locally using the actual bundled KaTeX and Chromium: `x+1` and a valid fraction both failed because the blank document was in `BackCompat` (quirks mode). After initialization with a doctype, the document reports `CSS1Compat`, valid formulas pass, and an unsupported command still fails.
- Added renderer startup self-check coverage and verified a renderer fault stops before any provider calls. Updated the obsolete prototype web-route tests to cover current authenticated routes, ownership, exact-count jobs, persistence, and terminal renderer errors. Full suite: **21 passed**, one existing Starlette/httpx deprecation warning.
- Used an isolated temporary local database and test identity/session. The Google identity exchange was not exercised; production authentication was not changed. Test harness code remains outside the repository and binds only to loopback.
- Real configured provider (`gpt-4.1-mini`), `main.pdf`, original pages 4–7, API job: **10/10 flashcards**, ordered goals 1–10, strict renderer validation, successful explicit save, **161.3 seconds**. Ten item-batch attempts included six prose-format rejections, one truncated response, and one actual formula-format rejection; bounded repairs completed the exact set.
- Separate real browser submission for **5 flashcards**, same selected pages: **5/5 completed**, approximately **145 seconds**, four item-batch attempts including recovery from one truncated response. Inspected each card and flipped each answer; the DOM contained KaTeX output and no formula error elements across all five cards. Screenshot: ignored local artifact `artifacts/ui/generation-five-cards.png`.
- Strict OpenSpec validation and `git diff --check` passed. These checks establish this reproduction and successful rendering, not pixel-identical reconstruction, semantic correctness for every formula, or a latency guarantee. Model truncation/repair can still add substantial waiting time.

Fix commit `6b3a98d` deployed successfully in [Deploy run 40208498587](https://github.com/KovalovOL/mathPDF/actions/runs/40208498587). The live container started with build `70e46fcf59e1`. A direct check inside that container confirmed standards mode, accepted valid fractions/sums/simple formulas, and rejected an unknown TeX command. This live check did not access user documents or call OpenAI. The temporary loopback browser-test server was stopped after verification.

## Single-request latency verification — October 25

The user replaced the earlier plan/batch/repair policy with one model request and a detailed formula guide. Removed planning/repair prompts and provider methods, kept exact counts and local strict rendering, and reduced provider output to compact items with a required central source formula. Old saved sets retain the canonical format.

Exploratory guide/schema drafts were rejected locally for prose-only items, raw TeX in prose, double escaping, or a dangling escape; no individual generation retried its model call. Added the required formula field, conventional delimited inline math, and bounded deterministic formatting normalization before final validation. The guide is `formula_lab/prompts/formula-guide.md`; original PDF data and the configured `gpt-4.1-mini` model remain the benchmark inputs.

Final real-provider API benchmark, isolated local storage/test identity, `main.pdf` original pages 4–7:

| Mode | Count | Provider requests | Wall time | Model output tokens |
| --- | --- | --- | --- | --- |
| Flashcards | 10/10 | 1 | 9.97 s | 1,031 |
| Problems | 10/10 | 1 | 10.85 s | 1,419 |

Both complete sets passed strict local KaTeX validation and explicit save. The earlier same-source 10-card benchmark took 161.3 seconds. This is a measured comparison, not a universal latency guarantee for other documents, counts, complexity, or provider load. Timing artifact: ignored local `artifacts/single-request-benchmark.json`.

Separate browser submissions completed 10/10 flashcards and 10/10 problems. Server logs recorded 7.779 s and 11.941 s respectively for collection/self-check/local validation (excluding input preparation and browser polling). Each job made one provider call. Inspected all twenty item tabs: KaTeX content was present and no formula error elements were found. Verified a card flip and waiting UI completion. Screenshot: ignored local `artifacts/ui/fast-generation-problems.png`.

Full test suite: **54 passed**, one existing Starlette/httpx deprecation warning. Tests cover counts 1/10/15 in both modes, no second request after invalid math/short or duplicated content/source failures/provider errors, one SDK attempt on truncation/refusal/timeout/schema errors, compact response expansion, exact citations, variants, mandatory formulas, escaping normalization and preservation of valid matrix/aligned rows. Python compilation, JavaScript syntax, strict OpenSpec validation and `git diff --check` passed. Google identity exchange was not tested; the temporary test harness is loopback-only and is not shipped.

Single-request commit `6fc719a` deployed successfully in [Deploy run 40211198740](https://github.com/KovalovOL/mathPDF/actions/runs/40211198740). The VPS app started with build `c4ec4872cc6d`, matching the committed local source. Direct container inspection confirmed the formula guide is present, the planning method and continuation prompt are absent, the overall deadline is 150 seconds, normalization and valid aligned formulas pass KaTeX, and an unsupported command still fails. No production user files were accessed or provider calls made during this live check. The temporary browser-test server was stopped. The full committed-version suite again passed all 54 tests.
