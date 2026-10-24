# Study workspace

## Documents and storage

Google sign-in is mandatory. `/` is the personal library; selecting an owned file opens `/workspace?document=<id>`, and selecting a saved set opens `/workspace?set=<id>` with its source PDF. The library starts empty and offers Upload files. It accepts PDF, UTF-8 TXT/Markdown, PNG, JPEG, and WebP uploads. Generation is enabled after a PDF is available. Each file is limited to 25 MB; text files to 1 MB; images to 40 megapixels. PDF uploads must be readable and unencrypted. Original filenames are display metadata; managed binaries use content hashes and opaque document IDs.

`Workspace` is the local storage adapter. SQLite users, sessions, document metadata, and saved sets live at `<data-dir>/workspace.sqlite3`; binaries live at `<data-dir>/documents/<owner-id>/`. The default data directory is `.formula-lab/`. Every repository read/write requires the authenticated owner; duplicate hashes are unique per account. Foreign IDs return generic not-found responses, including when used as generation context or export sources. A saved-set upsert cannot overwrite another owner's identifier. The user-authorized ownership migration deletes old unowned managed uploads and saved sets once. Owned data survives subsequent restarts. Garage integration remains future work.

Startup and the Docker image require no PDF. Shared legacy source-inspection HTTP routes and the `--pdf` option have been removed from the web application. `GET /api/generation/config` returns `default_document_id: null`; generation requires an owned primary document ID. See [authentication setup](authentication.md) for Google credentials, session behavior, and local configuration.

- `GET /api/me`: the current account's ID, name, and email.
- `GET /api/documents`: list the current account's document metadata.
- `POST /api/documents`: upload one multipart `file`.
- `GET /api/documents/{id}/file`: preview a managed file; `?download=true` returns an attachment.
- `GET /api/study-sets`: list the current account's explicitly saved sets.
- `GET /api/study-sets/{id}`: load the canonical saved set.
- `POST /api/study-sets`: save or update a validated set with its source/context snapshots, editable math, quiz originals, and generation metadata.

All these APIs require a live session; unsafe methods also require the trusted application Origin. Generation drafts are not saved automatically. Saved sets survive restart. Document tabs retain their preview instances and reading positions while the workspace is open. Browser preferences are scoped by account ID.

File-tab close controls remove previews, not stored documents. **Open** lists saved files, including closed ones. The open saved-file tab list persists in browser local storage. New files appear immediately as unsaved upload tabs; confirmation is required to close and cancel an unfinished or failed upload. Failed uploads retain the local file for **Retry upload** while the page is open. Leaving the browser page with pending uploads triggers the browser's unsaved-change warning. A request already committed by the server can remain in the library after cancellation.

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

`pages: null` selects an entire PDF. The service allows up to six context files, 100 PDF pages across all selected files, 40 MB of combined selected bytes, and 1–10 generated items. It validates all selections before the provider request. Page subsets are copied into in-memory PDFs; no formula catalog or full-text extraction is required.

`comment` is optional, defaults to an empty string, and is limited to 4,000 characters. It is independent of context attachments. `prompts/comment.md` supplies its instruction text; the runtime comment is inserted as a JSON string and cannot relax source, citation, or schema requirements. The generated and saved canonical set retains the trimmed `comment`. Existing saved sets remain readable with the empty default.

`StudyProvider.generate(documents, system, task)` receives provider-independent input documents. The OpenAI adapter sends PDF/text files as file inputs and images as image inputs. External prompt resources distinguish the primary source from context examples and supply per-file original-page mappings. Formula citations include the primary document ID and original page; citation scope is validated. Optional line ranges remain model-reported.

## Practice

Top-level tabs retain multiple generated or saved sets. Item tabs select individual problems/cards. Flashcards have front/back faces, a physical flip transition, pointer/Space/Enter controls, and previous/next navigation. The hidden face is inert and excluded from accessibility navigation. Links do not trigger a flip. Problems have a separate solution section.

Each top-level study-set tab has a separate close button. Closing a saved set removes its tab and keeps it available through Saved sets. Closing a draft offers Save and close, Close without saving, and Cancel. Save and close opens the naming dialog; only a successful save closes the draft, while cancellation or failure keeps it open. The open saved-set IDs and active set are remembered locally, so closing persists after reload. The browser warns before leaving with unsaved study sets or pending uploads.

A draggable vertical separator changes the panes' widths horizontally. Arrow keys adjust the focused separator, and Home/End move to its limits. The divider ratio is remembered locally. PDF pages render lazily near the viewport. Explicit page heights let the reader capture its top page/relative position before a width change, update geometry, and restore that position before painting. Browser scroll anchoring is disabled. The old canvas stays visible during resizing; replacement canvases render offscreen after resizing settles and swap in only when ready. The outer workspace explicitly signals viewport changes and drag completion; the reader measures again over two animation frames, redraws visible pages, and rechecks for missing canvases without waiting for pointer or scroll input. Distant canvases are released after layout stabilizes. Narrow screens stack the document and practice panes.

## PDF export

`POST /api/study/export.pdf` accepts the same canonical set used by Save and returns PDF bytes without requiring a database save. Questions and a separate answer section include all mathematical blocks, original quiz expressions, and citations.

The worker uses the shared local KaTeX HTML renderer and fonts, waits for font loading, checks unsupported expressions and print-width overflow, and prints A4 pages through headless Chromium. Formula text is typeset and embedded in the PDF rather than copied from source screenshots. The original document viewer's canvas is independent.

Install Chromium with:

```sh
uv run playwright install chromium
```

On macOS an installed Google Chrome is detected automatically. Alternatively set `MATHPDF_CHROMIUM_EXECUTABLE` to a Chrome/Chromium executable path. Printing runs in an isolated browser context with intercepted local assets and blocked external requests. Exports are limited to one concurrent request per process and a 90-second deadline.

Correct typesetting does not establish mathematical correctness or exact reproduction of every source PDF's typography. Source references and canonical TeX remain available for comparison.
