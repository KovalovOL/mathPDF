# Library folders and archive

The library uses one shared folder tree. Within each folder, **Files** and **Saved study sets** remain separate, collapsible sections. Study sets are grouped by their primary PDF, using its filename; context attachments do not affect grouping. Different PDFs with identical names remain separate groups.

Use **+ New folder**, folder tiles and breadcrumbs to navigate. Each **⋯** menu offers **Move** and **Archive**, or **Restore** in Archive. On desktop, drag a file, set or folder onto a folder tile or breadcrumb to move it. The Move dialog provides the same operation for touch and keyboard users. Folder menus also provide Rename and confirmed removal. Removing a folder moves its items and subfolders to its parent; it does not delete their content. A name collision asks the learner to rename or move the child folder first.

**Archive** shows all archived files and sets, with their saved folder paths. Archiving affects only the selected item and preserves its folder, source links, PDF bytes, annotations and study content. Restore returns it to its folder. Archived sources still open from existing sets. Explicit Delete retains the existing confirmation and primary-source cascade across both active and archived content; context-only sets survive.

Uploads from a folder are placed there. Historical and otherwise unassigned items appear at the library root, active. Moving a source does not implicitly move its sets; each can be organized independently.

## API

All routes require the current authenticated owner and the existing same-origin mutation checks.

- `GET /api/library` returns `folders`, `files` and `sets`, including archive/placement state. Existing `/api/documents` and `/api/study-sets` retain their complete owner-scoped listing behavior.
- `POST /api/library/folders` accepts `{ "name": "Algebra", "parent_id": null }`.
- `PATCH /api/library/folders/{id}` accepts a name and/or parent ID; explicit null moves to root.
- `PATCH /api/library/items/documents/{id}` and `/api/library/items/study-sets/{id}` accept a folder ID and/or boolean `archived`. An explicit null folder moves to root; omitted fields retain their values.
- `GET /api/library/folders/{id}/deletion` supplies a revision. `DELETE` on the folder requires that revision in `If-Match`; concurrent changes require review again.

Folder names are trimmed, case-insensitively unique among siblings and at most 100 characters. Trees support eight levels and 300 folders per account. Moves reject cycles and foreign destinations. Organization lives in additive SQLite sidecar tables and does not rewrite historical set JSON. Canonical saves preserve placement. Existing records do not require regeneration or format migration.
