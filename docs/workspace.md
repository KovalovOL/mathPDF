# Study workspace

## Documents and storage

Google sign-in is mandatory. `/` is the personal library; selecting an owned file opens `/workspace?document=<id>`, and selecting a saved set opens `/workspace?set=<id>` with its source PDF. The library starts empty and offers Upload files. It accepts PDF, UTF-8 TXT/Markdown, PNG, JPEG, and WebP uploads. Generation is enabled after a PDF is available. Each file is limited to 25 MB; text files to 1 MB; images to 40 megapixels. PDF uploads must be readable and unencrypted. Original filenames are display metadata; managed binaries use content hashes and opaque document IDs.

`Workspace` is the local storage adapter. SQLite users, sessions, document metadata, and saved sets live at `<data-dir>/workspace.sqlite3`; binaries live at `<data-dir>/documents/<owner-id>/`. The default data directory is `.formula-lab/`. Every repository read/write requires the authenticated owner; duplicate hashes are unique per account. Foreign IDs return generic not-found responses, including when used as generation context or export sources. A saved-set upsert cannot overwrite another owner's identifier. The user-authorized ownership migration deletes old unowned managed uploads and saved sets once. Owned data survives subsequent restarts. Garage integration remains future work.

Startup and the Docker image require no PDF. Shared legacy source-inspection HTTP routes and the `--pdf` option have been removed from the web application. `GET /api/generation/config` returns `default_document_id: null`; generation requires an owned primary document ID. See [authentication setup](authentication.md) for Google credentials, session behavior, and local configuration.

- `GET /api/me`: the current account's ID, name, and email.
- `GET /api/documents`: list the current account's document metadata.
- `GET /api/documents/{id}`: authorize and return one document's metadata before showing a cached page.
- `POST /api/documents`: upload one multipart `file`.
- `GET /api/documents/{id}/file`: preview a managed file; `?download=true` returns an attachment.
- `GET /api/documents/{id}/annotations` and `PUT /api/documents/{id}/annotations`: read/save the versioned editable PDF layer with owner and revision checks; see [PDF annotations](annotations.md) for usage, copy lifecycle and the payload contract.
- `GET /api/study-sets`: list the current account's explicitly saved sets.
- `GET /api/study-sets/{id}`: load the canonical saved set.
- `POST /api/study-sets`: save or update a validated set with its source/context snapshots, editable math, quiz originals, and generation metadata.

- `GET /api/documents/{id}/deletion` and `GET /api/study-sets/{id}/deletion`: review the deletion title, primary-source consequences, context detachments and revision.
- `DELETE /api/documents/{id}` and `DELETE /api/study-sets/{id}`: confirm permanent deletion with the reviewed revision in `If-Match`. Missing review returns 428; changed impact returns 409 and requires review/confirmation again.

All these APIs require a live session; unsafe methods also require the trusted application Origin. Generation drafts are not saved automatically. Saved sets survive restart. Document tabs retain their preview instances and reading positions while the workspace is open. Browser preferences are scoped by account ID.

Home displays responsive file cards with the first PDF page, an image thumbnail, or an opening plain-text/Markdown excerpt. Previews load near the viewport with at most two concurrent jobs using the existing owner-protected file endpoint. PDF resources are destroyed after rendering, image bitmaps are released, and queued requests are canceled when the library reloads or closes. Original file bytes are not stored in a separate thumbnail service. Preview failure leaves the file's workspace link and download action available.

File-tab close controls remove previews, not stored documents. **Open** lists saved files, including closed ones. The open saved-file tab list persists in browser local storage. New files appear immediately as unsaved upload tabs; confirmation is required to close and cancel an unfinished or failed upload. Failed uploads retain the local file for **Retry upload** while the page is open. Leaving the browser page with pending uploads triggers the browser's unsaved-change warning. A request already committed by the server can remain in the library after cancellation.

**Files** and **Saved study sets** are independent disclosure sections. Their open state is remembered per account. Each file/set has a **Delete** action with a modal confirmation and a safe default focus on Cancel. A bold warning states how many saved sets will also be deleted because the file is their **main source**. Context-only sets remain and lose only the deleted attachment; their existing items, formulas and metadata are preserved. Deleting a set retains all files. Ownership and an atomic impact/revision check apply on the server, including concurrent changes after the dialog opens. These are explicit user deletions, not data-format migrations.

## Browser visual cache

IndexedDB stores derived previews under the account ID, document ID, SHA-256, renderer revision and page number. Home checks an authorized library listing before using cached thumbnails or text excerpts. PDF viewers authorize individual document metadata before showing any cached page. Private API responses and original file bytes are not placed in a public or service-worker cache.

