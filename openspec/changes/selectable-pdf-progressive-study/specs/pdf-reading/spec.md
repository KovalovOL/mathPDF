# Spec Delta

## Purpose

Let readers select digital PDF text and follow study citations back to the original source page without losing their place during resizing.

## ADDED Requirements

### Requirement: Selectable document text
The reader SHALL allow text selection and copying from digital PDFs while keeping the text layer aligned with the displayed page at supported zoom levels.

#### Scenario: Select text after resizing
- **WHEN** a reader resizes the PDF pane in fit-width mode
- **THEN** visible text remains selectable and aligned with the page
- **AND** resizing preserves the reading position without a blank page flash

### Requirement: Animated source navigation
Following a source citation SHALL quickly animate the reader to its original page. Readers requesting reduced motion SHALL receive an immediate transition. Citation navigation SHALL NOT locate or highlight individual lines or quotations.

#### Scenario: Navigate to a distant source
- **WHEN** a reader follows a citation to another page
- **THEN** the PDF scrolls to that source using a brief animation
- **AND** direct user scrolling can interrupt the animation
