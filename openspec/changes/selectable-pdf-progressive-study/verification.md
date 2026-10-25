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

## Non-blocking formula display — October 25

The user explicitly prioritizes speed and accepts raw mathematical text. VPS reference `c7f8c8ee266b400a87fefa2c6004238c` returned all five requested problems in 12.970 seconds of provider time, then failed on the local `math_in_text` rule. Removed mathematical formatting rejection and Chromium preflight from generation. Counts, source ownership/citations, and exact-duplicate checks remain enforced; one provider request is unchanged.

The shared renderer now displays unsupported TeX as safely inserted raw text with its citation, rather than replacing the expression with an error message. The print renderer permits the same fallback. Raw mixed prose and TeX in titles/change descriptions no longer reject the set. Metadata reports `math_check: on_display` and `formatting_policy: best_effort` rather than claiming strict generation-time validation.

Verification: **60 tests passed** (one existing Starlette/httpx deprecation warning). New regressions cover raw prose, unsupported TeX, titles, and prose in math for both modes without extra provider calls; generation does not launch a validation browser. An authenticated API regression generated all five fixture cards containing unsupported TeX, saved them, exported a PDF, and confirmed the raw command was preserved in its text. This pass used fixture provider output, not a paid model call. Python/JavaScript syntax, strict OpenSpec validation and `git diff --check` passed.

