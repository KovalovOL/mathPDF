# Proposal

## Why

The current application combines HTTP composition, domain operations and persistence in a flat Python package, while browser assets and export templates are bundled into that same package. Future features need explicit boundaries and independently runnable frontend/backend applications without losing existing user data or changing generation behavior.

## What Changes

- Split the repository into `front/` and `back/`, each with its own application, dependencies, development commands, tests and Dockerfile. Run the frontend as a separate container on the existing public origin; connect to backend services over HTTP only, as confirmed by the owner.
- Organize the backend around identity, documents, annotations, study, generation, library, reviews, usage and reports domains. Separate domain models/policies, repository ports/adapters, services and HTTP handlers.
- Move cross-domain orchestration into application use cases, with one use-case implementation per file and constructor-injected ports.
- Replace large route factories and workspace objects with explicit composition roots and cohesive, encapsulated classes. Declare public APIs and repository/service contracts; keep implementation details private.
- Limit every first-party Python and JavaScript function, method and callback to 50 physical source lines, including tooling and tests. Exclude third-party/vendor/generated files; prohibit minification or compressed statements as a workaround.
- Restrict `core/` to reusable technical primitives and keep business behavior in its owning domain.
- Consolidate the existing JSON logging implementation into an explicit observability boundary with service/environment/build context and documented Loki ingestion/label rules.
- Preserve endpoint behavior, source fidelity, single-request generation, historical study formats, browser state, ownership rules, deletion confirmation, annotation revisions and review fingerprints.

## Capabilities

### New Capabilities

None. This change reorganizes implementation and delivery while preserving product behavior.

### Modified Capabilities

None. No product requirements or persisted formats change. This pure refactor declares `skip_specs: true`; architecture constraints and acceptance criteria are recorded in the design and tasks.

## Impact

All first-party Python/JavaScript modules, static asset paths, runtime packaging, HTTP composition, deployment configuration, scripts, test locations and documentation. PostgreSQL/Garage data paths and identifiers remain unchanged. Existing historical fixtures remain byte-for-byte unchanged. No production data access, paid generation, commit/push or deployment is part of the planning phase.
