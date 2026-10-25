# Spec Delta

## Purpose

Provides a document and practice workspace for exploring source material before generation and retaining useful mathematics study sets.

## ADDED Requirements

### Requirement: Confirm library deletion
The library SHALL offer owner-scoped deletion of files and saved sets with explicit confirmation before every deletion. File confirmation SHALL prominently identify primary-source sets that will also be deleted. A stale impact confirmation SHALL require renewed review.

#### Scenario: Delete a primary source
- **WHEN** a learner confirms file deletion
- **THEN** that file and only sets with that primary source are deleted
- **AND** sets using it only as context survive with that attachment detached and study content preserved

#### Scenario: Delete one saved set
- **WHEN** a learner confirms deletion of a saved set
- **THEN** only that owned set is deleted, retaining its uploaded files and other sets

### Requirement: Collapsible responsive reading
The library sections SHALL be collapsible. The source pane SHALL fully collapse through an explicit control or the desktop divider's left edge, and SHALL restore without losing reading position. Mobile study focus SHALL support restoring the source by a downward pull at the top of practice or an explicit control.

#### Scenario: Focus on practice on a phone
- **WHEN** the learner scrolls the outer workspace fully into practice
- **THEN** the source hides and practice uses the available viewport
- **AND** ordinary scrolling inside a long answer remains available

#### Scenario: Restore a hidden source
- **WHEN** a learner chooses Show PDF, pulls down at the top of mobile practice or follows a source citation
- **THEN** the existing viewer reappears with its reading state intact

### Requirement: Bounded private visual caching
The browser SHALL cache derived library previews and up to ten recently viewed PDF page images per account, keyed by document content and cache revision. Session and ownership checks SHALL precede cached page display. Deletion and sign-out SHALL invalidate affected caches. Cache failures SHALL fall back to normal rendering.

#### Scenario: Reload the library
- **WHEN** a valid preview exists in the current account's cache
- **THEN** the thumbnail appears without downloading and rendering the original again

#### Scenario: Reopen a recently viewed page
- **WHEN** its cached image is available after authorization
- **THEN** that image can appear while the source PDF and selectable text load
- **AND** page-image cache entries remain bounded by count and bytes

### Requirement: Single-request waiting text
Generation waiting SHALL retain phase, elapsed time and cancellation without showing obsolete accepted/requested item progress.

#### Scenario: Wait for the complete response
- **WHEN** a set is being generated
- **THEN** no zero-of-N or accepted-item counter appears

### Requirement: Start with an upload prompt
The application SHALL start without a required or automatically imported bundled PDF. An empty library SHALL show an Upload PDF action, and generation SHALL require a selected PDF. Existing installations SHALL hide the old bundled sample from the library through a one-time content-hash migration while retaining citation sources for saved sets.

#### Scenario: First launch
- **WHEN** the application starts with an empty data directory and no source argument
- **THEN** it serves the workspace with an upload prompt and no sample document

#### Scenario: Upgrade an existing installation
- **WHEN** the old bundled sample exists in the document database
- **THEN** it is hidden from the file library while other uploads and saved study-set sources remain accessible

### Requirement: Browse complete documents in tabs
The workspace SHALL display available source and context files as tabs and SHALL let the learner browse every PDF page without selecting a generation range first.

#### Scenario: Explore a PDF
- **WHEN** a learner opens a PDF tab
- **THEN** all pages are reachable by continuous scrolling and page navigation

#### Scenario: Switch files
- **WHEN** the learner switches document tabs
- **THEN** the corresponding file preview appears and the previous document's reading position is retained

#### Scenario: Close and reopen a saved file
- **WHEN** the learner closes a saved file tab
- **THEN** its preview closes without deleting the file, and the file can be reopened from the library

#### Scenario: Close a file that has not been saved
- **WHEN** the learner closes an unfinished or failed upload tab
- **THEN** the workspace asks for confirmation before discarding the local file and cancelling its upload

### Requirement: Attach context files
The workspace SHALL accept PDFs, UTF-8 TXT/Markdown files, and supported images as additional generation context and make uploaded files available in document tabs.