Fix `e47cc25` deployed successfully in [Deploy run 40212182637](https://github.com/KovalovOL/mathPDF/actions/runs/40212182637). Public API headers confirm build `e528d384ad92`. A direct container check accepted a fixture item with bare TeX in prose and an unsupported command, using one fixture provider call and no validation browser. No user documents were accessed and no paid API request was made. This verification-record update skips CI to avoid restarting the live app again for documentation-only changes.

## Question-only flashcard fronts — October 25

The adapter previously appended each central formula to the flashcard question, and validation required a front-side formula. Removed that rule and placed central/question formula objects on the answer side. External prompts now request self-contained plain-English recall questions without answer formulas or hints. Workspace fronts omit item titles and sources, and use a neutral accessible card label. The back retains the title, formulas, explanation, citations and original variant expressions. The shared projection also handles older saved cards and browser drafts without modifying stored records. PDF questions use neutral Card N headings and keep formulas and titles in the answer section.

- Full suite: **65 passed**, one existing Starlette/httpx deprecation warning. Regressions cover back-only formula acceptance, repeated front formulas, variants, exact counts, one-request behavior, unchanged problem inputs, and both new/legacy PDF question/answer separation with raw-TeX fallback.
- Browser check used a disposable local database, loopback-only test-session harness, and fixtures matching the reported vector examples. Verified zero front formulas, links or item titles; answer reveal, keyboard flipping, navigation resetting to the question, inert/aria-hidden opposite faces, and variant original explanations appearing once. The harness is outside the repository and changes no production authentication.
- One real configured-provider request with the provided sample PDF, original pages 4–7: **5/5 flashcards in 6.11 seconds**, **one provider request**, 702 output tokens. All five questions were recall prompts without answer formulas. Opened the real result in the browser: membership notation was absent on the front and typeset correctly on the back with its page citation and explanation. Local result: ignored `artifacts/flashcard-recall-check.json`; screenshots: ignored `artifacts/ui/flashcard-recall-question.png` and `flashcard-recall-answer.png`.
- JavaScript syntax, strict OpenSpec validation and `git diff --check` passed. Mathematical correctness, semantic absence of every possible hint, and universal latency bounds are not established by this check; no extra model-based content filter or repair request was added.

Commit `66211d1` deployed successfully in [Deploy run 40213724805](https://github.com/KovalovOL/mathPDF/actions/runs/40213724805). Public API headers report build `070b81b0a723`, matching the local tested source; the public workspace asset contains the shared flashcard projection and neutral card label. Unauthenticated `/api/me` remains 401 JSON. No production user files or sessions were accessed. The temporary local UI server was stopped and its browser tab closed. This documentation-only completion record skips CI to avoid another live restart.

## Reusable LaTeX and source notation — October 25

The screenshots showed bare TeX inside prose, duplicate formulas, flattened exercise rows, invented equations for prose definitions and incorrect mathematical/source content. Added explicit paragraph parts with inline math objects; the adapter supplies delimiters. The provider generation schema now requests one complete flashcard question and structured answer paragraphs/formulas, with constrained prose decoding and a permissive local reader. Added `math-patterns.md` with reusable cross-topic structures and source-image/notation rules. A page-only central reference supports prose definitions without a fabricated equation, with selected-page/owner checks and answer-side citations. Kept the configured model and the single-request/no-repair generation policy.

The shared renderer recovers complete bare environments and bounded inline fragments in legacy prose, preserves explicit top-level row breaks with an aligned wrapper, and completes only a single unfinished terminal text-label brace. It does not infer missing fraction/overbar scope, substitute operators, fill mathematical blanks, decode entities into different symbols, or correct false statements. Exact standalone duplicates are suppressed with matching source/variant metadata. UI and PDF export use the same renderer.

Verification:

- **79 tests passed** with one existing Starlette/httpx deprecation warning. New regressions cover inline parts, decoding versus permissive parsing, one-question output, reusable guide JSON/TeX, source operator/bar/equality-order invariance, page-only definition ownership/save/export, screenshot-derived bare fragments, explicit row layout, and the bounded terminal-label repair.
- The user supplied `Homework  1.pdf` and `Vectors.pdf`. Visual inspection confirmed overbars can be vector strokes missing from text extraction. Source images remained local QA artifacts; study formulas remain editable LaTeX rendered as HTML/MathML, not images.
- Automatic review initially rejected external tests for lack of explicit permission for these files. The user then explicitly approved the listed pages of Homework, Vectors and main.pdf for OpenAI testing. All real requests used only those pages, isolated local data and a loopback-only test identity. No production sessions/documents were accessed.
- Iterative configured-model checks remained one provider request per generation. Observed examples: ten Homework cards in 12.30 s; revised five Homework cards in 6.61 s; five problems in 5.82 s; three vector cards in 4.42 s. Counts were exact and saves succeeded. These are individual measurements, not universal latency guarantees.
- A comparison using GPT-4.1 returned five Homework cards in 6.59 s and three vector cards in 4.11 s. The vector result correctly exercised page-only prose citation. The comparison still contained logical/source errors, so the application model was not changed and this is not evidence that upgrading alone ensures fidelity.
- Actual model output still included a false claim that an implication from true is a tautology, a misread overbar/option, and a rewritten equality order. Formatting/schema success does **not** establish literal transcription, mathematical correctness or pixel-identical PDF typography. These remaining model limitations are documented rather than hidden by another request or semantic rewriting. Old mathematical errors require regeneration/correction; renderer recovery alone cannot recover missing source information.
- Browser checks confirmed question-only fronts, a rendered source truth table and citation navigation, source-page-only definition display, and legacy environment/inline recovery. One malformed terminal text label found in a generated explanation motivated the bounded syntax repair and regression. Screenshot: ignored local `artifacts/ui/latex-truth-table.png`.
- Exported three existing generated sets through the local API, including inline binomial/factorial formulas, labelled rows and a page-only definition; PDFs had 3, 3 and 2 pages. Rendered answer pages were visually inspected. Unsupported content remains readable instead of discarding a set.
- JavaScript syntax, strict OpenSpec validation and `git diff --check` passed. Source PDFs and test artifacts are not included in the commit.

Commit `e1804b3` deployed successfully in [Deploy run 40237882149](https://github.com/KovalovOL/mathPDF/actions/runs/40237882149). Public `/api/me` reports build `9d64a1cd750b`, matching the committed local source, and remains 401 JSON without a session. Browser verification confirmed the terminal-label repair removed the remaining raw formatting fallback in the inspected five-card set; this does not establish its mathematical correctness. The temporary local server and browser tab were closed. The completion-record commit skips CI to avoid another live restart for documentation only.

## Literal conjunction ampersands - October 26

The remaining screenshot showed conjunction ampersands disappearing from mathematical rows and raw inline equivalences in the explanation. A raw ampersand was being consumed as an alignment tab, or rejected outside an alignment environment. Added local display escaping outside column contexts and bounded recovery for a single-letter Boolean conjunction immediately before a logical relation in aligned rows. Actual relation alignment markers and table/matrix/cases column separators remain structural. The legacy prose scanner now recognizes raw ampersands and LaTeX commands immediately followed by digits. The external pattern guide includes escaped conjunctions alongside genuine alignment markers.

- **81 tests passed**, with one existing Starlette/httpx deprecation warning. Coverage includes explicit and bare inline expressions, unwrapped and aligned rows, existing overbars, unchanged arrays/matrices/cases, starred matrices, nested environments, repeated rendering, and save/export preservation. The API regression retains the original stored formula and exports four visible ampersands, using one fixture provider call.
- A disposable local account and screenshot-derived fixture reproduced the reported display, including the already incorrect unnegated row from the screenshot. Browser inspection confirmed four visible ampersands and no raw TeX in the inspected answer. Saved QA screenshot: ignored `artifacts/ui/conjunction-ampersands.png`.
- Exported the same fixture through the local API, rendered its answer page with Poppler and visually inspected it. The two-page export contains four visible ampersands and no raw `Leftrightarrow` command. No paid provider request was made.
- Recovery is shared by workspace and export and does not rewrite saved records, substitute a wedge, infer a missing negation, or prove a mathematical equivalence. In aligned environments, the conjunction recovery is deliberately limited to the reported Boolean operand/relation shape; arbitrary ambiguous columns are not treated as conjunctions.
- JavaScript syntax, strict OpenSpec validation and `git diff --check` passed. Source PDFs, screenshots, test exports and the loopback harness are not included in the deployment.

Commit `a889bbb` deployed successfully in [Deploy run 40239282745](https://github.com/KovalovOL/mathPDF/actions/runs/40239282745). Public `/api/me` remains 401 JSON and reports build `f257365e2f62`, matching the tested local source. The public renderer asset matches the local file byte for byte. The disposable local server was stopped and its browser tab closed. This completion-record update skips CI to avoid another restart for documentation only.
