# mathPDF

A local mathematics study workspace with document tabs, complete PDF browsing, context attachments, flip cards, saved study sets, and formatted PDF downloads. The interface and documentation are English.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run formula-lab --pdf main.pdf --port 8765
```

Open <http://127.0.0.1:8765>. `--pdf` imports a startup document into the workspace. `--data-dir` changes the persistent workspace location; the default is `.formula-lab/`. The server binds to localhost.

Set `OPENAI_API_KEY` or the existing `OPENAI_KEY` in the server environment or project `.env`. `OPENAI_MODEL` defaults to `gpt-4.1-mini`; it must support the input modalities and structured output used by the application. Restart the server after changing credentials or model. Only submitting **Generate** sends documents to the provider.

## Workflow

1. Read the complete PDF by scrolling, page navigation, or zooming. Click **Add files** to add PDFs, TXT/Markdown, or PNG/JPEG/WebP files. File tabs retain reading positions when switching.
2. Drag the divider horizontally to adjust the document and practice panes. Keyboard users can focus the divider and use Left/Right or Home/End.
3. Open **Generate study set**. Choose a source PDF, flashcards or problems, and an item count. Choose **Entire PDF** or inclusive **From / To** pages. Set both endpoints to the same page for a single page.
4. Enable any additional context files. Each PDF has an independent page range; text and images are included in full. Context examples guide the task style and difficulty; formulas remain grounded in the selected source pages.
5. Each generation opens a separate set tab. Inner tabs select cards or problems. Click a card, press Space/Enter, or use **Flip card** to turn it over. Problems have a solution section. Formula references navigate to the original document page.
6. Click **Save** to name and persist a set in SQLite. Saved sets reopen after reload and are also available through **Saved sets**.
7. Click **Download PDF** to export the current set, whether or not it is saved. The PDF includes questions and a separate answer section with formatted mathematical text.

## Supported files and limits

- PDF, UTF-8 TXT/MD, PNG, JPEG, WebP; 25 MB per upload, 1 MB for text, 40 megapixels for images.
- Up to six optional context files, 100 selected PDF pages across all attachments, and 40 MB of combined selected input per generation.
- One to ten items per set; one concurrent generation and one concurrent PDF export per process.
- PDFs must be readable and unencrypted. Version one targets printed digital notes; handwriting/OCR is outside the current scope.

## Storage

`.formula-lab/workspace.sqlite3` stores document metadata and explicitly saved sets. `.formula-lab/documents/` stores managed original files. Save preserves question/answer blocks, TeX, source references, context selections, quiz originals, and provider/prompt metadata. Unsaved sets remain browser drafts and are lost on reload. The original startup PDF and old diagnostic records are preserved.

The current workspace is local and has no account system. Google identity and private Garage storage remain part of the broader application plan.

## PDF export setup

Export uses Chromium and the same local KaTeX renderer/fonts as the workspace. Fractions, indices, operators, and aligned expressions remain typeset text; study formulas are not screenshots. The original PDF reader uses PDF.js independently.

```sh
uv run playwright install chromium
```

An installed Google Chrome is detected on macOS. To use another installation, set `MATHPDF_CHROMIUM_EXECUTABLE` to its executable path. Export waits for rendering and fonts and reports unsupported/oversized formulas rather than silently dropping them.

## Architecture

```text
Document tabs + continuous PDF viewer
    -> Generation dialog: source range + optional context ranges
    -> Generation service -> external prompts -> StudyProvider -> OpenAI
    -> typed text/math blocks -> tabbed flip cards or problems
    -> explicit SQLite save / Chromium PDF export
```

- `formula_lab/workspace.py`: document/file adapter and SQLite repository.
- `formula_lab/study.py`: canonical study schema, selected-page preparation, prompts/hashes, source-scope validation.
- `formula_lab/providers.py`: OpenAI adapter for PDF/text/image attachments.
- `formula_lab/prompts/`: all LLM instruction text and templates.
- `formula_lab/static/math-renderer.js`: reusable TeX to HTML/MathML rendering.
- `formula_lab/static/pdf-viewer.js`: continuous lazy document preview.
- `formula_lab/pdf_export.py` and `static/print.*`: isolated print document and PDF worker.
- `formula_lab/app.py`: local FastAPI routes.

[Workspace behavior and API](docs/workspace.md) describes the request contract, persistence, controls, and export. [The earlier fidelity report](docs/fidelity-report.md) concerns the separate source-font diagnostic experiment. Legacy source-font extraction, explicit-save, review, variant, and export APIs remain available, but the normal UI has no formula catalog.

## Local frontend assets

Runtime assets require no CDN. To refresh vendored KaTeX/PDF.js after dependency changes:

```sh
npm ci --ignore-scripts
npm run vendor:math
```

Node is not required to run the Python application with these assets present. Keep lockfiles and bundled licenses.

## Fidelity and verification scope

Correct typesetting does not prove that an LLM transcribed the PDF correctly or that generic math fonts match its original typography. Generated sets retain unchecked source metadata and references for comparison. The current work does not claim universal PDF fidelity.

Existing automated tests and historical browser scripts cover the earlier source-font prototype; they were not run for this UX revision. The superseded `scripts/browser_check.cjs` does not cover the new workspace. Current manual UI observations and any model/export execution are recorded separately from automated test coverage.
