# Proposal

## Why

External testers need actionable automatic and manual reports, while the owner needs controlled administration and accurate AI usage/cost visibility. The deployment needs explicit service boundaries and durable database/object storage without losing existing accounts or study data.

## What Changes

- Add durable reports for API errors and manual categorized feedback, with user, request/response, recent actions, active content and immutable source snapshots; redact credentials and prevent recursive reporting.
- Replace the production SQLite backend with PostgreSQL as requested by the owner; retain SQLite compatibility for local/historical use and migrate all owned records and document bytes with backups and verification.
- Run app, PostgreSQL, private Garage object storage, reports and admin as distinct Compose services, with one-shot bootstrap/migration stages and existing Traefik HTTPS routing.
- Add free, premium, admin and owner roles. Bootstrap the verified owner email; only owner can grant/revoke admins. Protect all admin APIs server-side and audit changes.
- Record actual provider attempts and token usage, including failed outputs when usage exists, with model-specific effective price snapshots and daily/weekly/monthly user dashboards.

## Capabilities

### New Capabilities
- `incident-reporting`: Safe, contextual, durable automatic/manual incident reports and admin triage.
- `platform-rbac`: Owner identity, role enforcement and audited administration.
- `service-data-platform`: PostgreSQL/Garage service persistence and verified non-destructive migration.
- `usage-analytics`: Actual AI request/token tracking and transparent cost estimates.

### Modified Capabilities
None; existing main specification inventory is empty.

## Impact

Shared storage/database adapters, authentication, provider observations, HTTP diagnostics, report worker/service, dedicated admin service/UI, shared frontend request wrapper and feedback dialog, Compose/deployment, migrations, tests and English documentation. Historical saved formats and opaque sessions remain readable. No additional LLM calls.
