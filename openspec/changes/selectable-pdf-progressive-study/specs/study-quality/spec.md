# Spec Delta

## Purpose

Create varied study material grounded in the selected PDF, with progressive learning goals and formulas that the application can typeset correctly.

## ADDED Requirements

### Requirement: Progressive learning sequence
Generation SHALL plan distinct source-grounded learning goals in increasing intended difficulty before creating items. Returned items SHALL follow that plan across batches and repairs. Difficulty is a model assessment, not a proof of mathematical complexity.

#### Scenario: Generate a multi-batch set
- **WHEN** a reader requests more items than fit in one generation batch
- **THEN** every item fills its assigned learning goal
- **AND** the final order follows the whole-set progression rather than restarting at each batch

### Requirement: Varied questions
Generation SHALL instruct the provider to vary learning goals and reasoning activities, and SHALL reject exact or conservatively detected near-duplicate questions within the set. Rejected items SHALL be repaired within bounded attempts without silently reducing the requested count.

#### Scenario: Provider repeats an exercise
- **WHEN** a returned item repeats an accepted question with only superficial wording changes
- **THEN** it is rejected and its learning slot remains unfilled
- **AND** generation either completes the requested count or returns an actionable failure

### Requirement: Renderable mathematical output
Newly generated formulas SHALL pass the same strict mathematical renderer settings used by the application. Undelimited TeX commands in prose and obvious exercise prose placed in formula blocks SHALL be rejected for repair. Correctly delimited prose mathematics SHALL be accepted only after renderer validation.

#### Scenario: Provider places TeX in a text list
- **WHEN** a text block contains undelimited TeX commands
- **THEN** the item is rejected and the provider is instructed to use separate mathematical blocks

#### Scenario: Formula contains unsupported syntax
- **WHEN** a formula fails the application's mathematical renderer
- **THEN** the item is repaired or generation reports failure instead of presenting broken TeX

#### Scenario: Validation browser has an operational fault
- **WHEN** the renderer cannot render a known-valid expression during its startup self-check
- **THEN** generation fails before making provider requests instead of asking the model to repair valid formulas
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