#### Scenario: Add example problems
- **WHEN** the learner uploads a supported context file
- **THEN** its tab and preview become available and it can be selected for generation

### Requirement: Choose file ranges immediately before generation
The workspace SHALL offer source and context selection in a generation dialog. Each selected PDF SHALL support the whole document or an inclusive page range, including a single page. Text and image context SHALL be included in full.

#### Scenario: Choose pages five through seven
- **WHEN** the learner chooses page 5 as the range start and 7 as its end
- **THEN** only pages 5, 6, and 7 of that PDF are sent

#### Scenario: Choose only page seven
- **WHEN** both range endpoints are 7
- **THEN** only page 7 is sent

#### Scenario: Invalid range
- **WHEN** a range is reversed or exceeds the selected document
- **THEN** the workspace reports the invalid selection before sending a model request

### Requirement: Add a generation comment
The workspace SHALL accept an optional plain-text additional-context comment of up to 4,000 characters independently of attached files. It SHALL pass the comment to generation through an external prompt template while retaining primary-source restrictions, and SHALL preserve the comment when the resulting set is saved.

#### Scenario: Describe the desired exercise style
- **WHEN** the learner enters a comment and generates a set
- **THEN** the comment is included as learner preferences even when no context files are selected

### Requirement: Resize document and practice panes
The workspace SHALL support horizontal dragging of the divider between document and practice panes and SHALL adapt both contents to the resulting widths.

#### Scenario: Widen the source pane
- **WHEN** the learner drags the divider to the right
- **THEN** the source pane becomes wider, the practice pane becomes narrower, and the PDF rendering adapts

#### Scenario: Resize a PDF in Fit width mode
- **WHEN** the learner changes the pane width while reading a PDF
- **THEN** the same page and relative reading position remain in view and the previous canvas remains visible until its replacement is ready
- **AND** the final viewport update completes without requiring a click, hover, or scroll

### Requirement: Practice with physical flip cards
Flashcards SHALL display a front and back with a flip transition. The learner SHALL be able to flip using pointer or keyboard controls and navigate between cards.

#### Scenario: Reveal a card answer
- **WHEN** the learner flips a question card
- **THEN** the card turns to its answer side while preserving mathematical formatting

### Requirement: Navigate study sets and items through tabs
The workspace SHALL retain multiple generated sets in tabs and SHALL let the learner select individual cards or problems without replacing other sets.

#### Scenario: Generate another set
- **WHEN** generation completes while another set is open
- **THEN** a new set tab appears and the earlier set remains available

#### Scenario: Close a saved study set
- **WHEN** the learner closes a saved set tab
- **THEN** it closes without deleting the saved set, remains closed after reload, and can be reopened through Saved sets

#### Scenario: Save a draft before closing
- **WHEN** the learner closes an unsaved set and chooses Save and close
- **THEN** the workspace offers naming and closes the set only after a successful save

#### Scenario: Cancel or discard a draft close
- **WHEN** the learner closes an unsaved set
- **THEN** Cancel retains the draft and Close without saving explicitly discards it

#### Scenario: Saving fails
- **WHEN** saving a set before closing fails
- **THEN** the workspace reports the error and retains the open draft

### Requirement: Save study sets across restarts
The workspace SHALL explicitly save a study set's items, editable mathematics, source references, context selections, and generation metadata to persistent storage and SHALL restore saved sets after restart.

#### Scenario: Reopen a saved set
- **WHEN** the learner saves a set and reloads the workspace
- **THEN** the saved set is available with its original mathematical content and references

### Requirement: Download formatted study PDFs
The workspace SHALL export saved or unsaved study sets as downloadable PDFs containing their questions, answers, source references, and selectable mathematical text with formatted fractions, indices, and operators.

#### Scenario: Download a set
- **WHEN** the learner requests PDF download
- **THEN** a PDF is returned with all study items and their formatted mathematics rather than formula screenshots

#### Scenario: Mathematical source cannot be rendered
- **WHEN** an expression cannot be rendered for export
- **THEN** the workspace identifies the failure rather than exporting a silently incomplete formula
