# mathPDF

A personal mathematics study platform with Google sign-in, an account library, complete PDF browsing, context attachments, flip cards, saved study sets, and formatted PDF downloads. The interface and documentation are English.

## Run

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
APP_BASE_URL=http://127.0.0.1:8765 uv run formula-lab --port 8765
```

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the environment or ignored project `.env`; `.env.example` contains placeholders. Register `http://127.0.0.1:8765/auth/google/callback` for a development Google web client. See [Google setup and authentication](docs/authentication.md).

Open [http://127.0.0.1:8765](http://127.0.0.1:8765) and sign in with Google. Home shows your own files with first-page previews and saved study sets. A fresh account starts empty with **Upload PDF**. Selecting a file or set opens the existing reading workspace. `--data-dir` changes the persistent location; the default is `.formula-lab/`. The server binds to localhost. No startup PDF or anonymous development bypass is provided.

Set `OPENAI_API_KEY` or the existing `OPENAI_KEY` in the server environment or project `.env`. `OPENAI_MODEL` defaults to `gpt-4.1-mini`; it must support the input modalities and structured output used by the application. Restart the server after changing credentials or model. Only submitting **Generate** sends documents to the provider.

## Workflow

1. Sign in with Google. Home lists your files and saved sets; use **Upload files** to add PDFs, TXT/Markdown, or PNG/JPEG/WebP files. Choose a file to read the complete document by scrolling, page navigation, or zooming. **Add files** adds context from the workspace. Tabs retain reading positions; close them with **×** and reopen files through **Open**. Closing unfinished or failed uploads asks for confirmation; failed uploads can be retried. Click **mathPDF** to return home. The top-right account menu provides **Sign out**.
2. Drag the divider horizontally to adjust the document and practice panes. **Hide viewer**, dragging fully left, or the divider's Home key hides the PDF; **Show viewer** restores it. Fit width retains the reading position and previous canvas during resizing. On phones, scrolling fully into practice hides the viewer; pull down from the top of the answer or use **Show viewer** to restore it. Home's **Files** and **Saved study sets** sections collapse independently.
3. Open **Generate**. Choose a source PDF, flashcards or problems, and 1–50 items. The whole set is generated in one model request, with varied questions ordered from easier to harder. External LaTeX guides provide reusable inline, equation, row and table structures while requiring the PDF's original notation. The adapter supplies delimiters for explicit inline math; the UI also recovers unambiguous older TeX fragments and displays unsupported syntax as raw text. Formatting does not block the whole set. Prose-only definitions can retain a source-page citation without an invented equation. Successful generation returns exactly the requested count; incomplete or invalid source responses fail explicitly without automatic model retries. The waiting panel shows the actual phase, elapsed time, and **Cancel**. Insufficient source material produces an actionable error instead of a partial set. Choose **Entire PDF** or inclusive **From / To** pages. Set both endpoints to the same page for a single page.
4. Enable any additional context files. Each PDF has an independent page range; text and images are included in full. Optionally enter a plain-text **Comment** (up to 4,000 characters), with or without attachments, to describe the desired style, difficulty, or focus. Formulas remain grounded in the selected source pages.
5. Each generation opens a separate set tab. Inner tabs select cards or problems. Flashcard fronts show only the recall question; the title, formula, answer and source link appear on the back. This also applies to older cards. Click a card, press Space/Enter, or use **Flip card** to turn it over. Problems have a solution section. Select and copy text in digital PDF pages. Formula references briefly animate to the original source page.
6. Click **Save** to name and persist a set in SQLite. Close a set tab with **×**. Unsaved sets offer **Save and close**, **Close without saving**, or **Cancel**; saving must succeed before the tab closes. Saved sets remain available through **Saved sets**, and closed tabs stay closed after reload.
7. Click **Download PDF** to export the current set, whether or not it is saved. The PDF includes questions and a separate answer section with formatted mathematical text.

8. Use **Delete** on home to permanently remove a file or saved set after confirmation. **Deleting a main source also deletes its saved study sets.** Sets using that file only as additional context remain, with that attachment removed. Deleting a set keeps its source files.

## Supported files and limits

- PDF, UTF-8 TXT/MD, PNG, JPEG, WebP; 25 MB per upload, 1 MB for text, 40 megapixels for images.
- Up to six optional context files, 100 selected PDF pages across all attachments, and 40 MB of combined selected input per generation.
- One to fifty requested items per set, with exactly that count on successful generation; one concurrent generation and one concurrent PDF export per process.
- PDFs must be readable and unencrypted. Version one targets printed digital notes; handwriting/OCR is outside the current scope.

## Storage

`.formula-lab/workspace.sqlite3` stores document metadata and explicitly saved sets. `.formula-lab/documents/` stores managed original files. Save preserves question/answer blocks, TeX, source references, context selections, the generation comment, quiz originals, and provider/prompt metadata. Unsaved sets remain browser drafts; leaving the page warns about pending uploads or unsaved sets. Closing a saved file or study-set tab retains its stored record. Open saved-file and study-set tab lists are remembered locally.

New releases must read every previously supported persisted format. Study sets without a version marker are version 1; newer writes include `schema_version: 1`. Reading an older set does not rewrite it. Compatibility may be broken only for a major change with the project owner's explicit approval; older releases need not read newer payloads. See the [compatibility contract](docs/study-contract.md#backward-compatibility) and frozen fixtures under `tests/fixtures/study-sets/`.

Every file and saved set belongs to its authenticated owner. All reads, downloads, generation attachments, updates, and exports enforce ownership on the backend. Identical files uploaded by different accounts receive separate records. Browser preferences are scoped by account ID.

Derived previews are cached in account-scoped IndexedDB: up to 150 home previews and the ten most recently viewed PDF page images, each group capped at 30 MB. Cached pages appear while the authorized PDF and selectable text load; this is not offline file access. Deletion and sign-out clear the relevant cache. If browser storage is unavailable, previews render normally. See [cache behavior](docs/workspace.md#browser-visual-cache).

On the first ownership upgrade, the application deletes pre-authentication managed uploads and saved sets, as explicitly requested by the project owner. Later restarts preserve owned data. Repository PDFs outside the managed upload directory are untouched. Storage remains local; Garage integration is future work.

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

- `formula_lab/auth.py`: Google identity, one-use OAuth transactions, and revocable server-side sessions.
- `formula_lab/workspace.py`: owner-scoped document/file adapter and SQLite repository.
- `formula_lab/study.py`: canonical study schema, selected-page preparation, prompts/hashes, source-scope validation.
- `formula_lab/providers.py`: OpenAI adapter for PDF/text/image attachments.
- `formula_lab/prompts/`: all LLM instruction text and templates.
- `formula_lab/static/math-renderer.js`: reusable TeX to HTML/MathML rendering.
- `formula_lab/static/pdf-viewer.js`: continuous lazy document preview.
- `formula_lab/static/workspace-layout.js`: pane resizing, collapse and mobile focus gestures.
- `formula_lab/static/visual-cache.js`: bounded account-scoped derived previews and page images.
- `formula_lab/pdf_export.py` and `static/print.*`: isolated print document and PDF worker.
- `formula_lab/app.py`: authenticated FastAPI routes, origin checks, and private response handling.

[Workspace behavior and API](docs/workspace.md) describes the request contract, persistence, controls, and export. [The earlier fidelity report](docs/fidelity-report.md) concerns the separate source-font diagnostic experiment. Its Python modules remain as offline tooling; shared legacy diagnostic HTTP endpoints are no longer exposed by the web application.

[Diagnostics](docs/diagnostics.md) explains request references, browser failure reports, asset versions, and `docker compose logs` commands for the VPS.

## VPS deployment

The single GitHub Actions job in `.github/workflows/deploy.yml` deploys pushes to `main` and also supports manual runs. It syncs the repository to `/opt/mathPDF`, writes `.env` directly on the VPS from `APP_ENV`, and runs `docker compose up -d --build`. All deployment commands are inline in the workflow.

Add these **repository secrets** under **Settings → Secrets and variables → Actions → Secrets**:

| Secret | Value |
| --- | --- |
| `VPS_HOST` | VPS hostname or IP, using SSH port 22 |
| `VPS_USER` | SSH user with write access to `/opt/mathPDF` and permission to run Docker |
| `VPS_SSH_KEY` | Complete private SSH key authorized on the VPS |
| `APP_ENV` | Complete multiline `.env` contents, including Google client credentials and the OpenAI API key |

Example `APP_ENV` (replace the placeholders):

```dotenv
OPENAI_KEY=your-api-key
OPENAI_MODEL=gpt-4.1-mini
GOOGLE_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
```

The VPS needs Docker with the Compose plugin, `rsync`, and the existing Traefik attached to `traefik-public`, with entrypoint `websecure` and certificate resolver `myresolver`. The domain `mathpdf.site` is fixed in `docker-compose.yaml`; point its DNS records at the VPS. Compose joins the [existing external network](https://docs.docker.com/reference/compose-file/networks/#external) and configures [Traefik's Docker labels](https://doc.traefik.io/traefik/routing/providers/docker/) to route HTTPS to container port 8765.

SQLite, uploaded files, and saved sets persist in `/opt/mathPDF/.formula-lab`. Deployment excludes that directory and `.env` from file synchronization; `.env` is replaced separately from the secret with permissions `600`. The image includes Chromium for PDF export and installs dependencies from `uv.lock`. Google sign-in is mandatory; the production callback is fixed by the default origin to `https://mathpdf.site/auth/google/callback`. Omit the local `APP_BASE_URL` override on the VPS. Missing Google credentials leave private content protected and sign-in unavailable.

## Local frontend assets

Runtime assets require no CDN. To refresh vendored KaTeX/PDF.js after dependency changes:

```sh
npm ci --ignore-scripts
npm run vendor:math
```

Node is not required to run the Python application with these assets present. Keep lockfiles and bundled licenses.

## Fidelity and verification scope

Correct typesetting does not prove that an LLM transcribed the PDF correctly or that generic math fonts match its original typography. Generated sets retain unchecked source metadata and references for comparison. The current work does not claim universal PDF fidelity.

The regression suite covers generation, provider adaptation, shared mathematical rendering, owner-scoped persistence, historical payload compatibility and PDF export. Run it with `uv run --frozen --extra dev pytest -q`. Real-provider latency and manual browser observations are recorded separately in the OpenSpec change verification notes. The superseded `scripts/browser_check.cjs` does not cover the current workspace.
