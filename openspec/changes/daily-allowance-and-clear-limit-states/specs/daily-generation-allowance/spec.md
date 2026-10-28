## Purpose

Provide daily free usage with understandable feedback.

## ADDED Requirements

### Requirement: Daily allowance windows
Free generation SHALL reset every 24 hours at midnight UTC and SHALL preserve historical configured values and usage records.

#### Scenario: Reset at midnight
- **WHEN** the next UTC day begins
- **THEN** the allowance is fully available and earlier actual and pending usage remains stored without counting against the new day

### Requirement: Clear allowance feedback
The UI SHALL label used and remaining percentages, show reset timing, and present a friendly recoverable state when generation cannot fit.

#### Scenario: Insufficient allowance
- **WHEN** dispatch rejects a request for insufficient remaining allowance
- **THEN** the user sees an accessible explanation and can adjust the preserved generation selection without a generic failure toast
