# Design

## Problems beta and assessment colors

Label the Problems selector and active problem-set status as Beta, including restored sets, without changing persisted mode values. Keep Correct/Incorrect labels and use dark green/red text and borders over translucent matching fills.

## Context

The existing FastAPI application serves one configured PDF, single-page PDF.js preview, and transient structured LLM responses. It has reusable KaTeX rendering and external prompts, but no document library or study-set database. See proposal.md for the requested UX.

## Goals / Non-Goals

**Goals:** A functional local document workspace; context-aware generation; responsive split panes; tabbed practice with physical flip cards; explicit SQLite saves; faithful rendering of editable math in exported PDFs.

**Non-Goals:** Google login, public deployment, Garage provisioning, OCR, DOCX, mathematical correctness proofs, or a claim that generic typesetting reproduces every source PDF font.

## Decisions

### Use a persistent local document repository

Store document metadata and study-set JSON in SQLite, with uploaded binaries in a managed local directory behind repository methods. Start with an empty library and an Upload PDF action. A source PDF is optional and explicitly supplied with `--pdf` only for legacy inspection. The production image includes no startup PDF. Use opaque document IDs and content hashes, validate PDF/image/text content, and retain original names for display. Keep files across restarts. This is a local adapter pending the broader authenticated Garage integration.

Migrate existing databases once to hide the old bundled sample by its exact content hash. Retain its managed binary and metadata so saved study-set citations still work. Explicitly uploading that PDF restores it to the visible library. The migration leaves other uploads and saved sets available. Generation requires a selected uploaded PDF; the default source ID may be null.

Support PDF, UTF-8 TXT/MD, PNG, JPEG, and WebP, as confirmed by the user. Preview PDFs in PDF.js, text as escaped text, and images through the managed file endpoint. Add bounded uploads and combined generation payload limits without requiring formula extraction.

### Separate reading from generation scope

Document tabs preserve their preview instances. PDF.js builds page placeholders and renders nearby pages lazily; continuous scrolling and page jumps can reach the whole document. Resizing causes visible pages to be re-rendered at the new width. The generation dialog independently selects the primary PDF, whole-document or inclusive from/to ranges, mode/count, and optional context files with their own ranges.

Separate open tabs from the persistent file library. Closing a saved file only closes its preview; an Open files dialog reopens it. Show selected files immediately as unsaved upload tabs, require confirmation before closing an unfinished or failed upload, and allow failed uploads to be retried. Persist the open saved-file tab list locally. Use a local SVG favicon for browser identification.

Keep PDF page heights explicit so a width change cannot reflow the document before a reading anchor is captured. During layout changes, preserve the page and relative vertical position at the top of the viewport, disable browser scroll anchoring, and update geometry and scroll position together. Retain the old canvas while rendering its replacement offscreen, defer expensive rendering until resizing settles, and release only distant canvases after layout stabilizes. Explicit outer-workspace notifications on resizing, drag completion, and file reopening complement viewport/container observers. A final two-frame measurement and visible-page redraw, followed by a missing-canvas recheck, must complete without requiring pointer or scroll interaction.

The generation dialog also accepts an optional plain-text comment (up to 4,000 characters). Pass it through an external prompt template as learner preferences bounded by the primary-source rules, and retain it in the study-set snapshot when saved. Comments require no context attachment.

Send the selected primary PDF and selected context attachments through a provider-independent document-input contract. Context files guide examples and task style; source formulas remain grounded in the primary selected pages. Prompts include document identity and per-file original-page mapping, all from external resources. Citation validation checks both document identity and selected page scope. The total selected PDF-page limit is 100, so the supplied 59-page file can be selected in full; the combined input-byte limit is 40 MB.

### Make the workspace responsive and keyboard accessible

Use a full-height workspace with independently scrollable panes and editor-style tab strips. A vertical separator supports horizontal pointer dragging and arrow-key resizing, bounded by usable minimum pane widths. Persist its ratio locally. On narrow screens, stack panes without imposing desktop minimum widths.

