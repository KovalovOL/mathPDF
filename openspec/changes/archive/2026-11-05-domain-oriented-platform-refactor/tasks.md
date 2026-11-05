# Tasks

Implementation and local acceptance are complete on `codex/domain-oriented-platform-refactor`. This change skips product-spec deltas because externally observable behavior and persisted formats remain unchanged. The owner explicitly authorized focused and full local tests plus disposable image builds; no live AI calls or production deployment were performed.

## 1. Baseline and architectural boundaries

- [x] 1.1 Create an isolated refactor branch, preserve unrelated working-tree changes/PDFs and inventory current HTTP routes, entry points, environment names and fixture hashes; verify a baseline manifest is delivered without changing runtime data.
- [x] 1.2 Create the `front/`, `back/`, contracts and infrastructure ownership skeleton from design.md and document dependency directions; verify each existing first-party source file has a destination and an owning domain/feature.
- [x] 1.3 Add a readable function-length inventory for first-party Python/JavaScript, including callbacks, constructors and embedded browser fixtures, using AST positions and pinned formatting/parser versions; verify it reports file/line/name/span, excludes only documented third-party/generated paths and enforces 50 physical lines after formatting.

## 2. Backend core, repositories and composition

- [x] 2.1 Extract typed configuration, technical errors, correlation context and narrow clock/identifier/unit-of-work contracts into backend core; verify imports contain no business-specific rules or application service locator.
- [x] 2.2 Move SQLite/PostgreSQL and private object-storage adapters under backend infrastructure without changing bound parameters, JSON payload storage, locks or durable paths; verify adapter interfaces and transaction semantics are documented alongside the moved existing checks.
- [x] 2.3 Replace schema bootstrapping side effects across domain constructors with explicit ordered infrastructure initialization, retaining historical migration IDs and a non-destructive unsupported-schema failure; verify the initialization manifest contains no automatic owned-data reset or payload rewrite.
- [x] 2.4 Implement small, typed composition-root classes for app/admin/reports and explicit lifespan dependencies; verify no route factory or dependency container function exceeds 50 lines and no mutable `Workspace`-style service registry remains in the target design.

## 3. Identity, documents and annotations

- [x] 3.1 Extract identity models, session/OAuth/role repository ports and services, plus thin handlers; verify cookie names, origin/account checks, one-use flows and admin/owner policies are mapped to the original HTTP contract and existing tests/docs move with them.
- [x] 3.2 Extract document models, upload policies, metadata/binary repository ports, service and handlers; verify owner scoping, deduplication, accepted types, limits and stable IDs/digests remain explicit in the contract and moved checks.
- [x] 3.3 Extract annotation models/policies and PDF overlay adapter; implement `save_document_annotations.py` with revision/one-copy rules and atomic repository writes; verify original/copy references and stored annotation shape match the baseline documentation and existing checks.
- [x] 3.4 Implement `preview_document_deletion.py` and `delete_document.py` using the shared unit of work; verify primary-source cascading, annotated-copy deletion, context-only detachment, confirmation revisions and report-pinned binary retention are documented without changing historical payload fields.

## 4. Study content, generation and export ports

- [x] 4.1 Move canonical study contracts and compatibility readers into the study domain, separating persistence and content policies; verify historical fixture bytes, optional-field omission, metadata, source/variant fields and fingerprint inputs match the baseline manifest.
- [x] 4.2 Separate provider output schemas/expansion, OpenAI transport and usage-attempt port from generation orchestration; verify public interfaces and one-provider-call behavior are explicit and no prompt text/hash or generation retry behavior changes.
- [x] 4.3 Extract selected-page preparation and prompt resources into generation-owned services with injected document readers; verify original-page mapping and context roles remain represented in the documented contract and moved checks.
- [x] 4.4 Implement `generate_study.py`, `start_generation.py` and `cancel_generation.py` as separate use-case files with small job lifecycle collaborators; verify lock admission, cancellation-before-start, timeout, quota handling, context reset and incident paths are recorded in the lifecycle table.
- [x] 4.5 Implement `save_study_set.py` and the backend portion of `export_study_set.py` behind an export port; verify source authorization and legacy-compatible validation preserve the current save/export HTTP contract, including filename/deadline semantics.

## 5. Library, review progress and usage

- [x] 5.1 Extract folder/placement/archive models, repositories, services and handlers; implement `get_library_snapshot.py` and `rename_library_item.py`; verify folder-depth rules, archive restoration, name concurrency and Python JSON parsing are captured in moved checks/docs.
- [x] 5.2 Extract review models/repositories/services and `start_review.py`; replace domain HTTP exceptions with typed conflicts; verify round resumption, answer idempotency, ownership and normalized legacy fingerprints remain part of the public contract and existing checks.
- [x] 5.3 Extract allowance/reservation, provider attempts, tariffs, cost calculations and durable spool handling into usage-owned ports/services/adapters; verify daily reset definitions, immutable price snapshots, exact decimals and retry-spool paths remain unchanged in documentation and moved checks.
- [x] 5.4 Implement role/allowance/dashboard cross-domain administration use cases in separate files and thin admin handlers; verify owner-only operations and admin access map to the original permissions/HTTP contracts without exposing repositories to handlers.

