# Spec Delta

## Purpose

Let readers select digital PDF text and follow study citations back to a visible source fragment without losing their place during resizing.

## ADDED Requirements

### Requirement: Selectable document text
The reader SHALL allow text selection and copying from digital PDFs while keeping the text layer aligned with the displayed page at supported zoom levels.

#### Scenario: Select text after resizing
- **WHEN** a reader resizes the PDF pane in fit-width mode
- **THEN** visible text remains selectable and aligned with the page
- **AND** resizing preserves the reading position without a blank page flash

### Requirement: Animated source navigation
Following a source citation SHALL quickly animate the reader to its page or matched fragment. Readers requesting reduced motion SHALL receive an immediate transition.

#### Scenario: Navigate to a distant source
- **WHEN** a reader follows a citation to another page
- **THEN** the PDF scrolls to that source using a brief animation
- **AND** direct user scrolling can interrupt the animation

### Requirement: Honest source fragment highlighting
The reader SHALL temporarily highlight a source quotation only when it matches a unique text fragment on the cited page. Missing or ambiguous quotations SHALL fall back to page navigation without claiming an exact line match.

#### Scenario: Quotation matches uniquely
- **WHEN** a citation quotation uniquely matches text on its page
- **THEN** the matched fragment is brought into view and highlighted temporarily

#### Scenario: Quotation cannot be located
- **WHEN** a quotation is absent, ambiguous, or differs from extracted PDF text
- **THEN** the reader navigates to the cited page without highlighting an invented line
