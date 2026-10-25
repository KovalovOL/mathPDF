# Library management, mobile layout and visual cache verification

Date: 2026-10-26.

## Automated checks

- Full suite: **94 passed**, with one existing Starlette/httpx deprecation warning (15.57 seconds).
- New owner-scoped deletion coverage verifies the confirmation revision, 428/409 handling, foreign-ID isolation, primary-source cascade, context-only detachment, binary cleanup, and retained sets reopening, saving and exporting.
- A versionless saved payload survives context detachment with all items and metadata unchanged. Historical compatibility fixtures remain unchanged; the canonical study-set schema is unchanged.
- Isolated Chromium cache checks verify the ten-page LRU bound, account/content separation, deletion/sign-out invalidation, suppression of late writes, and unavailable-storage fallback.
- An isolated layout component check verifies mobile outer-scroll collapse, top-of-answer downward restoration, priority for long-answer/horizontal scrolling and interactive targets, desktop Home/restore, and retention of the same document iframe. Touch events are simulated; this is not a physical iPhone/Safari test.
- JavaScript syntax checks passed for all seven affected modules; `git diff --check` and strict OpenSpec validation passed.

## Local browser observations

A disposable loopback application used its own data directory, ordinary authenticated fixture session and a deterministic five-second provider. No production account/data or external model request was used.

- Home displayed six PDF previews and two saved sets. The file-deletion dialog emphasized one primary-source set that would be deleted and separately explained that the one context-only set would remain. Cancel received default focus. The browser dialog was canceled; destructive paths ran against isolated API test fixtures.
- A home reload reused all six cached previews, displaying six images and zero newly rendered PDF canvases.
- At 390 × 844, collapsing Files brought Saved study sets immediately into view. Scrolling into practice hid the source pane, and a source-page link restored it.
- Desktop Hide/Show and dragging the divider fully left retained page 5. Reloading restored page 5 and reused two cached page images while the source loaded. The source text layer remained selectable.
- At 320 × 568, the workspace had no horizontal document overflow. A six-card fixture generation displayed phase/time/Cancel without an obsolete ready-count and completed with six cards; the waiting UI cleared.
- Saved screenshots under ignored `artifacts/ui/`: `library-delete-warning.png`, `mobile-library-collapsed.png`, `mobile-study-focus.png`, `desktop-viewer-collapsed.png`, and `mobile-generation-result.png` (captured during waiting).

## Limits and release

The page cache contains derived page images, not full offline PDFs or cached private API responses. Authoritative metadata access precedes cache display; selectable text arrives with the authorized PDF. Browser storage may be evicted or unavailable, in which case ordinary rendering remains available. Real-device gesture and browser-specific repaint behavior has not been exhaustively tested.

Deployment verification will be recorded after the existing GitHub Actions workflow completes.
