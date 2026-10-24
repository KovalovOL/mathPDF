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

1. Read the complete PDF by scrolling, page navigation, or zooming. Click **Add files** to add PDFs, TXT/Markdown, or PNG/JPEG/WebP files. File tabs retain reading positions when switching. Close tabs with **×** and reopen saved files through **Open**. Closing unfinished or failed uploads asks for confirmation; failed uploads can be retried.
2. Drag the divider horizontally to adjust the document and practice panes. Fit width retains the top reading position and keeps the previous canvas visible while a sharper replacement renders. Keyboard users can focus the divider and use Left/Right or Home/End.
3. Open **Generate study set**. Choose a source PDF, flashcards or problems, and an item count. Choose **Entire PDF** or inclusive **From / To** pages. Set both endpoints to the same page for a single page.
4. Enable any additional context files. Each PDF has an independent page range; text and images are included in full. Optionally enter a plain-text **Comment** (up to 4,000 characters), with or without attachments, to describe the desired style, difficulty, or focus. Formulas remain grounded in the selected source pages.
5. Each generation opens a separate set tab. Inner tabs select cards or problems. Click a card, press Space/Enter, or use **Flip card** to turn it over. Problems have a solution section. Formula references navigate to the original document page.
6. Click **Save** to name and persist a set in SQLite. Saved sets reopen after reload and are also available through **Saved sets**.
7. Click **Download PDF** to export the current set, whether or not it is saved. The PDF includes questions and a separate answer section with formatted mathematical text.

## Supported files and limits

- PDF, UTF-8 TXT/MD, PNG, JPEG, WebP; 25 MB per upload, 1 MB for text, 40 megapixels for images.
- Up to six optional context files, 100 selected PDF pages across all attachments, and 40 MB of combined selected input per generation.
- One to ten items per set; one concurrent generation and one concurrent PDF export per process.
- PDFs must be readable and unencrypted. Version one targets printed digital notes; handwriting/OCR is outside the current scope.

## Storage

`.formula-lab/workspace.sqlite3` stores document metadata and explicitly saved sets. `.formula-lab/documents/` stores managed original files. Save preserves question/answer blocks, TeX, source references, context selections, the generation comment, quiz originals, and provider/prompt metadata. Unsaved sets remain browser drafts and are lost on reload. Closing a saved file tab does not delete it. The open saved-file tab list is remembered locally. The original startup PDF and old diagnostic records are preserved.

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

## VPS deployment

The single GitHub Actions job in `.github/workflows/deploy.yml` deploys pushes to `main` and also supports manual runs. It syncs the repository to `/opt/mathPDF`, writes `.env` directly on the VPS from `APP_ENV`, and runs `docker compose up -d --build`. All deployment commands are inline in the workflow.

Add these **repository secrets** under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS hostname or IP, using SSH port 22 |
| `VPS_USER` | SSH user with write access to `/opt/mathPDF` and permission to run Docker |
| `VPS_SSH_KEY` | Complete private SSH key authorized on the VPS |
| `APP_ENV` | Complete multiline `.env` contents, including the OpenAI API key |

Example `APP_ENV` (replace the key):

```dotenv
OPENAI_KEY=your-api-key
OPENAI_MODEL=gpt-4.1-mini
```

The VPS needs Docker with the Compose plugin, `rsync`, and the existing Traefik attached to `traefik-public`, with entrypoint `websecure` and certificate resolver `myresolver`. The domain `mathpdf.site` is fixed in `docker-compose.yaml`; point its DNS records at the VPS. Compose joins the [existing external network](https://docs.docker.com/reference/compose-file/networks/#external) and configures [Traefik's Docker labels](https://doc.traefik.io/traefik/routing/providers/docker/) to route HTTPS to container port 8765.

SQLite, uploaded files, and saved sets persist in `/opt/mathPDF/.formula-lab`. Deployment excludes that directory and `.env` from file synchronization; `.env` is replaced separately from the secret with permissions `600`. The image includes Chromium for PDF export, installs Python dependencies from `uv.lock`, and serves the existing frontend assets. The current workspace has no user authentication; it is accessible at the configured domain.

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
