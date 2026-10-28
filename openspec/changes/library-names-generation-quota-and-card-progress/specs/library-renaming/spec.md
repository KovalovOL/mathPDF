## Purpose

Support library names, controlled generation and learner progress.

## ADDED Requirements

### Requirement: Compatible owned renaming
Users SHALL rename their own files and sets while IDs, source references, variants, metadata and stored formats remain intact.

#### Scenario: Rename a historical set
- **WHEN** its owner assigns a new name
- **THEN** only its name and modification timestamp change and historical payload fields remain readable