## 6. Reports, offline formulas and HTTP delivery

- [x] 6.1 Extract report input/storage/triage/bundle services and separate `record_incident.py` and `collect_report_bundle.py`; verify sanitization, bounded snapshots, source retention, deduplication and existing report statuses/content are preserved in moved documentation/checks.
- [x] 6.2 Split ASGI request capture into small collaborators and a reports port, preserving bounded streaming and quota-report exclusions; verify request bodies are never buffered without bounds and report failures cannot break the original response.
- [x] 6.3 Move offline extraction/fonts/formula store/variant behavior into `formula_extraction` with explicit public services and small helpers; verify the legacy formula format, glyph semantics and original-source transformation rules remain documented and existing fixture bytes unchanged.
- [x] 6.4 Replace remaining nested route registration and middleware closures with domain handlers and reusable delivery adapters; verify the route manifest, status/error mapping, security headers and middleware ordering match the baseline.

## 7. Independent frontend application

- [x] 7.1 Move browser pages/styles/vendor assets, package manifests and asset scripts into frontend ownership; create an independent build/dev entry point and content manifest; verify the backend build context no longer contains frontend source and legacy public asset URLs resolve through the gateway contract.
- [x] 7.2 Refactor session/API/account/reporting code into injected classes and explicit ES-module APIs, retaining safe leave behavior and bounded diagnostics; verify no first-party global IIFE or callback exceeds 50 lines and existing browser checks/docs move with their feature.
- [x] 7.3 Extract library/workspace/document controllers, view/state objects and feature services from `home.js`, `app.js` and the viewer; verify first-party imports use explicit feature/core/rendering APIs and the old account/draft/cache/postMessage contract is documented unchanged.
- [x] 7.4 Refactor annotation/history and card/review/rendering controls into cohesive encapsulated collaborators; verify source navigation, formula front/back projection, gesture behavior, undo/save shortcuts and assessment semantics are retained in moved checks/docs.
- [x] 7.5 Publish the versioned private frontend print manifest/assets and implement the backend HTTP export adapter; verify no shared source mount/import or duplicate renderer exists, asset digests are explicit and the browser request allowlist remains bounded to approved print assets.
- [x] 7.6 Relocate frontend-owned checks/fixtures and split oversized existing test helpers without altering historical study-set fixture bytes; verify frontend tests do not import backend implementation and cross-application checks use HTTP contracts.

## 8. Logging and deployment configuration

- [x] 8.1 Consolidate JSON formatter, bound context and per-process setup under core observability; configure application/Uvicorn/background logs with service/environment/build identity; verify documented examples are single-line JSON, retain request/job IDs and contain no secrets/source payloads.
- [x] 8.2 Add optional Grafana Alloy Docker-envelope parsing and Loki field/label configuration, plus example LogQL queries; verify high-cardinality context stays in JSON, Docker rotation remains bounded and application startup does not depend on Loki availability.
- [x] 8.3 Add separate frontend/backend Dockerfiles, same-origin gateway/auth contract and private service routing; update local/production Compose and health checks; verify independent build contexts, unchanged durable mounts/secrets, proxy-header trust and admin/auth paths by configuration inspection.
- [x] 8.4 Update workflow build/deploy commands to build a coordinated frontend/backend release while retaining admin/reports and one-shot jobs; verify the existing main-push deployment cannot publish a mixed image set, and document rollback without running the workflow.
- [x] 8.5 Update README, runtime commands, architecture/contract documentation and local Pyan generator paths; remove obsolete flat-package imports, retain documented public browser facades required by classic entry points; verify documented paths match the tree and no first-party consumer depends on the flat package.

## 9. Integration acceptance

- [x] 9.1 Deliver the final import-direction/function-length/API/fixture-digest inventories and architecture review; verify zero first-party functions over 50 physical lines, no domain-to-handler/SDK dependency, no frontend/backend source coupling and one implementation file per cross-domain use case.
- [x] 9.2 Add/run focused checks alongside each owning group for repository isolation, gateway policies, logging/context reset, legacy read/save/restart/render/export, review resumption and browser state; verify results and failures are recorded per area rather than represented by static inventories.
- [x] 9.3 Run the existing complete regression suite, separate PostgreSQL/Garage checks and both application image builds with the integration HTTP flows; verify exact results and distinguish unavailable/live-provider checks from passed checks.
- [x] 9.4 Deliver the implementation diff, resulting tree, compatibility evidence, commands and any remaining verification limits; verify no production data, report status or user settings were modified and no deployment is claimed without separate authorization.

## Workflow follow-up

- Start implementation only after a new user request, as required by the `openspec-propose` planning boundary.
- Archive this change after implementation and the requested verification/review are complete.
- A production rollout is separate work: snapshot durable data, deploy a coordinated image set, verify historical hashes/fingerprints and use the documented image rollback if required.
