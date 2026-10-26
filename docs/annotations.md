# PDF annotations

An original PDF remains immutable. The first explicit annotation save creates one owned `- annotated.pdf` copy; subsequent saves update that document ID. Its portable PDF includes vector highlights/ink while an independent editable layer retains their geometry. The viewer draws the layer over the original, preventing duplicated notes. Generation and downloads use the saved, annotated bytes.

## Use

Open a PDF and select the pencil icon beside Download. The toolbar can be hidden with the same icon; existing marks remain visible and text can still be selected. On phones, opening the tools expands the reading pane to provide more drawing space.

- **Select text**: read, select and copy the PDF's text.
- **Highlight selected text**: select text first and click Highlight, or activate Highlight before selecting text. Adjacent runs merge into a continuous background on each selected line. Choose one of five color swatches; the selected color has an outline and check mark. Each swatch has an accessible name and supports keyboard activation.
- **Draw**: choose a color and 1, 2, 4 or 6 pt width, then draw with a pointer, touch or pen. Switch to Select to scroll normally with touch.
- **Eraser**: tap or drag over notes to remove whole strokes or highlights. A drag is one undo action; this does not erase the original page content.
- **Undo / Redo**: use the toolbar, Ctrl/Cmd+Z and Ctrl/Cmd+Shift+Z. Ctrl+Y also redoes. The current viewer retains up to 100 operations; reopening retains the saved marks, not the prior undo history.
- **Save**: use the disk icon or Ctrl/Cmd+S. The first save creates the edited copy; later saves update it. Editing is paused during a save. A failed or conflicting save keeps the local changes open and reports the error.

The library labels the copy **Edited copy** and names its original. Opening an original's annotation tools when a copy already exists opens that copy. Download returns the saved PDF, so save pending work before downloading. Unsaved changes are held in the open viewer; they are not an automatic persistent draft. Closing asks to save/discard/cancel, and browser navigation warns about unsaved work.

Selecting the home link or **Sign out** opens **Save before leaving?** when any open PDF, study set or upload is unsaved. **Save and leave** saves every dirty PDF, saves study sets under their current titles and waits for uploads before proceeding. Cancel retains the workspace; a failed save stays in the dialog with the remaining work listed. **Leave without saving** explicitly proceeds without saving remaining work. An active generation must finish or be canceled before Save and leave can complete. The library also guards uploads when opening a file or signing out and offers another upload attempt for failed pending files.

Closing a browser tab, reloading or leaving through browser controls uses the browser's native warning. Browser security rules do not allow the page to replace its text/buttons or complete asynchronous saves from that event; cancel that departure and save in the workspace first.

Before generating with any unsaved source or context PDF, a filename-specific dialog offers **Use original PDF**, **Save and use edited copy**, or **Cancel**. The original choice keeps local notes open; the save choice waits for successful persistence. Neither a canceled nor failed save starts generation. Other selected files keep their independent ranges.

## Data and API

- `GET /api/documents/{id}/annotations`: current document, immutable `base_document`, optional `copy_document`, revision and annotation data. Originals have an empty layer; an existing copy can be opened for editing.
- `PUT /api/documents/{id}/annotations`: annotation data plus `expected_revision`. First save uses revision zero; later saves require the current copy revision. Stale or concurrent creation returns 409 and keeps local work available. Every route requires the authenticated owner and unsafe methods require the trusted origin.

Version 1 is `{ "schema_version": 1, "items": [...] }`. Missing markers default to version 1. Each mark has a unique ID, one-based page and hex color. Ink adds `kind: "ink"`, `width` and PDF-space `points`; highlights add `kind: "highlight"` and ordered four-point `quads`. Coordinates use the original unrotated PDF user space, including crop origins. PDF.js inverse viewport transforms handle reading zoom and rotation. Bounds, finite coordinates, unique IDs and payload complexity are validated before writing. Highlight opacity is fixed at 28 percent with multiply blending.

The additive `document_edits` table stores the owner, original/copy relationship, revision and versioned JSON. Document snapshots gain optional `original_document_id` and default-zero `annotation_revision`; older documents, saved study sets and drafts stay readable. The existing study-set schema remains version 1. Source hash/revision snapshots record what generation used; editing notes does not change stored questions or formulas.

Deleting an original includes its edited copy and sets with either as main source. Deleting only the copy retains its original. Sets with deleted files only as context keep their content and detach those attachments. Confirmations include the whole current impact and reject a stale review.

## Limits

Highlighting needs an extractable text layer; scanned images can be drawn on but do not gain OCR. The editable layer supports up to 5,000 marks and 200,000 points, with 20,000 points per stroke and 5,000 quads per highlight. Erasing removes entire marks, not fragments. The feature does not change the source text or provide collaborative editing. Annotating changes the copy's bytes, so any original digital signature continues to apply only to the untouched original.
