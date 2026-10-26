# Proposal

## Why

Learners need to highlight relevant text and draw working notes directly on source PDFs. Those edits must remain editable and be available to generation without replacing the original lecture file.

## What Changes

- Add text highlights and vector pen strokes, a small color palette, pen widths, whole-annotation erasing, Undo/Redo and Ctrl/Cmd+Z.
- Add a collapsible annotation toolbar matching the existing workspace, with explicit Save and Ctrl/Cmd+S.
- Keep one owner-scoped edited copy per original, as confirmed by the owner. Further saves update that copy and preserve its editable layer.
- Mark edited copies in the library, download them as annotated PDFs and allow their use as generation sources/context.
- Before generation with unsaved notes, offer the unchanged original, Save and use edited copy, or Cancel.
- Warn before closing unsaved notes. Protect concurrent saves and keep source-relative coordinates stable through zoom, resize and page rotation.
- Offer saving all unsaved work before home navigation or sign-out, keep native browser unload warnings, center recall questions and expose colors as accessible swatches.
- Deleting an original also deletes its edited copy and sets based on either primary file; context-only sets retain their content and detach the deleted references.

## Capabilities

### New Capabilities

- `pdf-annotations`: Editable source-PDF marks, copy lifecycle, generation choices and deletion semantics.

### Modified Capabilities

None. The main spec inventory is currently empty; existing workspace changes remain compatible.

## Impact

Owner-protected annotation APIs, an additive SQLite table, document metadata defaults, a vector PDF overlay writer, isolated annotation frontend modules, library badges/deletion warnings and generation preflight. Existing study payloads and rendering contracts remain supported. No additional LLM request or paid provider dependency is introduced.
