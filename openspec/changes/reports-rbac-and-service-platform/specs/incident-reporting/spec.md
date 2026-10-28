## Purpose

Let testers and administrators diagnose failures and content complaints using correlated private context.

## ADDED Requirements

### Requirement: Automatic correlated reports
Authenticated API 4xx/5xx failures SHALL create bounded durable reports with request identity, business payload, response/error, build and recent activity. Frontend and server reports for the same failure SHALL correlate without recursive reporting. Failed generation jobs SHALL remain reportable even when polling returns HTTP 200.

#### Scenario: API failure
- **WHEN** a signed-in tester receives a backend 400 or 500
- **THEN** a report is queued with the authoritative user and request context, and collection failure does not block the original response

### Requirement: Manual feedback and context
Users SHALL submit categorized feedback with a comment and active content/request/activity context. Reports SHALL collect owner-checked source versions and remain accessible to admin/owner for triage and private download. Missing/unavailable/truncated context SHALL be marked explicitly.

#### Scenario: Wrong formula feedback
- **WHEN** a learner reports incorrect content while viewing a card
- **THEN** the report retains the active set/item, relevant request, source pages/files and the learner's comment

### Requirement: Safe durable collection
Credentials, cookies, OAuth codes and password inputs SHALL be excluded from stored context. Report processing SHALL retry durably, deduplicate automatic incidents and enforce ingestion limits. Untrusted client content SHALL be safely rendered and SHALL NOT authorize access to another user's files.

#### Scenario: Injected reference
- **WHEN** feedback contains another account's document ID or a credential field
- **THEN** that document is excluded and the credential value is redacted
