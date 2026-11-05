# Coordinated frontend/backend rollout

This document describes a future deployment. Local refactor acceptance does not authorize a production rollout.

## Durable data

Keep the existing `.formula-lab/` and `.infrastructure/` directories and all current PostgreSQL/Garage secrets and volumes. Take a database snapshot and preserve object storage before a production rollout. The source-layout refactor introduces no payload rewrite and no new migration identifier. The existing one-shot verified migration still runs with writers stopped; original SQLite files and backups remain available.

Compose retains the existing app/admin/reports/db/garage/bootstrap/migrate service names and adds `front`. Only `front:8080` receives public Traefik traffic. Its private `8081` asset contract is not published. Backend processes use the same image and storage configuration. App health checks do not depend on the frontend asset server, avoiding a startup cycle.

## Image pair

The deployment workflow builds both applications from one checked-out commit before stopping any writer. The backend image has a commit build identifier; the frontend has a content-derived asset identifier. Both images receive immutable release tags. The workflow starts the pair with `--no-build --wait`, then updates the convenience `:production` tags only after the services are healthy.

`.infrastructure/release.env` records the healthy image pair; `.infrastructure/previous-release.env` retains the preceding pair. They contain image references only. Local source PDFs, development environments, generated graphs and Node dependencies are excluded from synchronization. Bootstrap and migration containers remain one-shot jobs and are removed after a successful run.

## Rollback

For a later release using this layout, select the prior pair with:

```sh
docker compose --env-file .env --env-file .infrastructure/previous-release.env up -d --no-build --wait
```

For the first transition from the single application image, preserve the previous checkout, Compose file and image IDs before rollout. Roll back that checkout and its Compose configuration together, stop the new frontend container and restore the prior image for app/admin/reports. An old backend cannot serve the new private gateway contract. Do not combine an old backend with the new frontend. Keep durable directories attached and do not run `down -v` or delete migration backups.

Verify authenticated library loading, an existing saved set, its source link, review resumption, annotation-copy loading and PDF export after either operation. No live AI generation is necessary to verify the layout change.

## JSON logs and Loki

Backend records contain `schema_version`, `timestamp`, `level`, `service`, `environment`, `build`, `event`, `request_id` and `job_id`, plus bounded context. Exception records use safe type/location fields; credentials are redacted. Request and background scopes reset after completion. The frontend gateway also emits JSON access records without query strings.

`infrastructure/observability/alloy.alloy` unwraps Docker records, keeps only the `mathpdf` Compose project, parses application JSON and indexes only `app`, `service`, `environment` and `level`. Request IDs, users, filenames and routes remain JSON fields, preventing unbounded label cardinality. Compose's bounded `json-file` driver retains the project/service envelope metadata.

Use this pipeline in an existing Alloy installation, or explicitly enable the optional Linux-host service:

```sh
LOKI_URL=https://your-private-loki/loki/api/v1/push docker compose -f docker-compose.yaml -f infrastructure/compose/observability.yaml --profile observability up -d alloy
```

Configure authenticated delivery for the receiving Loki deployment. The optional shipper mounts Docker log files read-only and has no Docker socket or application data mount. The shipped filter expects the existing Compose project name `mathpdf`; change that selector if intentionally using another project name. The configuration can be checked offline with `alloy validate` without sending logs.

Example LogQL filters (references are parsed fields, not indexed labels):

```logql
{app="mathpdf", service="app"} | json | request_id="YOUR_REFERENCE"
{app="mathpdf", level="ERROR"} | json | line_format "{{.event}} {{.summary}} {{.location}}"
```
