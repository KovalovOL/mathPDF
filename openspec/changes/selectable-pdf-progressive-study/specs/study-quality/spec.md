# Spec Delta

## Purpose

Create varied study material grounded in the selected PDF, with progressive learning goals and formulas that the application can typeset correctly.

## ADDED Requirements

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

### Requirement: Guided renderable mathematical output
All formula-writing instructions SHALL live in a detailed separate English prompt file loaded into the single generation request. The guide SHALL cover text/math boundaries, JSON/TeX escaping, supported notation/environments, source fidelity, citations, and intentional variants. New formulas SHALL pass the same strict renderer used by the UI, in a local validation pass without model repair calls.

#### Scenario: Formula contains unsupported syntax
- **WHEN** a returned formula fails mathematical rendering
- **THEN** the job fails explicitly without sending a repair request

#### Scenario: Validation browser has an operational fault
- **WHEN** the renderer cannot render a known-valid expression during startup
- **THEN** generation fails before any provider request
- **AND** the validation browser uses standards mode, matching the UI and export

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
