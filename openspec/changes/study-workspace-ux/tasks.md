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

## 7. Library management, phone layout and browser caching

- [x] 7.1 Add confirmed owner-scoped file/set deletion with stale-impact protection, primary-only cascade and context detachment; verify ownership and legacy payload preservation.
- [x] 7.2 Add bounded account-scoped visual preview/page caching with content keys and deletion/sign-out invalidation, falling back safely when storage is unavailable.
- [x] 7.3 Add home deletion dialogs and collapsible sections with cached previews and account-specific preferences.
- [x] 7.4 Add full desktop source collapse and mobile study focus/pull-down restoration while preserving source navigation, resize anchors and ordinary answer scrolling.
- [x] 7.5 Integrate the ten-page cache into the source viewer and remove obsolete per-item generation progress text.
- [x] 7.6 Verify regression tests, local desktop/mobile behavior and cache reloads; update English documentation and deploy through the existing workflow.

## 8. Safari cache recovery and compact viewer controls

- [x] 8.1 Store derived images as byte buffers, read older Blob cache entries compatibly and recover unreadable images without displaying broken thumbnails; cover library and PDF page caches.
- [x] 8.2 Replace source show/hide text with accessible icons and place the expanded viewer's collapse control at the far left of its file bar.
- [ ] 8.3 Verify cache migration/recovery and desktop/mobile controls, update English documentation and deploy through the existing workflow.
