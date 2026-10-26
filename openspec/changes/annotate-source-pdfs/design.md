# Design

## Context

See proposal.md. PDF.js renders lazy page canvases and selectable text inside retained iframes. Private documents use content-addressed managed files and SQLite records; study sets retain source snapshots. Existing formats must remain readable.

## Goals / Non-Goals

Preserve original page content and reuse its PDF coordinate system for editable vector marks. Keep annotation handling in modules independent of formula generation/rendering. This change adds highlights and ink, not source-text replacement or real-time shared editing.

## Decisions

- Store a versioned annotation JSON layer in an additive owner-scoped SQLite table linked to an original and one edited document. A unique original/owner pair enforces the owner's single-copy decision. Document metadata gains optional original ID and revision defaults; existing study shapes remain supported.
- Use PDF.js viewport inverse transforms to store unrotated PDF coordinates, including crop origins. Render SVG layers over the base original; keep text selection available in reading/highlight modes. Store translucent highlight polygons and rounded pen polylines. Erasing removes a complete stroke/highlight; a gesture is one undo operation. A bounded immutable history preserves save/undo semantics.
- Save a portable PDF by merging vector overlay streams into a fresh copy of the immutable original using pypdf. Keep original boxes/rotation, fonts and selectable content. The editable JSON is retained separately. Rebuild from the original each save to avoid duplicated marks. Alternative raster flattening would lose source quality; PDF-only annotation objects would not reliably appear to every generation/preview consumer.
- Protect writes with expected revisions, recheck inside the commit transaction, and atomically install a new content-addressed binary. Concurrent changes or deleted originals reject a stale save. Updating a copy changes its hash but keeps its document ID. Normal private file endpoints serve the annotated bytes; the editable viewer loads the original with its JSON layer to avoid drawing the marks twice.
- Parent/iframe messages are restricted to the same origin and known document frames. The iframe owns drawing/selection/history; a parent toolbar bridge owns controls, close choices and generation preflight. Saving an original transitions its retained iframe to the copy while leaving an original tab available. Editing an original with an existing copy opens that copy.
- Generation resolves unsaved changes for every selected source/context PDF before creating a job. Use original preserves local notes; Save and use copy waits for persistence and remaps the selected ID; Cancel starts no job. Prompt/provider contracts remain unchanged.
- Deletion computes the original/copy family transactionally. Cascade primary-source sets, detach context-only references, remove annotation rows and binaries, and invalidate each deleted document's visual cache. The confirmation and revision include linked copies.
- The toolbar uses existing colors, compact SVG controls and touch targets, can collapse, and restores Select mode when hidden. Keyboard shortcuts handle Ctrl and Cmd while leaving text inputs' undo intact. Unsaved annotation tabs and browser unload are guarded.

## Risks / Trade-offs

- Coordinate drift on rotated/cropped pages -> use the installed PDF.js transforms and verify vector overlays on those cases.
- Large ink histories -> bound payloads and shallow immutable history, simplify closely spaced input points and commit once per gesture.
- Save/generation races -> disable editing during save, retain failed local state and require successful revision checks before job creation.
- A saved copy can change after a study set is generated -> retain the generation source hash/revision snapshot; original PDF content remains immutable and stored study formulas are unchanged.
- Original signatures cannot remain valid on an edited copy; the original bytes are always retained. Existing form/page structures are cloned rather than intentionally flattened.

## Migration Plan

Create the annotation table additively on startup; do not rewrite existing document/set rows. Missing annotation metadata means an ordinary file with no notes. Version the new layer from its first release and preserve all supported versions. Deploy through the existing workflow after local/API/browser checks. Do not roll back to an older app against new edited files without retaining their annotation table and files.

## Follow-up interaction decisions

Use a reusable leave-confirmation controller for in-app home navigation and the account sign-out hook. List unsaved content, save every dirty annotation tab and study set and await pending uploads before committing navigation. Partial save success is retained; a failure keeps the dialog and remaining work available. Keep the native beforeunload warning for closing/reloading because browser chrome cannot run an asynchronous custom save dialog. Replace the color select with five named, keyboard-accessible swatch buttons with an explicit selected marker; keep text selection intact when clicking a swatch. Center only flashcard-front text.
