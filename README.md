# Acadence

An AI-assisted learning environment for students, with Google sign-in, an account library, PDF browsing and notes, context attachments, flip cards, saved study sets, and formatted PDF downloads. The interface and documentation are English.

## Run the two applications

Requires Python 3.12+, Node.js 24+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --python 3.12 --project back --extra dev
npm ci --prefix front
npm --prefix front run build
```

Run these processes from the repository root, in separate terminals:

```sh
APP_BASE_URL=http://127.0.0.1:8770 uv run --python 3.12 --project back formula-lab --port 8765
APP_BASE_URL=http://127.0.0.1:8770 uv run --python 3.12 --project back uvicorn app.bootstrap.platform:admin_app --factory --port 8767
APP_BASE_URL=http://127.0.0.1:8770 uv run --python 3.12 --project back uvicorn app.bootstrap.platform:reports_app --factory --port 8768
npm --prefix front start
```

Open [http://127.0.0.1:8770](http://127.0.0.1:8770). Only the frontend gateway is public. Its private asset server uses port 8771; API, admin and report processes have separate ports. Set the same `APP_BASE_URL`, data directory and storage configuration for backend services. `MATHPDF_FRONTEND_URL` defaults to `http://127.0.0.1:8771` for local PDF exports.

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in the environment or ignored root `.env`; `.env.example` contains placeholders. Register `http://127.0.0.1:8770/auth/google/callback` for development. See [authentication](docs/authentication.md). A fresh account starts empty; no anonymous development login is provided. `--data-dir` changes the default `.formula-lab/` location.

Set `OPENAI_API_KEY` or the existing `OPENAI_KEY` in the server environment or project `.env`. `OPENAI_MODEL` defaults to `gpt-4.1-mini`; it must support the input modalities and structured output used by the application. Restart the server after changing credentials or model. Only submitting **Generate** sends documents to the provider.

## First-login welcome

New accounts see a compact, dismissible welcome dialog once on the library or workspace. Its display is recorded per account on the server, including across browsers and devices. Existing accounts are not interrupted. Start learning, the close button, Escape, or clicking outside dismisses it. This adds only an account display receipt; existing files, study sets and sessions are unchanged.

## Workflow

1. Sign in with Google. Home lists your files and saved sets; use **Upload files** to add PDFs, TXT/Markdown, or PNG/JPEG/WebP files. Choose a file to read the complete document by scrolling, page navigation, or zooming. **Add files** adds context from the workspace. Tabs retain reading positions; close them with **×** and reopen files through **Open**. Closing unfinished or failed uploads asks for confirmation; failed uploads can be retried. Click **Acadence** to return home. The top-right account menu provides **Sign out**.
2. Drag the divider horizontally to adjust the document and practice panes. The **Hide viewer** icon at the left of the file bar, dragging fully left, or the divider's Home key hides the PDF; the **Show viewer** icon restores it. Fit width retains the reading position and previous canvas during resizing. On phones, scrolling fully into practice hides the viewer; pull down from the top of the answer or use **Show viewer** to restore it. Home's **Files** and **Saved study sets** sections collapse independently.
3. Open **Generate**. Choose a source PDF, flashcards or problems, and 1–50 items. The whole set is generated in one model request, with varied questions ordered from easier to harder. External LaTeX guides provide reusable inline, equation, row and table structures while requiring the PDF's original notation. The adapter supplies delimiters for explicit inline math; the UI also recovers unambiguous older TeX fragments and displays unsupported syntax as raw text. Formatting does not block the whole set. Prose-only definitions can retain a source-page citation without an invented equation. Successful generation returns exactly the requested count; incomplete or invalid source responses fail explicitly without automatic model retries. The waiting panel shows the actual phase, elapsed time, and **Cancel**. Insufficient source material produces an actionable error instead of a partial set. Choose **Entire PDF** or inclusive **From / To** pages. Set both endpoints to the same page for a single page.
4. Enable any additional context files. Each PDF has an independent page range; text and images are included in full. Optionally enter a plain-text **Comment** (up to 4,000 characters), with or without attachments, to describe the desired style, difficulty, or focus. Formulas remain grounded in the selected source pages.
5. Each generation opens a separate set tab. Inner tabs select cards or problems. Flashcard fronts show only the recall question; the title, formula, answer and source link appear on the back. This also applies to older cards. Click a card, press Space/Enter, or use **Flip card** to turn it over. Problems have a solution section. Select and copy text in digital PDF pages. Formula references briefly animate to the original source page.
6. Click **Save** to name and persist a set in SQLite. Close a set tab with **×**. Unsaved sets offer **Save and close**, **Close without saving**, or **Cancel**; saving must succeed before the tab closes. Saved sets remain available through **Saved sets**, and closed tabs stay closed after reload.
7. Click **Download PDF** to export the current set, whether or not it is saved. The PDF includes questions and a separate answer section with formatted mathematical text.

