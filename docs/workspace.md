# Study workspace

## Documents and storage

The workspace imports the startup PDF and accepts PDF, UTF-8 TXT/Markdown, PNG, JPEG, and WebP uploads. Each file is limited to 25 MB; text files to 1 MB; images to 40 megapixels. PDF uploads must be readable and unencrypted. Original filenames are display metadata; managed binaries use content hashes and opaque document IDs.

`Workspace` is the local storage adapter. SQLite metadata and saved sets live at `<data-dir>/workspace.sqlite3`; binaries live at `<data-dir>/documents/`. The default data directory is `.formula-lab/`. The original startup file and old diagnostic records are preserved. The application remains local and has no Google identity or Garage integration yet.

- `GET /api/documents`: list document metadata.
- `POST /api/documents`: upload one multipart `file`.
- `GET /api/documents/{id}/file`: preview a managed file; `?download=true` returns an attachment.
- `GET /api/study-sets`: list explicitly saved sets.
- `GET /api/study-sets/{id}`: load the canonical saved set.
- `POST /api/study-sets`: save or update a validated set with its source/context snapshots, editable math, quiz originals, and generation metadata.

Generation drafts are not saved automatically. Saved sets survive restart. Document tabs retain their preview instances and reading positions while the workspace is open.

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
  "mode": "flashcards",
  "count": 4
}
```

`pages: null` selects an entire PDF. The service allows up to six context files, 100 PDF pages across all selected files, 40 MB of combined selected bytes, and 1–10 generated items. It validates all selections before the provider request. Page subsets are copied into in-memory PDFs; no formula catalog or full-text extraction is required.

`StudyProvider.generate(documents, system, task)` receives provider-independent input documents. The OpenAI adapter sends PDF/text files as file inputs and images as image inputs. External prompt resources distinguish the primary source from context examples and supply per-file original-page mappings. Formula citations include the primary document ID and original page; citation scope is validated. Optional line ranges remain model-reported.

## Practice

Top-level tabs retain multiple generated or saved sets. Item tabs select individual problems/cards. Flashcards have front/back faces, a physical flip transition, pointer/Space/Enter controls, and previous/next navigation. The hidden face is inert and excluded from accessibility navigation. Links do not trigger a flip. Problems have a separate solution section.

A draggable vertical separator changes the panes' widths horizontally. Arrow keys adjust the focused separator, and Home/End move to its limits. The divider ratio is remembered locally. PDF pages render lazily near the viewport, release distant canvases, and re-render on width changes. Narrow screens stack the document and practice panes.

## PDF export

`POST /api/study/export.pdf` accepts the same canonical set used by Save and returns PDF bytes without requiring a database save. Questions and a separate answer section include all mathematical blocks, original quiz expressions, and citations.

The worker uses the shared local KaTeX HTML renderer and fonts, waits for font loading, checks unsupported expressions and print-width overflow, and prints A4 pages through headless Chromium. Formula text is typeset and embedded in the PDF rather than copied from source screenshots. The original document viewer's canvas is independent.

Install Chromium with:

```sh
uv run playwright install chromium
```

On macOS an installed Google Chrome is detected automatically. Alternatively set `MATHPDF_CHROMIUM_EXECUTABLE` to a Chrome/Chromium executable path. Printing runs in an isolated browser context with intercepted local assets and blocked external requests. Exports are limited to one concurrent request per process and a 90-second deadline.

Correct typesetting does not establish mathematical correctness or exact reproduction of every source PDF's typography. Source references and canonical TeX remain available for comparison.
