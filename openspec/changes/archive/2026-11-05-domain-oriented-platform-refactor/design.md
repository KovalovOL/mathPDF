# Design

## Context

See `proposal.md` for motivation and scope. Inspection on 5 November 2026 found:

- 32 Python modules in `formula_lab/`. The main `create_app` factory spans 428 physical lines and the admin/report `create_service` factory 126 lines; both register routes through nested closures.
- `Workspace` owns schema initialization, document validation/storage, annotation writes, study persistence, identity lookup, renaming and deletion. `Library`, `Reviews`, `Usage` and `Reports` receive this concrete object and issue SQL themselves.
- `study.py` mixes persisted Pydantic contracts, provider ports, prompt loading, selected-page preparation, validation and generation orchestration. `providers.py` mixes OpenAI response schemas, transport, usage accounting and canonical expansion.
- Browser code includes ES modules and global `window.MathPDF*` APIs. `app.js`, `home.js` and the PDF viewer hold multiple kinds of state. Assets, print templates and prompts are resolved relative to the Python package.
- `pdf_export.py` loads browser print assets from the same package and intercepts browser requests. Relocating static files alone would break export. `web_assets.py` hashes nearby Python, prompt and frontend files into a build identity.
- JSON logging already exists in `diagnostics.py`; it provides request/job IDs, safe exception identity and bounded UI context. The refactor must preserve this behavior and improve its ownership/configuration.
- The existing Compose stack has app/admin/reports, PostgreSQL and Garage services plus one-shot bootstrap/migration jobs. All application processes use one Python image. Public traffic currently enters the app service.
- Existing tests reference `formula_lab` and filesystem asset paths directly. A read-only Python AST inventory found 26 function definitions exceeding 50 physical lines across production and tests, before expanding compressed statements. JavaScript requires its own parser-based inventory.

The owner confirmed separate frontend/backend applications and containers, communicating over HTTP at the existing public origin. Historical persisted formats and browser drafts must remain readable. Historical fixture bytes must remain unchanged.

## Goals / Non-Goals

**Goals:** Independent source/build/runtime ownership, explicit domain boundaries, small functions, object-oriented application services, declared public contracts, cohesive JSON logging and non-destructive transition.

**Non-Goals:** Product redesign, a new frontend framework, changed prompts or provider behavior, new generation stages, changing database/storage engines, renaming persisted fields or cache keys, or changing customer-facing endpoint semantics. No deployment is implied by completing this planning workflow.

## Decisions

### 1. Independent applications with a same-origin gateway

Target structure:

```text
front/
  app/
    pages/
    features/
      account/
      library/
      workspace/
      documents/
      annotations/
      study/
      reports/
      administration/
    core/
      http/
      browser-storage/
      observability/
    rendering/
      math/
      pdf/
      print/
    assets/
  tests/
  scripts/
  infrastructure/
    nginx.conf
  package.json
  package-lock.json
  Dockerfile
back/
  app/
    identity/
    documents/
    annotations/
    study/
    generation/
    library/
    reviews/
    usage/
    reports/
    formula_extraction/
    application/
      use_cases/
    core/
      contracts/
      errors/
      observability/
      settings/
    infrastructure/
      database/
      object_storage/
      providers/
      export/
      migrations/
    bootstrap/
      api.py
      administration.py
      reports.py
      container.py
      cli.py
  tests/
  pyproject.toml
  uv.lock
  Dockerfile
infrastructure/
  compose/
  observability/
contracts/
  http/
tests/
  fixtures/study-sets/  # Frozen bytes; retained at the historical location.
  integration/         # Cross-application HTTP checks, not implementation imports.
docker-compose.yaml
```

Names inside each domain communicate business ownership. Each applicable domain has `models.py`, `ports.py`, `service.py`, `handler.py`, and `repositories/`; large domains may use directories instead of oversized single files. Do not manufacture empty layers.

The frontend image builds only frontend source and dependencies. The backend image builds only backend source and dependencies; neither imports or mounts the other's source directory. Compose networks connect them over HTTP. PostgreSQL and Garage remain private backend dependencies.