8. Use the pencil icon beside Download to highlight selected text or draw on a PDF. The collapsible toolbar includes colors, pen widths, a whole-stroke/highlight eraser, Undo/Redo and Save. Ctrl/Cmd+Z undoes and Ctrl/Cmd+S saves. One edited copy is created per original; later saves update it. Before generation with unsaved notes, choose the original, save and use the copy, or Cancel. See [PDF annotations](docs/annotations.md).
9. Use **Delete** on home to permanently remove a file or saved set after confirmation. **Deleting an original also deletes its edited copy and saved sets with either as their main source.** Sets using those files only as additional context remain, with those attachments removed. Deleting a copy retains the original; deleting a set keeps its source files.

## Supported files and limits

- PDF, UTF-8 TXT/MD, PNG, JPEG, WebP; 25 MB per upload, 1 MB for text, 40 megapixels for images.
- Up to six optional context files, 100 selected PDF pages across all attachments, and 40 MB of combined selected input per generation.
- One to fifty requested items per set, with exactly that count on successful generation; one concurrent generation with a FIFO waiting queue (up to 20 unfinished jobs, one per account) and one concurrent PDF export per process. Waiting jobs start automatically and can be cancelled. The queue is process-local and does not survive server restarts. Older open tabs keep their previous 180-second client deadline; reload to use extended queue waiting.
- PDFs must be readable and unencrypted. Version one targets printed digital notes; handwriting/OCR is outside the current scope.

## Storage

`.formula-lab/workspace.sqlite3` stores document metadata and explicitly saved sets. `.formula-lab/documents/` stores managed original files. Save preserves question/answer blocks, TeX, source references, context selections, the generation comment, quiz originals, and provider/prompt metadata. Unsaved sets remain browser drafts; leaving the page warns about pending uploads or unsaved sets. Closing a saved file or study-set tab retains its stored record. Open saved-file and study-set tab lists are remembered locally.

New releases must read every previously supported persisted format. Study sets without a version marker are version 1; newer writes include `schema_version: 1`. Reading an older set does not rewrite it. Compatibility may be broken only for a major change with the project owner's explicit approval; older releases need not read newer payloads. See the [compatibility contract](docs/study-contract.md#backward-compatibility) and frozen fixtures under `tests/fixtures/study-sets/`.

Every file and saved set belongs to its authenticated owner. All reads, downloads, generation attachments, updates, and exports enforce ownership on the backend. Identical files uploaded by different accounts receive separate records. Browser preferences are scoped by account ID.

