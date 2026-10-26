# Design

## Context

The library currently lists documents and study sets independently. SQLite owns both records; saved canonical sets contain historical source snapshots. Generation loads separate prompt files and makes one provider call. See proposal.md for motivation.

## Goals / Non-Goals

Provide compatible organization and difficulty with the existing SQLite and server-served frontend. Folder/archive state belongs to the library, not historical study payloads. No OS filesystem paths, document-byte changes or extra model calls are needed.

## Decisions

- Shared owner-scoped folders use a parent ID tree (maximum eight levels) and normalized sibling-name uniqueness. Both library sections share the current folder. Breadcrumbs and folder tiles work on phones.
- Use a sidecar item-placement table keyed by owner, kind and item ID, with nullable folder IDs and active archive defaults. Canonical document/set records stay independent of organization. New set listings derive primary-document ID/name from existing JSON without modifying it. Moves and archives update only metadata. Saves preserve metadata on conflict; annotated-copy updates preserve its organization.
- Root study groups are virtual primary-source groups; they do not move documents or create duplicate records. Custom folder views group their contained study sets the same way. Archive lists archived items across the tree and shows their location.
- Folder removal moves immediate items and child folders to its parent in a transaction after confirmation. Colliding sibling names block the operation rather than renaming content silently.
- Add difficulty to request and StudySet with default 3. A separate difficulty prompt maps levels to challenge bands and requires progression inside each band. All writing guidance stays in prompt files.
- Native radio inputs styled as five compact choices keep keyboard and touch support. Clear level labels and a live short description explain the selection.
- Per-item menus expose Move, Archive/Restore and existing confirmed Delete, avoiding button clutter. A destination dialog supports the same operations on mobile; desktop folder drop targets offer an additional route.

## Risks / Trade-offs

- Longer solutions increase output latency → retain one call and concise card answers; increase output allowance only to accommodate complete responses.
- Difficulty and explanation quality depend on model reasoning → explicit reusable guidance, deterministic prompt tests and source fidelity requirements; no promise of mathematically verified answers.
- Concurrent moves/deletes → transactional destination validation, clear errors and reload; ownership checked at every boundary.
- Larger trees → depth and folder-count bounds, stable ordering and no recursive browser rendering outside the visible folder.

## Migration Plan

Add sidecar tables idempotently at startup. Historical rows remain at root and active. New readers accept missing difficulty as 3. Keep frozen fixtures unchanged. Existing code can ignore organization columns; older readers need not accept newly written set fields. Deploy with the existing workflow after API/compatibility and UI checks.
