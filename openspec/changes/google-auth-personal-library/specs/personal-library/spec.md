## Purpose

Provide an account home for finding personal documents and saved study sets and reopening the existing study workspace.

## ADDED Requirements

### Requirement: Personal home
The system SHALL serve the authenticated user's library at `/`, displaying their uploaded files, saved flashcards, saved problem sets, and account menu at the top right. It SHALL provide upload and download actions and an upload-first empty state. All interface text SHALL be English and match the workspace palette.

#### Scenario: Empty account
- **WHEN** a new user signs in
- **THEN** home offers file upload and shows no sample documents or other users' material

#### Scenario: Returning account
- **WHEN** a user returns with a valid session
- **THEN** home lists their persisted files and saved sets with useful type and count metadata

### Requirement: Workspace entry
The system SHALL open the existing reading and study interface at `/workspace` for an owned file or saved set selected from home. Selecting a saved set SHALL restore its source document and generated content. Existing tabs, page ranges, resizing, flashcard flipping, and export interactions SHALL remain available.

#### Scenario: Open saved set
- **WHEN** the user chooses a saved flashcard set on home
- **THEN** the workspace displays that set and its source PDF

### Requirement: Account-specific browser state
The system SHALL scope workspace preferences by authenticated account and handle expired API sessions by returning to login. Account changes SHALL NOT restore a previous user's document or study-set selection.

#### Scenario: Account switch
- **WHEN** a different account signs in in the same browser
- **THEN** its workspace uses only its own saved selections and authorized resources
