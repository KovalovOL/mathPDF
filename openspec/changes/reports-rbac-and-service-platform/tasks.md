# Tasks

## 1. Persistent services and migration
- [x] 1.1 Add PostgreSQL and private object-storage adapters while preserving SQLite readers; verify parameterized queries, transactions, historical fixtures and storage hashes, and document configuration.
- [x] 1.2 Add persistent secret bootstrap, five-service Compose and verified SQLite/object migration with backup manifests; exercise empty, populated, retry and mismatch scenarios and document rollback.

## 2. Identity and AI usage
- [x] 2.1 Add verified owner bootstrap, role checks and audited owner-only grants; verify direct API denial, immediate revocation and preserved sessions, and document policy.
- [x] 2.2 Persist provider attempts, actual usage and effective tariff snapshots; verify failures, cached tokens and unknown prices, and document aggregation semantics.

## 3. Reports and administration
- [x] 3.1 Add durable report ingestion/worker, correlated server context and private bundles; verify deduplication, redaction, owner checks and retry after storage failure, and document collection limits.
- [x] 3.2 Add automatic frontend context and categorized manual feedback; verify 4xx/5xx, generation failures, non-recursion, active item context and mobile form behavior.
- [x] 3.3 Implement a separate protected admin service and dashboard for users/roles/reports/usage; verify role boundaries, day/week/month figures and safe rendering in browser/API checks.

## 4. Integration and cutover
- [x] 4.1 Run full compatibility/security and real PostgreSQL/Garage integration checks; record evidence and validate OpenSpec.
- [ ] 4.2 Review the concrete migration, deploy with a retained backup and verify all transferred records/object hashes, live services and owner access policy.