A frontend gateway serves assets and forwards `/api/*`, OAuth and logout requests to the appropriate backend service. Preserve existing public paths, cookie names/attributes, trusted origin validation, account-change behavior, safe redirects, security headers and authenticated/admin HTML access. Implement an explicit internal authorization contract for the gateway, including the requested original route and role checks; clients cannot supply trusted gateway metadata through public headers. Backend APIs independently enforce authentication, authorization, CSRF/origin and owner scoping. Admin/report APIs remain separate private services. Do not expose the container network or Docker socket.

A development gateway mirrors production paths at one local origin, so cookies and origin checks do not depend on permissive CORS. Independent frontend development can use an explicit mocked HTTP contract. A directory-only move or a backend static-file mount does not meet the isolation requirement.

### 2. Domain ownership and dependencies

| Domain | Owns | Existing sources |
| --- | --- | --- |
| identity | Users, roles, OAuth flows, sessions, owner/admin policies | auth.py, roles.py, identity parts of workspace/platform_services |
| documents | File metadata, upload validation, private binaries | document parts of workspace.py |
| annotations | Vector marks, revisions, one edited copy per original, PDF overlay | annotations.py, annotation parts of workspace.py |
| study | Canonical blocks/sets, compatibility reader, content rules, set persistence | study.py contracts/validation, set parts of workspace.py |
| generation | Requests, preparation, jobs, prompts, provider port and output adaptation | generation_jobs.py, study.py preparation/generation, providers.py |
| library | Folders, placements, archives, organization projections | library.py |
| reviews | Review rounds, answers, scores and historical fingerprints | reviews.py |
| usage | Provider attempts, token allowance, reservations, tariffs and analytics | usage.py, quotas.py |
| reports | Incident records, snapshots, retention, triage and bundles | reports.py, report_summary.py, reporting parts of request_reports.py |
| formula_extraction | Offline source glyph/formula extraction and variants | models.py, extract.py, fonts.py, store.py, variants.py |

Repositories own SQL, row mapping and owner-scoped persistence. Services own domain rules and operate on declared repository ports. HTTP handlers translate request/response/error contracts and invoke a domain service or application use case. Domain models, policies, ports and services cannot import FastAPI, provider SDKs, database drivers, environment lookups or browser processes. Domain-local repository adapters may depend on infrastructure database contracts; HTTP handlers remain delivery adapters. Dependencies point inward toward models and ports. Replace domain-raised `HTTPException` (for example review conflicts) with typed domain errors mapped at the HTTP edge.

Concrete dependencies are assembled at a composition root. Domain ports are narrow Python `Protocol`/ABC contracts; configuration and dependencies enter constructors. Application code depends on ports, and infrastructure implements them. Explicitly type public methods, inputs, outputs and errors. Export supported entry points through package `__all__`; underscore implementation fields/helpers and avoid service locators, dynamic `setattr` APIs or public mutable service registries. Immutable DTOs/value objects express invariants; aggregates own their updates.

Do not replace `Workspace` with another all-purpose service, move SQL to a class named Service, or split one god object across mixins. Temporary legacy import facades may delegate during incremental migration, but final application code must use domain contracts and no longer depend on the flat package.

### 3. One cross-domain use case per file

Use-case classes expose an explicitly typed `execute` method. File names describe the operation; helpers supporting that one operation may stay in the same file. Separate files include at least:

- `generate_study.py`: authorized source selection, preparation, allowance/attempt coordination, one provider request, canonical result and reporting.
- `start_generation.py`, `cancel_generation.py`: job lifecycle and quota preconditions, preserving existing in-process lock semantics.
- `save_study_set.py`, `export_study_set.py`: source ownership, legacy-compatible validation, persistence or printing.
- `start_review.py`: saved/unsaved set authorization and existing-round identity.
- `save_document_annotations.py`: original/copy authorization, expected revision, overlay storage and atomic revision write.
- `preview_document_deletion.py`, `delete_document.py`: primary-source cascading, annotated copies, context detachment and binary retention/cleanup.
- `rename_library_item.py`: document/set naming and expected-name concurrency.
- `get_library_snapshot.py`: document/set/folder projection without SQL JSONB conversion of canonical payloads.
- `record_incident.py`, `collect_report_bundle.py`: reports, identity, retained source versions and diagnostic context.
- `change_user_role.py`, `change_generation_limit.py`, `get_admin_dashboard.py`: authorization and cross-domain administrative coordination.

