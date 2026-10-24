## Purpose

Keep uploaded documents and study material private to the account that created them throughout their lifecycle.

## ADDED Requirements

### Requirement: Owned document storage
The system SHALL assign each upload to the authenticated user and scope every document lookup, list, download, preview, and generation input by that owner. File deduplication SHALL be account-local. Cross-account identifiers SHALL return the same not-found response as missing identifiers.

#### Scenario: Identical uploads by two accounts
- **WHEN** two users upload identical bytes
- **THEN** each receives a separate owned document record and neither gains access to the other's record

#### Scenario: Foreign context document
- **WHEN** a user selects another account's document as a generation source or context
- **THEN** the server rejects the request before calling the LLM

### Requirement: Owned study sets
The system SHALL assign saved flashcards and problem sets to their authenticated owner. Lists, retrieval, updates, and exports SHALL enforce ownership, including all referenced documents. A caller SHALL NOT overwrite another user's saved set by submitting its identifier.

#### Scenario: Foreign saved-set identifier
- **WHEN** a caller requests or attempts to replace another user's saved set
- **THEN** the server returns not found and preserves the owner's data

### Requirement: Authorized legacy reset
The system SHALL delete pre-authentication uploaded files and saved sets during the one-time ownership migration, as requested by the user. It SHALL preserve owned data on later restarts and SHALL NOT delete repository sample source files outside managed upload storage.

#### Scenario: First ownership migration
- **WHEN** startup discovers the legacy unowned schema
- **THEN** managed legacy uploads and saved sets are removed before the private library becomes available

#### Scenario: Later startup
- **WHEN** startup discovers the owned schema
- **THEN** existing owned files and study sets remain available to their owners
