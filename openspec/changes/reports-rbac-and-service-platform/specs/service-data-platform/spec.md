## Purpose

Run separately managed services and migrate existing personal libraries without losing durable data.

## ADDED Requirements

### Requirement: Explicit services and private persistence
Compose SHALL define distinct app, PostgreSQL, Garage, reports and admin services with persistent storage and existing HTTPS routing. Database/object-store endpoints SHALL remain private. Bootstrap SHALL retain secrets across releases without exposing them in logs or version control.

#### Scenario: Container replacement
- **WHEN** app, reports or admin containers are rebuilt
- **THEN** database records, report queues, object bytes and configuration secrets survive

### Requirement: Verified non-destructive migration
Migration SHALL retain a consistent SQLite backup and all original document bytes; preserve users, session hashes, IDs, canonical study JSON, annotations, folders and archive placement; verify counts/content hashes; and record atomic completion. Unsupported data or mismatches SHALL stop deployment rather than discard data. Re-running a completed migration SHALL NOT overwrite newer production records.

#### Scenario: Interrupted copy
- **WHEN** migration fails before verification completes
- **THEN** app cutover is blocked, the source remains intact and the migration can be retried

### Requirement: Historical readability
Every previously supported study payload and draft SHALL remain readable after migration without regeneration or content reinterpretation.

#### Scenario: Legacy saved set
- **WHEN** a versionless saved set is transferred to PostgreSQL
- **THEN** its persisted JSON and references are preserved and the current reader opens it using compatible defaults
