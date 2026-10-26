# Proposal

## Why

Learners need explanations that teach the reasoning, control over study difficulty, and an organized personal library as their collection grows.

## What Changes

- Explain answers clearly, with compact flashcard backs and complete worked problem solutions.
- Add a five-level difficulty selector while retaining easier-to-harder progression within each requested band and one provider request.
- Add shared nested personal folders, moving files/sets, and reversible item archiving, with independent Files and Study sets sections.
- Group study sets by their primary source document within their chosen folder.
- Preserve historical persisted formats through additive defaults and independent organization metadata.

## Capabilities

### New Capabilities

- `study-difficulty`: Requested difficulty bands, answer guidance and compatible persistence.
- `library-organization`: Owner-scoped shared folders, source grouping, moving and archiving.

### Modified Capabilities

None. The main specification inventory is currently empty.

## Impact

SQLite storage, library APIs and home UI, generation request/response defaults, separate prompt files, generation dialog, documentation and regression coverage. No new runtime dependencies or provider round trips.
