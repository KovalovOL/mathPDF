## Purpose

Deliver the requested number of source-grounded study items with reliable validation and visible generation feedback.

## ADDED Requirements

### Requirement: Exact requested item count
The system SHALL accept 1–50 requested flashcards or problems and return successful generation only with exactly that count of validated items. Missing items SHALL be generated automatically within bounded attempts. Exact repeated questions SHALL NOT be used to fill the count.

#### Scenario: Fifteen flashcards
- **WHEN** the learner requests 15 flashcards and generation succeeds
- **THEN** the returned workspace set contains exactly 15 flashcards

#### Scenario: Short first response
- **WHEN** a provider response contains fewer valid items than requested
- **THEN** the system requests missing replacements before returning success

### Requirement: Formula and source validation
Every accepted item SHALL include a source-cited mathematical block, and flashcards SHALL include one on the question face. Invalid items SHALL be replaced automatically without discarding accepted items. All LLM instructions SHALL live in separate prompt files.

#### Scenario: Missing formula
- **WHEN** a candidate omits its required mathematical block
- **THEN** it is rejected and a replacement is requested rather than displaying the internal provider-validation error

### Requirement: Honest bounded failure
The system SHALL stop at a finite request or time limit, preserve source constraints, and return an actionable error if it cannot complete the requested set. It SHALL support an explicit insufficient-source response and SHALL NOT return a successful partial set or fabricate source formulas to satisfy the count.

#### Scenario: Insufficient source
- **WHEN** the selected pages cannot support the requested material
- **THEN** no partial set is opened and the user is asked to choose more pages or fewer items

### Requirement: Generation waiting feedback
The workspace SHALL show an animated, accessible waiting indicator with the requested item count while generation is running. It SHALL respect reduced-motion preferences, avoid invented progress percentages, and restore controls and remove the indicator after success or failure.

#### Scenario: Generation fails
- **WHEN** an active generation ends with an error
- **THEN** the loading state ends, existing study sets remain usable, and generation can be started again
