# Spec Delta

## Purpose

Lets authenticated learners mark source PDFs, retain editable notes and use explicitly saved annotated copies for study generation without replacing originals.

## ADDED Requirements

### Requirement: Mark text and draw on pages
Learners SHALL highlight selected PDF text and draw pen strokes with selectable colors and widths. Marks SHALL remain aligned with their source through zoom, resizing and page rotation.

#### Scenario: Highlight multiple lines
- **WHEN** selected text is highlighted
- **THEN** the selected runs receive translucent colored backgrounds while the original text remains readable

#### Scenario: Draw and resize
- **WHEN** a learner draws on a page and changes the viewer width or zoom
- **THEN** the same vector stroke remains at its source position

### Requirement: Control and undo annotation actions
A hideable toolbar SHALL offer selection, highlight, pen, whole-annotation eraser, colors, widths, Undo/Redo and Save. Ctrl/Cmd+Z SHALL undo a complete marking or erasing gesture, and Ctrl/Cmd+S SHALL save notes without opening the browser save dialog.

#### Scenario: Undo erasing
- **WHEN** a learner erases one or more strokes/highlights in one gesture and invokes Undo
- **THEN** that gesture is restored

#### Scenario: Hide tools
- **WHEN** the toolbar is hidden
- **THEN** existing notes remain visible and normal reading and selection remain available

### Requirement: Keep one editable copy
The first explicit save SHALL create one owned edited copy linked to an unchanged original. Later saves SHALL update that copy in place while retaining its editable marks. Conflicting saves SHALL preserve the local changes and report the conflict.

#### Scenario: Save and reopen
- **WHEN** saved notes are reopened after restart
- **THEN** the marks remain editable and the original remains separately available

#### Scenario: Edit again
- **WHEN** an edited copy is saved again
- **THEN** its document identity remains the same and no additional copy is created

#### Scenario: Concurrent save
- **WHEN** another tab has already saved a newer revision
- **THEN** a stale save is rejected and its local work is retained

### Requirement: Retain portable annotated PDFs
Edited copies SHALL be distinguishable in the library and downloadable as PDFs containing their visible marks and original page content. Generation SHALL receive the selected saved PDF including its marks.

#### Scenario: Generate from a saved copy
- **WHEN** a saved edited copy is selected as source or context
- **THEN** its annotated PDF is submitted with the selected page range

### Requirement: Choose how unsaved notes enter generation
Before generation from a PDF with unsaved notes, the learner SHALL choose the unchanged original, save and use the edited copy, or Cancel. A failed or canceled save SHALL not start generation or discard notes.

#### Scenario: Use the original
- **WHEN** the learner chooses the original
- **THEN** generation uses the original PDF and unsaved notes remain open

#### Scenario: Save and generate
- **WHEN** the learner chooses Save and use edited copy
- **THEN** saving succeeds before generation starts with the copy

### Requirement: Confirm discarding notes
Closing a PDF with unsaved notes SHALL offer Save and close, Discard changes and Cancel. Leaving the browser page with unsaved notes SHALL warn the learner.

#### Scenario: Cancel closing
- **WHEN** the learner cancels closing an unsaved annotated PDF
- **THEN** its marks and undo history remain open

### Requirement: Delete linked copies with their original
Confirmed deletion of an original SHALL remove its edited copy and sets using either as primary source. Deleting only the copy SHALL retain the original. Context-only sets SHALL survive with deleted attachments detached.

#### Scenario: Delete an original with a copy
- **WHEN** its deletion is confirmed after reviewing the consequences
- **THEN** the original, edited copy and primary-dependent sets are removed
- **AND** the confirmation prominently identifies those consequences

### Requirement: Preserve ownership and old formats
Annotation reads, writes and files SHALL require the authenticated owner. New releases SHALL continue reading existing documents, saved sets and drafts with compatible defaults and shall not modify historical content as a migration.

#### Scenario: Open an existing file
- **WHEN** a file has no annotation data
- **THEN** it opens normally with an empty editable layer

#### Scenario: Request another owner's notes
- **WHEN** a different account requests an annotation record
- **THEN** it receives the same not-found response as an unknown document

### Requirement: Save before leaving the workspace
Home navigation and sign-out SHALL offer Save and leave, Leave without saving and Cancel whenever any open PDF notes, study sets or file uploads are unsaved. Save and leave SHALL wait for all saves to succeed. A canceled or failed save SHALL retain the workspace. Closing or reloading the browser SHALL retain the native unload warning; browsers control that warning's text and available actions.

#### Scenario: Leave with multiple unsaved files
- **WHEN** the learner requests home navigation or sign-out with unsaved work in multiple tabs
- **THEN** the confirmation lists that work and saving completes before leaving

#### Scenario: Failed leave save
- **WHEN** one save fails
- **THEN** navigation and sign-out do not occur and the remaining local work stays open

### Requirement: Compact color controls and centered recall questions
Annotation colors SHALL be selected from visible color swatches with accessible names and selected state. Flashcard question text SHALL be horizontally centered on the front; answer layout SHALL remain readable.

#### Scenario: Select a swatch
- **WHEN** a learner selects a color with pointer or keyboard
- **THEN** that color applies to the active marking tool and its selected state is visible without relying only on color