The cache keeps at most 150 home previews and **ten recently viewed page images total per account**, across documents, using least-recently-used eviction. Each group is limited to 30 MB and each entry to 6 MB. Only the page being read enters the page cache; neighboring prefetched pages do not evict the reading history. Cached images retain page proportions and display during PDF loading, then are replaced by the full canvas and selectable text layer. Original PDFs still require an online authenticated request; this is not an offline reader.

File deletion purges its entries. Sign-out purges the account's entries, and cross-tab invalidation prevents in-flight writes from restoring purged entries. Browser eviction, disabled storage, quota errors and incompatible visual-cache revisions fall back to ordinary rendering. Original documents, canonical study sets and historical format compatibility are unaffected.

Derived images are persisted as byte buffers with MIME types, then reconstructed as in-memory images. This avoids repeatedly writing IndexedDB-backed Blobs, a failure reported in [WebKit issue 240216](https://bugs.webkit.org/show_bug.cgi?id=240216). Readable older Blob entries migrate locally; unreadable entries are treated as misses. Cached images are decoded before insertion, with a bounded timeout; a failed entry is removed and the authorized original renders normally. This applies to both home previews and PDF page images. A late failure cannot delete a newer replacement. The initial PDF render queue also starts explicitly once the parser is ready, without waiting for a resize or pointer event.

## Generation request

Reading always exposes the entire PDF. Only the generation dialog chooses what is sent to the model. Its inclusive From/To endpoints support both a range and one page; Entire PDF sends all pages. Each enabled PDF context file has its own independent selection. Text and images are attached in full.

```json
{
  "document_id": "primary-document-id",
  "pages": [5, 6, 7],
  "context": [
    {"document_id": "example-pdf-id", "pages": [2, 3]},
    {"document_id": "instructions-text-id", "pages": null}
  ],
  "comment": "Focus on notation and include a sign-error question.",
  "mode": "flashcards",
  "count": 4
}
```

`pages: null` selects an entire PDF. The service allows up to six context files, 100 PDF pages across all selected files, 40 MB of combined selected bytes, and 1–50 requested items. It validates all selections before the provider request. Page subsets are copied into in-memory PDFs; no formula catalog or full-text extraction is required.

`comment` is optional, defaults to an empty string, and is limited to 4,000 characters. It is independent of context attachments. `prompts/comment.md` supplies its instruction text; the runtime comment is inserted as a JSON string and cannot relax source, citation, or schema requirements. The generated and saved canonical set retains the trimmed `comment`. Existing saved sets remain readable with the empty default.

`StudyProvider.generate(documents, system, task, count=..., mode=...)` receives the complete requested count and is invoked once. The OpenAI adapter sends selected PDF/text files as file inputs and images as image inputs, with SDK retries disabled. There is no planning call, batch loop, continuation request, or model repair request.

### Formula guide and compact provider output

All LLM instructions remain separate English files in `formula_lab/prompts/`. `study-system.md` requests variety and an easier-to-harder whole-set order; the mode file supplies the exact count and original-page mapping. `formula-guide.md` is the complete writing contract: prose/formula boundaries, JSON versus TeX escaping, self-contained expressions, fonts/operators, fractions, indices, delimiters, matrices, aligned rows, piecewise definitions, sums, integrals, citations, deliberate variants, and a silent final checklist.

`math-patterns.md` supplies reusable LaTeX structures across topics: ordered text/math paragraph parts, bars/accents, original operators, labelled rows, truth tables, matrices, cases, fractions and sums. Examples specify structure, not substitute formulas. Source instructions require comparison with the actual PDF page image because overbars may be vector strokes missing from extracted text. Worksheet answer options are candidates to evaluate, not asserted facts. Original operator choice, bar scope, row boundaries and chained-equality order must remain intact. These are prompt requirements, not a mathematical proof or an exact-transcription guarantee.

New answer paragraphs use explicit segments, for example `{"parts":["The coefficient ",{"math":"\\binom{n}{m}"}," counts selections."]}`. The adapter supplies canonical inline delimiters, and saved sets keep the existing text/math block format. Flashcard generation uses exactly one complete plain-English question string and structured answer paragraphs/formulas. A constrained prose pattern guides provider decoding; local parsing stays permissive for older/nonconforming formatting so it cannot trigger an extra provider request. Identical standalone formulas are deduplicated only with matching source/variant metadata; symbols and mathematical equivalence are not normalized.

If a definition or geometric rule is expressed only in words, the compact central reference can be `{"page":4}`. It expands into optional `StudyItem.source`, validated against the same selected primary pages and owner as formula citations. Its source link appears on the answer/back and in PDF answers. The application does not require a fabricated equation to represent a prose definition. Missing both formula blocks and an item source remains invalid.

Provider items have a title, a required central source reference (formula or page-only), and question/answer arrays. The central formula is placed with the answer for both modes unless it is already present (problem question inputs remain in place). Flashcard questions request recall in plain English without giving away the answer; formula objects in older question arrays are relocated to the answer. Formula entries contain `latex`, original `page`, and a nullable `variant` (`original` TeX and plain-English `change`). The adapter restores canonical text/math blocks, display defaults, primary document IDs, null line/quote fields, and consecutive sequence IDs locally. This avoids generating repeated IDs and unused fields. Properly delimited inline math in prose remains typeset when possible, with raw text preserved on a rendering failure. The browser, saved sets, and PDF export retain backward compatibility. Earlier saved plans/goal identifiers remain readable.

### Exact counts and local validation

A completed response schema requires exactly the requested number of items (1–50); an explicit insufficient-source branch permits honest failure. The service rechecks count, source scope, required formula presence, and exact repeated questions. Formatting issues do not reject a complete set. It never silently drops a candidate or fills a missing item. Model-assessed progression and variety are prompt requirements; no separate learning plan or semantic-paraphrase model call is made.

Before validation, deterministic formatting normalization removes uniformly duplicated JSON escape layers and invalid dangling terminal escapes, reuses exact known formula citations when a formula is repeated as prose, and delimits only unambiguous standalone TeX lines. It does not use an LLM or infer new formulas/pages; mixed prose that cannot be interpreted safely remains plain text. Valid aligned/matrix row breaks remain intact.

Generation does not launch Chromium or perform a server-side formula preflight. KaTeX renders mathematical blocks and delimited prose in the learner's browser. Unsupported syntax or missing renderer assets fall back to safely escaped raw TeX, preserving the expression and citation without discarding the set. The same fallback is available in PDF export. Raw TeX in prose, titles or variant descriptions is accepted. No additional model call is made to fix formatting.

Wrong counts, repeated questions, invalid citations, truncation, refusal, or provider failure still produce explicit errors. The original document's access controls remain enforced. A learner can intentionally submit a fresh request after a service/content error.

One generation has a 150-second overall deadline; the provider HTTP attempt has a 120-second timeout and zero SDK retries. Large sets, complex solutions, long source selections, and provider load can still exceed a 20-second target. Successful metadata records `provider_requests: 1`, `generation_attempts: 1`, `generation_strategy: single_request`, duration, prompt hashes, provider/model and `math_check: on_display` and `formatting_policy: best_effort`. Latency improvements follow fewer requests and less generated syntax, as described in [OpenAI latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization). Rendering improvements and schema constraints do not prove literal source transcription or the truth of generated answers; actual tests on Boolean multiple-choice exercises still exposed semantic errors in both the configured model and a stronger comparison model. The application model remains configurable and was not silently changed.

Source transcription and mathematical correctness still require review: syntactically valid TeX does not prove fidelity to the PDF. The renderer retains conservative recovery of unambiguous standalone TeX lines in older saved material and handles delimited math as before.

The shared renderer additionally handles complete bare `aligned`, `array`, matrix and cases environments and bounded bare inline TeX fragments in older prose. English stays outside math; unsupported fragments remain readable raw text. Explicit row breaks outside an environment gain an aligned layout without changing their operands; nested row breaks (such as substack) remain untouched. It never guesses missing right-hand sides, removes or adds overbars, replaces logical operators, or repairs a wrong mathematical answer. Older content with transcription/answer errors must be regenerated or corrected; formatting recovery cannot establish the missing source content.

The workspace starts generation with `POST /api/study/jobs` (202), polls `GET /api/study/jobs/{id}`, and cancels with `DELETE /api/study/jobs/{id}`. All endpoints require the same authenticated owner; unknown and foreign IDs return the same 404. One process-wide generation lock is reserved before a job is returned. Jobs run in process, retain terminal results for 15 minutes (at most 20), and are cancelled on shutdown. A restart loses unsaved jobs explicitly; a subsequent poll displays an interruption message. The synchronous `/api/study/generate` endpoint remains for compatibility and shares the lock.

The panel shows the actual preparing/generating/checking phase, elapsed time, and Cancel, without an obsolete per-item `0 / N ready` counter. Create/poll requests have 15-second deadlines; the browser's overall deadline is 30 seconds beyond the server's generation deadline. API parsing handles non-JSON gateway errors and always clears timers and waiting UI. Normal JSON requests use a 30-second deadline; file uploads allow three minutes. Existing sets and the PDF remain readable. No percentage is invented. The browser warns before leaving active generation; errors preserve existing sets. Application logs contain phases, counts, total duration, rejection codes and schema field locations, without PDF content, prompt bodies, formulas, credentials, or OAuth codes.

## Practice

Top-level tabs retain multiple generated or saved sets. Item tabs select individual problems/cards. Flashcards have front/back faces, a physical flip transition, pointer/Space/Enter controls, and previous/next navigation. The hidden face is inert and excluded from accessibility navigation. Links do not trigger a flip. Problems have a separate solution section.

Flashcard fronts show only the question, with a neutral accessible card label. Titles, answer formulas, explanations, variant originals and source links appear only after flipping. The shared `MathPDF.flashcardSides` projection relocates math blocks from older questions to the answer without changing stored records or browser drafts, deduplicating repeated formulas. PDF export uses the same projection and neutral `Card N` question headings. Prompt instructions ask for self-contained recall questions that do not rely on a hidden formula or include answer hints; no additional model or repair call is made.

Each top-level study-set tab has a separate close button. Closing a saved set removes its tab and keeps it available through Saved sets. Closing a draft offers Save and close, Close without saving, and Cancel. Save and close opens the naming dialog; only a successful save closes the draft, while cancellation or failure keeps it open. The open saved-set IDs and active set are remembered locally, so closing persists after reload. The browser warns before leaving with unsaved study sets or pending uploads.

A draggable vertical separator changes the panes' widths horizontally. Arrow keys adjust the focused separator, and Home/End move to its limits. The divider ratio is remembered locally. PDF pages render lazily near the viewport. Explicit page heights let the reader capture its top page/relative position before a width change, update geometry, and restore that position before painting. Browser scroll anchoring is disabled. The old canvas stays visible during resizing; replacement canvases render offscreen after resizing settles and swap in only when ready. The outer workspace explicitly signals viewport changes and drag completion; the reader measures again over two animation frames, redraws visible pages, and rechecks for missing canvases without waiting for pointer or scroll input. Distant canvases are released after layout stabilizes. Narrow screens stack the document and practice panes. On desktop, **Hide viewer**, dragging the divider fully left or pressing Home collapses the source while retaining its iframe and reading position. **Show viewer** restores the last expanded width. Collapse preference and reading page/zoom are account-scoped.

On phones, scrolling the outer workspace fully into practice collapses the viewer so practice fills the available viewport. A downward pull from the top of noninteractive answer content restores it; ordinary scrolling inside a long answer, horizontal formula scrolling and text selection take priority. The visible **Show viewer** button and source citations also restore the reader. Source-page navigation retains its smooth animation and reduced-motion behavior.

The show/hide controls use panel-and-arrow SVG icons with English accessible labels and tooltips. The expanded viewer's collapse icon is first at the left edge of the file bar; the restore icon is first in the practice bar when collapsed. Controls remain keyboard accessible and provide 44-pixel touch targets on phones.

The PDF reader overlays the vendored PDF.js `TextLayer` on each rendered page, using the matching scale and rotation rules. Text selection survives canvas replacement. Distant text/canvas layers are released except pages participating in an active selection; obsolete text rendering is canceled. Extracted glyph mappings and copying order depend on the PDF's text layer; this does not add OCR.

Citation links navigate to the original page after a `pdf-ready` handshake and settled viewport measurement. Navigation uses a cancellable 300 ms scroll and respects reduced motion; resize anchor restoration stays immediate. Per the revised user preference, individual rows/quotations are not located or highlighted. Text selection and copying remain available.

## PDF export

`POST /api/study/export.pdf` accepts the same canonical set used by Save and returns PDF bytes without requiring a database save. Questions and a separate answer section include all mathematical blocks, original quiz expressions, and citations.

The worker uses the shared local KaTeX HTML renderer and fonts, waits for font loading, checks unsupported expressions and print-width overflow, and prints A4 pages through headless Chromium. Formula text is typeset and embedded in the PDF rather than copied from source screenshots. The original document viewer's canvas is independent.

Install Chromium with:

```sh
uv run playwright install chromium
```

On macOS an installed Google Chrome is detected automatically. Alternatively set `MATHPDF_CHROMIUM_EXECUTABLE` to a Chrome/Chromium executable path. Printing runs in an isolated browser context with intercepted local assets and blocked external requests. Exports are limited to one concurrent request per process and a 90-second deadline.

Correct typesetting does not establish mathematical correctness or exact reproduction of every source PDF's typography. Source references and canonical TeX remain available for comparison.
