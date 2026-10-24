# Spec Delta

## Purpose

Creates mathematics practice from complete selected note pages using editable mathematical text and references for formulas actually used in study material.

## ADDED Requirements

### Requirement: User can generate formula quiz cards
The system SHALL create formula flashcards from selected pages of an owned PDF, with a formula question and an answer explaining its meaning, purpose, and conditions when supported by those pages.

#### Scenario: Generate cards from selected pages
- **WHEN** a user requests formula flashcards for selected pages
- **THEN** the system returns grounded formula questions and explanatory answers

#### Scenario: Insufficient source material
- **WHEN** the selected pages do not support the requested answer
- **THEN** the system identifies the limitation instead of presenting unsupported claims

### Requirement: Generation accepts complete PDF pages
The system SHALL accept complete selected digital PDF pages as model input. Local extraction of all text or formulas and persistence of a formula catalog SHALL NOT be prerequisites.

#### Scenario: Generate without a formula inventory
- **WHEN** a user requests study material from valid digital PDF pages
- **THEN** the system passes those complete pages to its model provider with their original page mapping

### Requirement: Multiple formulas are supported
The system SHALL render every mathematical block included in generated material, including multiple formulas from one PDF page and multiple formulas within one item.

#### Scenario: Several formulas come from one page
- **WHEN** the generated set includes several formulas from one selected page
- **THEN** all of them are available as independent mathematical blocks rather than only one selected formula

### Requirement: Formula display is editable mathematical text
The system SHALL render formulas from editable mathematical source as HTML or MathML. PDF screenshots or crops SHALL NOT replace the study formula's mathematical representation.

#### Scenario: View a formula
- **WHEN** a user views a formula in a study item
- **THEN** it appears as formatted mathematical text with editable source

#### Scenario: Unsupported markup
- **WHEN** one formula cannot be rendered
- **THEN** the system identifies that formula's error and retains the other blocks

### Requirement: Source notation and formatting remain the fidelity target
The system SHALL preserve source notation and formatting for an unmodified formula. Rendering success or mathematical equivalence SHALL NOT be described as proof of faithful PDF transcription.

#### Scenario: Compare output with its source
- **WHEN** a rendered transcription has not been checked against the PDF
- **THEN** it remains identified as unchecked and the source page is available for comparison

#### Scenario: A fidelity difference is found
- **WHEN** a source formula has altered symbols, font variants, scripts, fractions, delimiters, alignment, spacing, or line breaks
- **THEN** the system supports correction and does not silently label the transcription as exact

### Requirement: Quiz variants preserve their source expression
A deliberate quiz variant SHALL retain its original expression, source citation, changed expression, and change description within the study material without requiring a separate formula catalog record.

#### Scenario: Quiz changes a sign
- **WHEN** a quiz deliberately changes a source sign
- **THEN** the source expression remains unchanged and the answer explains the intentional edit

#### Scenario: Learner previews a local edit
- **WHEN** the learner edits mathematical source
- **THEN** the preview preserves the received original for comparison

### Requirement: References belong to used formulas
The system SHALL retain document and original-page references for math blocks actually used in generated items. Optional line ranges SHALL remain model-reported and nullable. The system SHALL NOT require saving all formulas discovered in a PDF.

#### Scenario: Navigate to a source formula
- **WHEN** a user follows a formula's reference
- **THEN** the original document page is available for comparison

#### Scenario: Lines are unavailable
- **WHEN** a reliable line range cannot be identified
- **THEN** the page reference remains and no exact line number is invented

#### Scenario: Citation exceeds source scope
- **WHEN** generated content cites a page outside the selected source pages
- **THEN** the system rejects that response

### Requirement: User can generate and practice problems
The system SHALL generate mathematical problems grounded in selected pages and let the learner reveal an associated answer or solution. Unrelated invented formulas SHALL remain outside the permitted source scope.

#### Scenario: Practice a problem
- **WHEN** a learner opens a generated problem
- **THEN** its question appears before the associated answer is revealed

#### Scenario: Problem needs an unrelated formula
- **WHEN** a problem cannot be produced using source formulas or deliberate source-derived variations
- **THEN** the system reports that limitation

### Requirement: LLM instructions are external resources
All system prompts and task instructions SHALL come from separate version-controlled files. Generated material SHALL retain prompt identifiers and content hashes.

#### Scenario: Generate a set
- **WHEN** a provider request is composed
- **THEN** all instruction text comes from prompt resources and their hashes accompany the result

### Requirement: Interface copy is English and functional
The system SHALL use English for application copy and accessibility text and SHALL omit purely decorative content.

#### Scenario: Use generation and practice controls
- **WHEN** a learner opens a study workspace
- **THEN** English controls support document selection, generation, source comparison, editing, and practice

### Requirement: User can save and download generated sets
The system SHALL persist explicitly saved study sets with editable mathematical content and references and SHALL export saved or unsaved sets as PDFs with formatted mathematical text.

#### Scenario: Reopen saved material
- **WHEN** a user saves a set and returns later
- **THEN** the set remains available with its questions, answers, mathematics, and source/context references

#### Scenario: Download a generated set
- **WHEN** a user requests PDF export
- **THEN** the system returns formatted questions and answers with typeset formulas

### Requirement: Practice uses tabs and physical flashcards
The system SHALL retain multiple sets and items through tabs and SHALL present flashcards with front/back flipping. The document/practice divider SHALL support horizontal resizing.

#### Scenario: Flip a card
- **WHEN** a learner flips a question card
- **THEN** the answer appears on its reverse face with mathematical formatting retained
