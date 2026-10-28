# Design

## Context

The app currently owns SQLite connections, local immutable document binaries, Google sessions and metadata-only diagnostic logging. Provider calls expose usage transiently but do not persist it. See proposal.md for motivation.

## Decisions

- PostgreSQL is the production system of record; a small connection adapter preserves existing parameterized SQL and row access while explicit helpers handle schema introspection, JSON extraction and deletion triggers. SQLite remains supported for historical/local fixtures. Existing write transactions retain their serialization requirements using transaction locks.
- Garage stores private document bytes and report bundles. The app materializes verified content-addressed local cache files for PDF parsing/rendering. No public buckets or presigned document access are introduced. Private service networks expose only the web app, reports routes and admin routes through existing Traefik.
- Five persistent services use one application image with dedicated commands. Bootstrap creates persistent random secrets locally (never logs them). A one-shot migration backs up SQLite and uploads referenced immutable files before transactional import and row/hash verification. It records completion atomically, retains source files/backups, rejects unsupported tables/schema and aborts cutover on mismatch. Existing session hashes, document IDs, study JSON, annotation data, folders and archive state survive.
- Reports persist an incident record plus a durable collection state. Background processing creates a private bundle with sanitized context, server trace and owner-checked source snapshots. Failures retry; the triggering operation never waits on report packaging. Front/server error reports correlate by request ID and merge context. Rate limits and bounded context apply with explicit truncation indicators, without recursive reports.
- Manual feedback offers bug, incorrect content, formatting, slow response, long answer and other. The frontend provides recent semantic actions and request payloads, active set/item/PDF page and viewport; it never records password fields, cookies, OAuth codes or API keys. Server identity is authoritative and client references are owner-checked.
- Roles live in a sidecar table and are resolved on every request. The verified configured owner email bootstraps owner privileges; users default free. Admin/owner can view administrative information/reports/usage, while only owner can assign free/premium/admin roles. Owner cannot be changed or self-demoted through APIs. Free/premium are stored access tiers; billing and quotas are a separate future policy.
- Provider observations record one attempt before HTTP dispatch and completion/usage before output validation. Persist model, request context, input/cached/output/reasoning tokens, duration, provider IDs and failure status. Missing usage remains unknown, not zero. Price versions apply at request time, including cached discounts; historical missing usage/cost is marked unavailable rather than fabricated. Dashboard windows use UTC calendar 1/7/30-day windows including today with zero-use days included in averages.
- All UI/documents/prompts remain English. Reports and role changes use existing Google sessions and same-origin mutation checks. Secrets are excluded recursively before report persistence, even when supplied by an untrusted client.

## Migration and rollback

Stop app writes for final SQLite backup/import. Bootstrap DB/Garage, migrate and verify, then start all web services. Keep legacy .formula-lab and backup manifests excluded from rsync deletion, alongside new persistent infrastructure. Rollback before accepting new writes may restart the previous image against the untouched SQLite directory; after accepting PostgreSQL writes, automatic rollback to stale SQLite is forbidden. New schema changes are additive and historical JSON is not normalized during transfer.

## Risks and trade-offs

Full diagnostic context includes private learner content: limit access to admin/owner, make collection visible in the feedback flow, and exclude credentials. Context is bounded and report packaging can lag during outages; durable retry makes that visible. A single VPS remains a single failure domain; persistent volumes and retained backups are required, not a promise of high availability. Model billing estimates depend on actual usage availability and the configured effective tariff, not invoice reconciliation.
