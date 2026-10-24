# Tasks

## 1. Documents and generation context

- [x] 1.1 Add managed PDF/text/image uploads and SQLite document metadata; document supported formats and inspect document identity, upload bounds, and persistent file paths.
- [x] 1.2 Extend generation requests, external prompts, provider attachments, and citation validation for per-file ranges; document the wire contract and inspect that only selected pages and enabled attachments enter the request.

## 2. Reading workspace

- [x] 2.1 Replace the single-page viewer with lazy continuous PDF browsing and file tabs; inspect scrolling, page navigation, source links, and preserved tab positions.
- [x] 2.2 Add a generation dialog with primary/context file selection and inclusive ranges; inspect range controls, preflight errors, and independent reading state.
- [x] 2.3 Add pointer and keyboard pane resizing with responsive PDF/card layout; inspect divider bounds and narrow-screen layout.

## 3. Practice and retention

- [x] 3.1 Add set/item tabs, front/back flashcards, keyboard flipping, and problem solutions; inspect accessible face state and navigation while retaining other sets.
- [x] 3.2 Add explicit SQLite study-set saves and restoration through the workspace; document persistence and inspect canonical set/source/context serialization and reload behavior.
- [x] 3.3 Add downloadable PDF export through the shared mathematical renderer and Chromium; document browser setup, print layout, font readiness, and visible rendering-error handling.

## 4. Integration documentation

- [x] 4.1 Update README and API/UX documentation, reconcile platform planning, and deliver the refreshed workspace preview; validate OpenSpec artifacts and record verification limits without claiming unrun automated tests or live model requests.

## 5. Workspace refinements

- [x] 5.1 Add a local browser favicon.
- [x] 5.2 Add accessible close controls to file tabs, saved-file reopening, and confirmation before closing unsaved uploads.
- [x] 5.3 Add an optional additional-context comment to the generation UI, request, external prompt, and saved study-set snapshot.
- [x] 5.4 Preserve PDF reading position and rendered canvases during Fit width resizing; update documentation and inspect the workspace manually.

## 6. Upload-first startup and study-set closing

- [x] 6.1 Remove required sample-PDF startup and container seeding; add empty-library upload guidance and retire the legacy seeded sample while preserving saved citations.
- [x] 6.2 Add study-set close controls, save/discard/cancel handling for drafts, saved-set reopening, and persisted open-tab state.
- [x] 6.3 Update documentation, manually inspect the revised workspace, and validate artifacts before the requested commit and push.