Keep the layout English and functional. Put generation options in a dialog, and move renderer diagnostics out of the normal study flow. Keep source navigation and file download within the document toolbar.

### Preserve sets and use a physical card interaction

Generated sets remain independent in top-level result tabs. Inner item tabs select individual problems or cards. Flashcards have front/back faces with a CSS three-dimensional flip, pointer/keyboard controls, accessible hidden-side handling, and next/previous navigation. Source links and editable controls do not accidentally trigger a flip. Problems use an ordinary reading view and an expandable solution.

Unsaved generation results remain drafts in browser memory. Explicit Save persists the canonical set, including source/context references, TeX, original quiz variants, and prompt metadata. Study-set tabs have sibling close controls like file tabs. Closing a draft offers Save and close, Close without saving, and Cancel. Saving must succeed before a requested close completes; cancelling a dialog or a failed save keeps the draft open. Closing a saved set removes its open tab while its database record remains available through Saved sets. Persist the open saved-set IDs and active set locally so closed tabs stay closed after reload.

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

## Authenticated library and responsive controls revision

The application now has mandatory Google identity and owner-scoped storage. The earlier local-only and strict-formatting descriptions are historical; preserve the current shared renderer, non-blocking math policy and backward-compatible study payloads.

Deletion uses an owner-protected impact read and a conditional DELETE. Recompute the impact inside the database transaction; reject stale confirmations rather than deleting newly related sets silently. Every library deletion opens a confirmation dialog. File deletion prominently states how many sets with that primary source will be permanently removed. As explicitly clarified by the owner, sets using the file only as additional context survive; detach that context snapshot without changing their items, formulas, primary citations or metadata. Remove the managed binary after the transaction and clear its local preview/page cache. Set deletion leaves files and other sets intact.

Native disclosure controls collapse the Files and Saved study sets sections, remembering account-specific preferences. Keep the source iframe mounted when its pane is hidden. A file-bar button and dragging the desktop divider to its left edge collapse the source; a persistent Show PDF control restores its previous width. On phones, scrolling the outer workspace fully into practice hides the source and gives practice the available viewport. A downward pull at the top of practice or Show PDF restores it. Do not intercept scrolling within long answers, text selection or horizontal formulas. Source citations reveal the pane before navigating. Respect reduced motion and preserve reading anchors on restore.

Use a small IndexedDB cache of derived visual previews, keyed by account, immutable document ID/content hash and cache revision. Library cache hits bypass original-file downloads and PDF.js loading. Cache at most ten viewed PDF page images per account as an LRU, with byte limits; show available cached images while the full source and selectable text load. This is a speed optimization, not offline authorization or a cache of generated mathematics. Verify the session and document ownership before displaying cached pages. Deletion and sign-out invalidate relevant entries and pending writes across tabs. Unavailable/cleared/quota-limited browser storage falls back to normal rendering without blocking use. Do not change private API responses to public-cacheable.

Retain phase text, elapsed time, spinner, cancellation and deadlines during generation. Remove accepted/requested item counters, since the complete set arrives in one provider response.

## Safari cache recovery and icon controls

Persist derived image bytes and MIME types rather than file-backed Blob objects, avoiding Safari's repeated IndexedDB Blob read/write failure. Read existing Blob entries by materializing their bytes outside the transaction, migrating readable entries without changing source or study content. An unreadable derived entry is a cache miss. Decode cached images before inserting them; discard a failed image entry and render the authorized original normally. Apply recovery to library previews and cached PDF pages. Keep existing privacy, invalidation and size limits.

Use inline SVG panel/arrow icons for source show/hide controls, with English accessible labels, tooltips and adequate touch targets. Put the collapse control first in the source tab bar, at the left edge when expanded; the restore icon remains first in the practice tab bar when collapsed. Retain keyboard controls, reading position and mobile gestures.