Derived previews are cached in account-scoped IndexedDB: up to 150 home previews and the ten most recently viewed PDF page images, each group capped at 30 MB. Cached pages appear while the authorized PDF and selectable text load; this is not offline file access. Deletion and sign-out clear the relevant cache. If browser storage is unavailable, previews render normally. See [cache behavior](docs/workspace.md#browser-visual-cache).

On the first ownership upgrade, the application deletes pre-authentication managed uploads and saved sets, as explicitly requested by the project owner. Later restarts preserve owned data. Repository PDFs outside the managed upload directory are untouched. Local development retains SQLite; production uses PostgreSQL and private Garage storage with a verified, non-destructive migration. See [platform services](docs/platform.md).

## PDF export setup

Export uses Chromium and the same local KaTeX renderer/fonts as the workspace. Fractions, indices, operators, and aligned expressions remain typeset text; study formulas are not screenshots. The original PDF reader uses PDF.js independently.

```sh
uv run --python 3.12 --project back playwright install chromium
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

See [the architecture and dependency rules](docs/architecture.md) for domain ownership, public ports, transaction boundaries and lifecycle invariants. Runtime code lives in `back/app/` and `front/app/`; each application has independent manifests, lockfiles, Dockerfile and tests. [Source ownership](contracts/source-ownership.json) records the complete move from the former flat package.

[Workspace behavior and API](docs/workspace.md) describes the request contract, persistence, controls, and export. [The earlier fidelity report](docs/fidelity-report.md) concerns the separate source-font diagnostic experiment. Its Python modules remain as offline tooling; shared legacy diagnostic HTTP endpoints are no longer exposed by the web application.

[Diagnostics](docs/diagnostics.md) explains request references, browser failure reports, asset versions, and `docker compose logs` commands for the VPS.

## VPS deployment

The single GitHub Actions job in `.github/workflows/deploy.yml` deploys pushes to `main` and also supports manual runs. It syncs the repository to `/opt/mathPDF`, writes `.env` directly on the VPS from `APP_ENV`, builds both application images before stopping writers for verified migration, and starts the coordinated frontend/backend services with health checks. All deployment commands are inline in the workflow.

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

The VPS needs Docker with the Compose plugin, `rsync`, and the existing Traefik attached to `traefik-public`, with entrypoint `websecure` and certificate resolver `myresolver`. The domain `mathpdf.site` is fixed in `docker-compose.yaml`; point its DNS records at the VPS. Compose joins the [existing external network](https://docs.docker.com/reference/compose-file/networks/#external) and configures [Traefik's Docker labels](https://doc.traefik.io/traefik/routing/providers/docker/) to route HTTPS to frontend gateway port 8080.

Production PostgreSQL/Garage data and persistent credentials live in `/opt/mathPDF/.infrastructure`; verified migration backups, retained original files and caches live in `.formula-lab`. Deployment excludes both directories and `.env` from file synchronization; `.env` is replaced separately from the secret with permissions `600`. The image includes Chromium for PDF export and installs dependencies from `uv.lock`. Google sign-in is mandatory; the production callback is fixed by the default origin to `https://mathpdf.site/auth/google/callback`. Omit the local `APP_BASE_URL` override on the VPS. Missing Google credentials leave private content protected and sign-in unavailable.

## Local frontend assets

Runtime assets require no CDN. To refresh vendored KaTeX/PDF.js after dependency changes:

```sh
npm ci --prefix front --ignore-scripts
npm --prefix front run vendor:math
```

Node is not required to run the Python application with these assets present. Keep lockfiles and bundled licenses.

## Fidelity and verification scope

Correct typesetting does not prove that an LLM transcribed the PDF correctly or that generic math fonts match its original typography. Generated sets retain unchecked source metadata and references for comparison. The current work does not claim universal PDF fidelity.

The regression suite covers generation, provider adaptation, shared mathematical rendering, owner-scoped persistence, historical payload compatibility and PDF export. Run it with `uv run --python 3.12 --project back --extra dev pytest -q`. Real-provider latency is outside the offline acceptance suite. The browser checks live under `front/scripts/browser_check.cjs`.

## Product branding and repository rename

The product is **Acadence**. Technical identifiers and the existing production domain remain compatible with previous releases. See [the branding audit and manual repository rename checklist](docs/rebranding.md). The intended repository name is `acadence`; it has not been renamed by this change.