Add a separate file for any additional cross-domain flow discovered during extraction. Do not route single-domain operations through a generic command bus just to add a layer.

A typed unit-of-work port coordinates one shared database transaction across repository adapters. Preserve current atomicity, owner-scoped queries, advisory locks, unique constraints, expected revision/name checks and rollback behavior. Blob writes and database commits are not a distributed transaction: keep verified object writes, cleanup-after-commit and safe orphan retention; do not introduce destructive compensation. Do not silently change generation admission or quota reservation semantics.

### 4. Frontend object boundaries and print contract

Retain the existing HTML/CSS and public paths while moving behavior into feature controllers, small views and state objects. Constructor-inject the HTTP client, document/set session, cache, annotation history and leave guard. Export public classes/functions explicitly from ES modules; use private fields for internal mutable state. Keep pure math parsing/rendering operations reusable under rendering and avoid forced stateful wrappers for simple value transformations.

Preserve account-scoped localStorage/IndexedDB names, object-store schemas, draft shapes, cache identity hashes, invalidation messages, iframe postMessage types, origin checks and annotation coordinate semantics. Migration is about code location, not user-state reset. Render old and new cards through the same projection and print renderer.

The frontend owns the print renderer/template and publishes a versioned private HTTP asset contract (manifest plus print assets). The backend export adapter fetches that version over the private service network and supplies study data only to its isolated local print browser. Retain URL/path allowlists, blocked external requests, font readiness, bounds and export deadlines. No frontend-source filesystem import, bind mount or duplicate renderer implementation is allowed. The contract identifies its version and asset digests so mismatched releases fail clearly without altering saved content. Backend-only unit work can inject an export port; full export requires the frontend HTTP service.

Frontend assets have their own content manifest; backend build identity hashes backend source/prompts. Responses and reports can record both build IDs. Update consumers that currently assume one build ID without breaking historical reports. Preserve HTTP cache/revalidation and private no-store behavior.

### 5. Function length and SOLID acceptance

Count physical lines from `def`/`async def` or the JavaScript function/arrow/method start through its last body line, including multiline signatures, docstrings, comments and blank lines inside the span. Check nested functions, callbacks, constructors, async methods and test functions as well. Exclude only vendored dependencies and generated artifacts; do not exclude a first-party module because it is difficult to split.

Use Python AST positions and a pinned JavaScript parser for the inventory. Apply readable formatting before evaluating the cap; do not compress statements or move huge executable strings into helpers simply to pass. Existing browser scripts embedded in Python tests also need JS analysis or extraction into frontend fixture modules. Aim for roughly 5–25 lines for ordinary behavior; 50 is a hard ceiling.

Split along responsibilities: upload type validation, transaction writes, annotation conflict checking, response adaptation, UI event binding and view updates. Extract cohesive collaborators with small public contracts, not helper chains with dozens of unrelated parameters. Review substitution, dependency inversion, narrow interfaces and invariant ownership in addition to the numerical limit; a line counter alone cannot establish SOLID.

### 6. Reusable core

`core/` may contain typed configuration, clock/identifier abstractions, HTTP-client primitives, bounded serialization, correlation context, logging contracts and technical errors. Physical adapters live under infrastructure. Formula rules, prompts, document ownership, quotas, review fingerprinting and deletion policy remain in their domains. Extract shared primitives when actual reuse exists or a concrete dependency warrants it; do not build speculative frameworks.

### 7. JSON logs and Loki

Keep one JSON object per stdout/stderr line, including exception events. Standard fields are `schema_version`, UTC `timestamp`, `level`, `event`, `message`, `service`, `environment`, `build`, `logger`, `request_id` and `job_id`; optional structured fields include normalized route, method, status, duration, error code/type/location and bounded UI identifiers. A fresh context is set and reset around each HTTP request and background job, including cancellation/error paths. Configure logging once per process, avoid duplicate propagation/handlers and integrate Uvicorn access/startup logs.

