# Spec Delta

## Purpose

Provides editable rendering of source-linked LLM mathematical output and optional PDF layout inspection before integration into the study platform.

## ADDED Requirements

### Requirement: Extract presentation records with source references
The prototype SHALL extract selectable text, source font information, layout, and source page locations from supported digital PDF pages into serializable formula presentation records.

#### Scenario: Extract a supported page
- **WHEN** a user opens a supported page of the supplied PDF
- **THEN** the prototype offers formula candidates and retains the original document, page, and coordinates for each selection

### Requirement: Render mathematical content as HTML text
The prototype SHALL render supported formula records as HTML text with source-derived fonts, positions, and mathematical rules. It SHALL NOT use screenshots, canvas crops, or SVG glyph paths as formula content.

#### Scenario: Display a fraction or indexed expression
- **WHEN** a supported formula containing a fraction or indices is selected
- **THEN** the mathematical glyphs are selectable HTML text and their source layout is retained

### Requirement: Apply traceable sign changes
The prototype SHALL let a user change a supported plus or minus text node into a separately stored variant while preserving the original record and the unchanged nodes.

#### Scenario: Replace a plus sign with a minus sign
- **WHEN** a user changes a selected plus sign whose replacement glyph is available
- **THEN** a variant records the original formula identifier, target node, and replacement while the source formula remains unchanged

#### Scenario: Replacement is unsupported
- **WHEN** a requested replacement glyph cannot be represented using available source fonts
- **THEN** the prototype reports the limitation instead of silently selecting a different font

### Requirement: Review source fidelity explicitly
The prototype SHALL show the original PDF alongside the HTML formula, expose unsupported cases, and keep extraction results unverified until a user records a review. A user review SHALL NOT be described as automated proof of universal fidelity.

#### Scenario: Compare and review a formula
- **WHEN** a user reviews a rendered formula against its PDF source
- **THEN** the prototype can persist the review state and notes with that formula

### Requirement: Preserve explicitly saved diagnostic records
The prototype SHALL preserve explicitly saved diagnostic formula selections, variants, references, and review notes. Page inspection and generation SHALL NOT require or automatically create an exhaustive formula catalog.

#### Scenario: Restart and export
- **WHEN** the workbench is restarted after a formula variant has been saved
- **THEN** the variant and its source lineage remain available and can be exported as JSON

### Requirement: Render every mathematical response block
The prototype SHALL render every math block in a structured study response independently as editable mathematical text. It SHALL support multiple formulas from one page and within one item.

#### Scenario: Response contains several formulas from one page
- **WHEN** a response includes three formulas from the same PDF page
- **THEN** all three are rendered with editable source and references

#### Scenario: One expression is unsupported
- **WHEN** one formula contains unsupported mathematical markup
- **THEN** its error is displayed locally and other formulas stay visible

### Requirement: Display all optional page candidates
The prototype SHALL display all detected candidates when page inspection is opened, without requiring selection of one candidate or saving them.

#### Scenario: Inspect a page with several candidates
- **WHEN** a page has multiple detected formula candidates
- **THEN** each appears as a separate formula preview

### Requirement: Generate from complete selected PDF pages
The prototype SHALL accept selected complete digital PDF pages through a replaceable model-provider interface. Extracting all formulas or page text locally SHALL NOT be a prerequisite.

#### Scenario: Generate flashcards or problems
- **WHEN** a user selects valid PDF pages and a study mode
- **THEN** the provider receives those complete pages and returns structured question and answer blocks

### Requirement: Cite formulas used in study material
Each generated math block SHALL identify its original PDF page and MAY include a model-reported line range and source quote. Out-of-selection references SHALL be rejected. Unavailable line numbers SHALL remain absent.

#### Scenario: No reliable line reference
- **WHEN** the model cannot identify a reliable line range
- **THEN** the citation retains the page and omits the line range

### Requirement: Externalize every LLM instruction
All system messages and task instructions SHALL be loaded from separate version-controlled prompt files. Generation metadata SHALL retain their content hashes.

#### Scenario: Compose a provider request
- **WHEN** the service composes generation instructions
- **THEN** instruction text comes from prompt resources and their hashes accompany the result

### Requirement: Use a minimal English interface
All application labels, controls, statuses, errors, placeholders, and accessibility text SHALL be English. Purely decorative content SHALL be removed.

#### Scenario: Open the application
- **WHEN** a user opens the workbench
- **THEN** it exposes document, generation, rendering, and practice controls without a decorative hero or formula catalog
