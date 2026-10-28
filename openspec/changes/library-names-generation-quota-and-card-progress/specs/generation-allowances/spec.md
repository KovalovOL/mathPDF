## Purpose

Support library names, controlled generation and learner progress.

## ADDED Requirements

### Requirement: Enforced free allowance
Free generations SHALL use an administrator-configurable monthly token allowance with transactional reservations and actual input/output settlement. Ordinary users SHALL see percentages and reset timing.

#### Scenario: No remaining allowance
- **WHEN** a free account has exhausted its monthly allowance
- **THEN** generation is rejected before a provider call and the user sees the reset timing

#### Scenario: Actual provider usage
- **WHEN** a response is rejected by local content validation
- **THEN** its actual tokens still count against the allowance
