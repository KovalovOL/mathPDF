## Purpose

Keep libraries visible and diagnostics and mobile study controls usable.

## ADDED Requirements

### Requirement: Compatible library projection
Library metadata SHALL be readable from all supported saved payloads without a JSONB conversion or content rewrite.

#### Scenario: Escaped NUL in a saved answer
- **WHEN** a valid stored study payload contains an escaped NUL
- **THEN** the owner's files and study sets remain visible and the saved payload is unchanged

### Requirement: Actionable diagnostics
Backend logs SHALL be structured JSON with safe error identities and correlated UI context, and reports SHALL show a concise human-readable summary before raw evidence.

#### Scenario: Request failure
- **WHEN** a library request fails after a frontend action
- **THEN** diagnostics identify the route, error type, user, screen, action and relevant entity without exposing credentials or document contents in logs

### Requirement: Compact mobile card controls
Cards SHALL flip by direct interaction, prevent accidental touch selection, and fit the screen with compact navigation and grading controls.

#### Scenario: Rate a card on a phone
- **WHEN** a user flips a card and rates the answer
- **THEN** no redundant Flip button or in-round progress bar consumes space and the page does not require horizontal scrolling
