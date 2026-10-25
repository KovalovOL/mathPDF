# Spec Delta

## Purpose

Create varied study material grounded in the selected PDF, with progressive learning goals and formulas that the application can typeset correctly.

## ADDED Requirements

### Requirement: Flashcard answers appear only after reveal
Flashcard fronts SHALL show only a self-contained recall question without answer hints. Titles, answer formulas, explanations and citations SHALL appear only on the back. External prompts SHALL enforce this separation, without another provider request. Hidden faces SHALL be inaccessible to assistive technology and keyboard focus.

#### Scenario: Recall a vector definition
- **WHEN** a card asks which two properties define a vector
- **THEN** the front displays that question without the definition formula or a source link
- **AND** flipping reveals the formula, explanation, title and citation

#### Scenario: Reopen or export an older flashcard
- **WHEN** an older card includes its answer formula in the question array
- **THEN** the workspace and exported question section omit that formula and the item title
- **AND** the answer side or section retains the formula, citation and variant explanation

### Requirement: Single-request progressive learning sequence
Generation SHALL request the complete set of distinct source-grounded items in one provider request, ordered in increasing intended difficulty. It SHALL NOT make separate planning, batching, repair, or automatic retry requests. Difficulty remains a model assessment.

#### Scenario: Generate a complete set
- **WHEN** a reader requests flashcards or problems
- **THEN** the provider receives exactly one request for the entire requested count
- **AND** the prompt asks for varied reasoning and an easier-to-harder sequence

### Requirement: Varied questions and exact counts
Successful generation SHALL return exactly the requested number of items and SHALL reject exact repeated questions. Invalid, incomplete, insufficient-source, or short responses SHALL terminate with an explicit failure and SHALL NOT trigger another model request or return a partial successful set.

#### Scenario: Provider repeats or omits an item
- **WHEN** a returned set contains an exact repeated question or has the wrong count
- **THEN** generation fails explicitly without an automatic model retry

### Requirement: Best-effort mathematical formatting
Formula-writing instructions SHALL remain in a separate English guide. The UI and PDF export SHALL typeset supported TeX locally and preserve unsupported TeX as readable plain text. Bare TeX in prose, unsupported commands, or unavailable renderer assets SHALL NOT cause generation to fail or discard the complete set. Generation SHALL NOT start a validation browser or make model repair calls. Exact counts and owner/source validation remain enforced.

#### Scenario: Provider returns a formula in prose
- **WHEN** a complete set includes an unformatted or unsupported mathematical expression
- **THEN** the complete requested set remains usable and saveable
- **AND** that expression is formatted locally when possible, otherwise displayed safely as raw text
- **AND** no additional provider call is made

#### Scenario: Export includes an unsupported formula
- **WHEN** a saved or unsaved set includes unsupported TeX
- **THEN** PDF export preserves it as readable raw text rather than rejecting the whole export

### Requirement: Existing study material remains readable
Existing saved sets SHALL remain readable without newly required planning fields. Unambiguous standalone TeX lines in old prose SHALL be typeset without treating ordinary English paragraphs as formulas.

#### Scenario: Open an older set
- **WHEN** a saved item lacks a learning goal identifier
- **THEN** it remains readable and exportable

### Requirement: Bounded generation progress
The workspace SHALL run generation through short owner-scoped job requests, display the actual phase and accepted count, and terminate waiting on completion, failure, cancellation, or deadline. Restarted or expired jobs SHALL produce an actionable interruption message.

#### Scenario: Generation takes several minutes
- **WHEN** generation is still running
- **THEN** short status requests show its phase and accepted count without holding one browser request open for the whole generation
- **AND** the learner can cancel it

#### Scenario: Another account requests a job
- **WHEN** an account requests a job belonging to another account
- **THEN** the service returns the same not-found result used for an unknown job

### Requirement: Diagnosable generation requests
Generation requests SHALL carry a correlation identifier through HTTP, jobs and provider logs. API failures SHALL identify the HTTP status and correlation identifier. Unreadable responses SHALL report their content type and redirect state without logging response bodies, credentials, source content or OAuth query parameters.

#### Scenario: Browser receives an unexpected HTML response
- **WHEN** an API request receives HTML instead of JSON
- **THEN** the browser displays diagnostic status and a reference identifier
- **AND** it submits a bounded owner-authenticated diagnostic event without the response body

#### Scenario: Unexpected server exception
- **WHEN** an API handler fails unexpectedly before its response starts
- **THEN** it returns a JSON error with a reference identifier and records sanitized stack locations
