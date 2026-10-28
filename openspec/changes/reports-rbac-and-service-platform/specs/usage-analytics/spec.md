## Purpose

Give administrators per-user AI request, token and cost visibility based on measured provider usage.

## ADDED Requirements

### Requirement: Actual provider usage
The system SHALL persist every provider attempt with user, model, time, outcome, duration and available input/cached/output/reasoning token counts. Usage SHALL be retained even when a returned response fails content validation. Missing usage SHALL be explicitly unknown.

#### Scenario: Invalid generated set
- **WHEN** the provider returns token usage but invalid content
- **THEN** the attempt and token usage still appear in the administrator's metrics

### Requirement: Dashboard and cost estimates
Admin/owner SHALL see user counts, user details and per-user/model request/token/cost metrics over day/week/month windows with daily averages. Costs SHALL use effective versioned USD tariffs and cached-input discounts. Unknown historical usage or tariff SHALL be displayed as unavailable, not fabricated zero cost.

#### Scenario: Model without a tariff
- **WHEN** a model reports tokens but has no configured price
- **THEN** tokens and requests are counted and its unpriced cost is marked unavailable
