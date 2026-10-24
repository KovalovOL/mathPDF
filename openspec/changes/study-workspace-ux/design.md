# Design

## Context

The existing FastAPI application serves one configured PDF, single-page PDF.js preview, and transient structured LLM responses. It has reusable KaTeX rendering and external prompts, but no document library or study-set database. See proposal.md for the requested UX.

## Goals / Non-Goals

**Goals:** A functional local document workspace; context-aware generation; responsive split panes; tabbed practice with physical flip cards; explicit SQLite saves; faithful rendering of editable math in exported PDFs.

**Non-Goals:** Google login, public deployment, Garage provisioning, OCR, DOCX, mathematical correctness proofs, or a claim that generic typesetting reproduces every source PDF font.

## Decisions

### Use a persistent local document repository

Store document metadata and study-set JSON in SQLite, with uploaded binaries in a managed local directory behind repository methods. Import the startup PDF into this workspace without modifying the original. Use opaque document IDs and content hashes, validate PDF/image/text content, and retain original names for display. Keep files across restarts. This is a local adapter pending the broader authenticated Garage integration.

Support PDF, UTF-8 TXT/MD, PNG, JPEG, and WebP, as confirmed by the user. Preview PDFs in PDF.js, text as escaped text, and images through the managed file endpoint. Add bounded uploads and combined generation payload limits without requiring formula extraction.

### Separate reading from generation scope

Document tabs preserve their preview instances. PDF.js builds page placeholders and renders nearby pages lazily; continuous scrolling and page jumps can reach the whole document. Resizing causes visible pages to be re-rendered at the new width. The generation dialog independently selects the primary PDF, whole-document or inclusive from/to ranges, mode/count, and optional context files with their own ranges.

Send the selected primary PDF and selected context attachments through a provider-independent document-input contract. Context files guide examples and task style; source formulas remain grounded in the primary selected pages. Prompts include document identity and per-file original-page mapping, all from external resources. Citation validation checks both document identity and selected page scope. The total selected PDF-page limit is 100, so the supplied 59-page file can be selected in full; the combined input-byte limit is 40 MB.

### Make the workspace responsive and keyboard accessible

Use a full-height workspace with independently scrollable panes and editor-style tab strips. A vertical separator supports horizontal pointer dragging and arrow-key resizing, bounded by usable minimum pane widths. Persist its ratio locally. On narrow screens, stack panes without imposing desktop minimum widths.

Keep the layout English and functional. Put generation options in a dialog, and move renderer diagnostics out of the normal study flow. Keep source navigation and file download within the document toolbar.

### Preserve sets and use a physical card interaction

Generated sets remain independent in top-level result tabs. Inner item tabs select individual problems or cards. Flashcards have front/back faces with a CSS three-dimensional flip, pointer/keyboard controls, accessible hidden-side handling, and next/previous navigation. Source links and editable controls do not accidentally trigger a flip. Problems use an ordinary reading view and an expandable solution.

Unsaved generation results remain drafts in browser memory. Explicit Save persists the canonical set, including source/context references, TeX, original quiz variants, and prompt metadata. Saved sets appear after reload. Closing a tab does not delete its database record.

### Print PDFs with the same mathematical renderer

Render a dedicated print document using the same locally served KaTeX implementation and fonts. A headless Chromium worker produces PDF bytes after rendering and font loading complete. Use an isolated browser context and locally intercepted asset requests; no remote document HTML or external assets are executed. Reject unsupported math or overflowing expressions rather than silently dropping them.

Export contains questions and an answer section. TeX remains the canonical editable source and Chromium embeds mathematical text/fonts in the PDF. This avoids rasterizing study formulas and keeps fraction, script, operator, and alignment layout consistent with the UI. Chromium is an explicit runtime dependency; support an installed Chrome path and document bundled browser installation.

## Risks / Trade-offs

- Many PDF canvases can consume memory -> Render nearby pages lazily and release distant canvases.
- Resizing can invalidate rendering work -> Use render versions and cancel stale page tasks.
- Context can be mistaken for authoritative lecture content -> Label attachment roles and validate primary-source citations.
- Long formulas can exceed print width -> Fit rendered expressions and fail clearly when layout is unsupported.
- Browser printing requires Chromium -> Detect the local executable or report a setup error without corrupting the set.
- Local storage has no account isolation -> Keep loopback binding; production identity/storage remain in the platform plan.

## Migration Plan

Add a new SQLite workspace and managed file directory under the existing ignored data root. Preserve old source-font diagnostic files and routes. Generation responses gain document identities, context snapshots, and a set ID; existing single-document calls can still use the configured default PDF.
