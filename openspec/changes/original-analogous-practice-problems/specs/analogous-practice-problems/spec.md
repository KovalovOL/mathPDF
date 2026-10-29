# Spec Delta

## Purpose

Generate original analogous practice that transfers methods from selected lecture pages while distinguishing source material from generated inputs and reasoning.

## ADDED Requirements

### Requirement: Method-grounded original practice
Problem-generation instructions SHALL select a source-supported method and target skill before constructing a new statement. They SHALL exclude copies, paraphrases, renamed objects and numerical substitutions as sufficient novelty, while preserving essential conditions and source-supported prerequisites.

#### Scenario: General induction theorem
- **WHEN** selected pages teach an induction proof for all natural numbers
- **THEN** instructions require a new task using induction
- **AND** evaluating the original theorem at one number does not qualify as an analogous proof task

#### Scenario: Transfer a counting method
- **WHEN** selected pages teach the pigeonhole principle through one example
- **THEN** instructions require a new configuration with a valid pigeonhole argument
- **AND** changing only the original counts does not satisfy novelty

### Requirement: Honest mathematical provenance
New problem output SHALL distinguish literal source references, generated givens and derived steps. Generated expressions SHALL reference the selected primary pages as method support without claiming literal presence there. Literal quotes and true source-edit variants SHALL retain exact source notation.

#### Scenario: New problem with different structure
- **WHEN** a generated problem applies a source method without directly editing one source expression
- **THEN** no fictitious original expression is required
- **AND** the learner can identify its method-support page and generated origin in the workspace and PDF export

#### Scenario: Prose-only source method
- **WHEN** the method is explained without a printed formula
- **THEN** a page-only method reference is accepted
- **AND** generated givens do not become purported source formulas

### Requirement: Complete and focused tasks
Instructions SHALL require self-contained givens, a solution of the actual generated instance and justified essential steps. Selecting a method SHALL remain part of the task when the requested skill assesses that selection. Difficulty SHALL reflect reasoning rather than longer prose or larger constants.

#### Scenario: Method selection is assessed
- **WHEN** a problem asks the learner to choose a suitable proof method
- **THEN** its question does not reveal that method
- **AND** the answer explains the choice and completes the proof

### Requirement: Bounded novelty validation
New generation SHALL reject exact duplicate questions and explicit self-reported copied or numerical-only tasks before returning success. Validation SHALL NOT claim to prove semantic novelty from metadata. Semantic novelty and method fidelity SHALL also be assessed through a source-linked review corpus.

#### Scenario: Explicit substitution-only output
- **WHEN** new problem metadata declares only changed constants or renamed variables
- **THEN** the complete set fails with a clear quality error
- **AND** no partial success or automatic provider retry occurs

#### Scenario: Model incorrectly claims originality
- **WHEN** a copied problem incorrectly claims substantive novelty
- **THEN** passing metadata checks is not reported as verified semantic originality
- **AND** the evaluation rubric classifies the copy as a failure

### Requirement: Single-request generation and historical compatibility
Generation SHALL retain exactly one provider request and exact requested counts. New metadata SHALL use compatible defaults when reading older sets and drafts. Reading, saving and exporting old material SHALL preserve formulas, citations, variants and user content without applying new-generation novelty gates retroactively.

#### Scenario: Reopen an old numerical variant
- **WHEN** a learner opens a saved numerical variant created before this change
- **THEN** it remains readable, saveable and exportable with its original lineage
- **AND** no regeneration or destructive migration is required

#### Scenario: Source cannot support the requested set
- **WHEN** selected pages cannot support the requested number of original tasks at the chosen difficulty
- **THEN** generation reports insufficient source without silently substituting easier copied tasks
- **AND** no additional provider request is made
