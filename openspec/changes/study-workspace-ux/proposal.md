# Proposal

## Why

The current workbench forces page selection before document exploration and displays practice as a static list. Learners need a document workspace where they can browse sources, attach examples, choose ranges at generation time, study flip cards, and retain or export useful results.

## What Changes

- Browse complete PDFs in a continuous viewer with file tabs and responsive sizing.
- Upload PDF, TXT/Markdown, and image context files, with per-PDF ranges chosen in a generation dialog.
- Resize source and practice panes by dragging their divider horizontally.
- Present flashcards as physical cards with front/back flipping and keyboard navigation.
- Keep generation sets and individual items accessible through tabs.
- Save study sets to SQLite and download formatted PDFs with selectable mathematical text.
- Extend provider inputs and source references to include document identities while keeping prompts external.

## Capabilities

### New Capabilities

- `study-workspace`: Explore source documents and context, configure generation, practice in tabs, and retain or export study sets.

### Modified Capabilities

None. The broader `pdf-study-workspace` plan still owns Google identity and production Garage integration.

## Impact

- Replace the local workbench frontend and single-page PDF viewer.
- Add local document metadata/file handling and SQLite study-set persistence.
- Extend selected-page generation to multiple attachments without formula cataloging.
- Add Chromium-based PDF printing using the same local mathematical renderer and fonts as the UI.
- Keep the application local; authenticated multi-user storage remains a separate integration concern.