Preserve the existing sanitizer and safe exception-summary behavior. Never emit cookies, authorization headers, OAuth queries, API keys, source/PDF contents or full request/response payloads to logs. Full report snapshots remain in existing private report storage under current authorization.

Provide an optional Grafana Alloy configuration to consume Docker container logs, decode the Docker envelope and parse the inner application JSON. Keep the existing bounded Docker log rotation. Loki labels are limited to stable, bounded dimensions such as app/service/environment/level. Request IDs, users, file IDs/names, job IDs, raw routes and exception text remain JSON fields, not labels. Document LogQL queries for requests, errors and job IDs. Existing Loki credentials/endpoints are external configuration; the base Compose stack must work without an observability server. Do not expose an unauthenticated Loki service.

### 8. Verification and compatibility evidence

No validators or data migrations are added to the generation path. Preserve prompt contents/hashes, exact optional-field serialization and review fingerprints. Move tests with their application ownership; retain historical fixture bytes at `tests/fixtures/study-sets/`. Update filesystem references and replace implementation-coupled browser test setup with isolated HTTP/asset fixtures where needed.

Plan structural checks for import direction, frontend/backend isolation, declared public interfaces, function lengths and valid logging examples. Behavioral checks should cover every existing endpoint plus source/annotation/deletion semantics, sessions/admin boundaries, quota reservations, cancellation, old-set read/save/restart/render/export and browser drafts. Per current session instructions, do not add or run tests until the owner requests testing; record that verification boundary explicitly when implementation finishes. Read-only inventories are not a regression-suite result.

## Risks / Trade-offs

- [Gateway changes could weaken auth, role or CSRF behavior] → Mirror existing policy, strip spoofed forwarding headers, enforce API authorization independently and explicitly review same-origin flows.
- [Moving assets could break export or Safari cache/drafts] → Preserve URLs/state keys and use one versioned frontend-owned print contract.
- [A physical move could leave hidden coupling] → Separate build contexts and dependencies; no cross-app source mounts/imports, dynamic import aliases or blanket re-export facades in the final design.
- [Repository extraction could change transaction boundaries] → Introduce the unit-of-work port before splitting atomic writes; document each multi-repository transaction.
- [Schema refactoring could change normalized payloads/review identity] → Keep serialized DTO fields/defaults and historical fixture hashes; no opaque JSON-to-JSONB casts or normalization on read.
- [A strict line cap could encourage indirection] → Format first and require responsibility-focused extraction plus explicit ports; apply the cap to helpers and callbacks too.
- [Runtime route discovery is not a complete dependency map] → Audit decorators, thread offloading, contextvars, middleware ordering and background tasks directly.
- [More containers add operational coordination] → Add readiness checks, frontend/backend build IDs, documented local commands and coordinated releases while retaining private data paths.

## Migration Plan

1. Work in an isolated refactor branch. Preserve current local user changes and untracked PDF files. Inventory endpoints, source imports, persisted key names, fixture hashes and runtime commands.
2. Introduce domain contracts and composition, then extract repositories/services/use cases incrementally. Keep old HTTP behavior during extraction; use temporary facades only as a transition.
3. Move backend package/prompts/tooling and reconfigure its install/import/entry points. Retain environment names and data directory layout.
4. Move frontend source/tooling/tests and publish versioned assets/print contract. Replace backend static-file ownership with the HTTP export adapter and gateway.
5. Update Compose, Dockerfiles, workflow build/deploy commands, documentation and local graph generator paths. Health checks must distinguish frontend/app/admin/reports readiness. Do not run deployment during implementation by default.
6. Remove transitional application imports/facades after all first-party consumers move; preserve externally documented CLI entry points through explicit compatibility entry points where required.
7. Produce a reviewable diff, architecture/function inventories and remaining verification status. Run existing/new behavioral checks only after the owner requests testing.
8. Before a separately authorized production rollout, back up database/object manifests and retained SQLite files without altering source data. Use the new image set with the same persistent mounts. Verify old record hashes, binary digests and review fingerprints after rollout.
9. Roll back application images/gateway as one release if necessary; no data downgrade or reset is required because persistence formats remain unchanged. Legacy schema-reset branches must never be newly triggered by the move; reject unsupported/unowned storage non-destructively and require a separate explicit ownership migration.
