# Design

## Context

See proposal.md. The local FastAPI workspace now provides multi-file document tabs, continuous PDF reading, generation-time ranges/context, SQLite study sets, physical flip cards, and PDF export. Generation receives complete selected pages; extracting and storing every source formula is unnecessary. Version one targets digital PDFs with printed mathematical notation.

## Goals / Non-Goals

**Goals:** Private PDF storage, Google identity, page-scoped study generation, editable mathematical text, traceable quiz changes, saved study sets and practice progress, external prompts, and replaceable infrastructure adapters.

**Non-Goals:** OCR and handwriting, Google Drive access, shared libraries, unrelated invented formulas, mandatory formula catalogs, or treating model output as verified source truth.

## Decisions

### Use complete selected pages as generation input

The generation service obtains the user's owned PDF through the storage adapter, validates the requested pages, and builds an in-memory PDF containing those complete pages. Supply an explicit attachment-page to original-page mapping. Local extraction of all text or formulas is not a prerequisite. Bounded page selections are supported first; larger selections can be split into generation jobs with original-page mapping retained.

The provider interface accepts selected source/context documents and composed prompt text, returning typed study content and provider metadata. Context examples guide style and difficulty while source citations remain grounded in the primary selected pages. OpenAI receives PDF/text file inputs and image inputs with explicit document identities and page mappings. The local service has limits, timeout, and no automatic retry. Persist job state before introducing a background worker.

### Store study content and only its used formulas

A study set contains document identity, selected pages, mode, item blocks, generation metadata, and practice state. An item contains question and answer block arrays. A block is plain text or editable TeX math, and an item or page can contribute several mathematical expressions. Store these blocks with the generated set, rather than pre-populating a global formula catalog.

A math block cites its original PDF page, optional model-reported line range, and an optional source quote or nearby heading. Validate the page against the selection. Lines are nullable and remain model-reported; do not invent them or represent them as verified coordinates. Source text can retain its original language while generated prose and the interface are English.

### Render model mathematical output as editable text

Persist the mathematical source and renderer profile rather than using generated HTML as the authoritative record. The current renderer uses locally served KaTeX HTML with accessibility MathML, strict errors, disabled trusted HTML commands, and bounded expansion. Treat prose as text. Display a failure for an unsupported formula without hiding the rest of the item. Both a response and a single item must support multiple formulas.

Original symbols, font variants, fractions, scripts, delimiters, alignment, spacing, and line breaks remain the source-fidelity target. Generic typesetting and schema validation do not prove that target. Keep transcriptions explicitly unchecked and offer source comparison and editing. A parse success must never imply verified PDF fidelity. The source-font experiment remains an optional diagnostic tool; its measurements do not validate LLM transcription.

### Preserve deliberate quiz changes within an item

An intentional variant retains the unmodified source TeX, changed TeX, source citation, and edit description within the generated material. Do not require a separately saved source-formula record. Reveal the change and its explanation with the answer; the question need not disclose it. A local edit preview preserves the received original and cannot silently overwrite source truth.

The model may reuse source formulas and deliberate source-derived variations. Prompts and review must distinguish those from unrelated invented formulas. Page validation establishes allowed source scope, not mathematical correctness.

### Keep layers independent of providers

```text
Browser (server-served UI, PDF viewer, HTML/MathML renderer)
    -> FastAPI routes -> use cases
        -> Generation service -> prompt resources -> StudyProvider -> OpenAI
        -> PDF service -> object-storage interface -> Garage
        -> Auth service -> Google identity and application sessions
        -> repositories -> SQLite users, PDFs, study sets, jobs and practice
```

Keep frontend controls functional and minimal: sign-in, library, upload, document preview/download, page selection, generation, source navigation, answer reveal, and formula correction. All application copy, accessibility labels, and documentation are English. Do not carry decorative prototype hero sections or a saved-formula catalog into the application. Plain JavaScript already provides the rendering boundary; HTMX/Alpine/Pico can be introduced where they simplify these flows.

### Load every LLM instruction from external files

All system messages, task templates, and reusable examples live under a version-controlled prompt directory. The loader composes runtime page mapping, mode, and item count without embedding natural-language instructions in routes or adapters. Record prompt identifiers and content hashes with each generation. Provider adapters add no hidden instructions. Treat document contents as untrusted source material, never as instructions.

### Use Google for identity and application-owned sessions

Use authorization-code sign-in with transaction-bound state and PKCE, requesting identity scopes only. The application owns the authenticated session in a secure HTTP-only same-origin cookie. Retain Google access/refresh tokens only if a future feature needs a Google API. Persist application session revocation and expiration; do not expose credentials to frontend JavaScript. See [Google web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server) and [OAuth security best current practice](https://www.rfc-editor.org/rfc/rfc9700.html).

### Use SQLite metadata and private Garage objects

SQLite stores users, sessions, PDF metadata/ownership/page count, generation jobs, selected pages, study sets with their used math blocks/citations, prompt versions, and practice progress. Garage stores PDF binaries behind an S3-compatible storage interface. Authorize every source-file access, preview, download, and generation request. Keep buckets private; any signed URLs must be short-lived and issued only after ownership validation.

Start with one application instance. Isolate repositories for a later database migration if concurrency or deployment needs require it. Coordinate database and object backups. Generated sets should be persisted independently from their practice attempts so repeated practice does not modify original material.

## Risks / Trade-offs

- Model transcription and explanations can be wrong -> Retain source references, unchecked state, and correction controls.
- Generic math fonts differ from source fonts -> Keep fidelity as an acceptance target; do not claim an automatic exact match.
- Model-reported lines may be wrong -> Prefer the page and quote; allow missing lines.
- PDF input consumes context and takes time -> Bound selections and output, persist jobs for longer requests, and surface failures.
- SQLite write concurrency is limited -> Start with one instance and revisit before scaling.
- Private documents can leak through public object URLs -> Authorize every access and keep objects private.

## Migration Plan

Keep existing ignored prototype records as diagnostic data. Do not import a page-wide formula inventory into SQLite. The `study-workspace-ux` change implements local managed files, SQLite study sets, per-file range selection, tabs, resizable panes, flip cards, and Chromium printing with the shared math renderer. Integrate these repositories and use cases with Google-owned sessions, account ownership, Garage objects, and practice attempts before production deployment.

## Open Questions

- Deployment upload size and total library quota.
- Deletion policy for PDFs referenced by existing study sets and practice history.
