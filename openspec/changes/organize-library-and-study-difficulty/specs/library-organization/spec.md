## Purpose

Keep a personal library manageable through shared folders, primary-source study grouping and reversible archiving.

## ADDED Requirements

### Requirement: Shared personal folders
The library SHALL support owner-scoped nested folders, creation, renaming and moves while displaying Files and Study sets separately within the current folder. Root SHALL remain available. Invalid cycles and foreign destinations SHALL be rejected. Deleting a folder SHALL require confirmation and move its contents and children to its parent without deleting them.

#### Scenario: Move a file and set
- **WHEN** a learner moves a file and a set into one folder
- **THEN** both appear in their respective sections there, with existing IDs, citations and payloads intact after restart

### Requirement: Primary-source grouping
Study sets in the current folder SHALL be grouped by primary document ID with its filename as the group title. Additional context SHALL NOT determine grouping.

#### Scenario: Same names
- **WHEN** distinct primary documents have the same filename
- **THEN** their study sets remain separate groups

### Requirement: Reversible archive
The library SHALL allow individual files and sets to be archived and restored. Active listings SHALL hide archived items; Archive SHALL show them across folders with their saved folder location. Archiving SHALL NOT cascade or delete content, break citations or prevent opening an existing set. Restore SHALL retain the item's folder.

#### Scenario: Archive source only
- **WHEN** a primary document is archived
- **THEN** its sets remain active, their source remains readable, and the document can be restored to its folder

### Requirement: Compatible and isolated organization
Existing owned data SHALL start active at root without rewriting stored content. Organization writes SHALL be owner-scoped, and ordinary saves SHALL retain existing organization. Existing explicit primary-source deletion cascades SHALL include active and archived items.

#### Scenario: Historical set is moved
- **WHEN** a historical set is moved, archived, restored and saved again
- **THEN** its formulas, references and other supported content survive and its latest organization is preserved
