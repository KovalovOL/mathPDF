# Spec Delta

## Purpose

Lets learners keep their mathematics notes in a private library and use selected pages as the source for study material.

## ADDED Requirements

### Requirement: User can upload a PDF to their library
The system SHALL let an authenticated user add a PDF document to that user's library.

#### Scenario: PDF is added successfully
- **WHEN** an authenticated user uploads a supported PDF
- **THEN** the system stores the document as belonging to that user and makes it available in that user's library

#### Scenario: Upload is not a supported PDF
- **WHEN** an authenticated user uploads a file that is not accepted as a PDF document
- **THEN** the system rejects the upload and reports that the document could not be added

### Requirement: User can preview and download a library PDF
The system SHALL let an authenticated user preview and download a PDF document in that user's library.

#### Scenario: User previews a library PDF
- **WHEN** an authenticated user opens a PDF they own
- **THEN** the system displays its pages in the web application

#### Scenario: User downloads a library PDF
- **WHEN** an authenticated user requests a download of a PDF they own
- **THEN** the system returns the original PDF file

### Requirement: User can select source pages
The system SHALL let an authenticated user select one or more pages from an owned PDF as the source for study-material generation.

#### Scenario: User selects a page range
- **WHEN** the user selects a valid page range in an owned PDF
- **THEN** the selection is associated with that PDF and can be used for generation

#### Scenario: User selects a page outside the document
- **WHEN** the user selects a page number that does not exist in the PDF
- **THEN** the system rejects the selection and identifies it as invalid

### Requirement: Reading precedes generation scope selection
The system SHALL let users browse complete documents in tabs and choose source/context PDF ranges immediately before generation. Reading position SHALL NOT restrict which document pages remain accessible.

#### Scenario: Browse before selecting a range
- **WHEN** a user explores a PDF and opens generation settings
- **THEN** the entire document remains readable and the user can choose an inclusive range or a single page independently

### Requirement: User can attach additional context
The system SHALL accept owned PDF, UTF-8 TXT/Markdown, and supported image files as generation context. Each PDF SHALL have an independent page selection; text and images SHALL be included in full.

#### Scenario: Add example problems
- **WHEN** a user attaches a supported example file
- **THEN** its preview tab becomes available and its selected content can accompany the primary source
