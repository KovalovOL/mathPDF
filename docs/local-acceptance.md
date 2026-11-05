# Local acceptance

The `acceptance.yaml` stack uses only named volumes created for a disposable Compose project, loopback ports and synthetic credentials. It does not mount the host's `.formula-lab`, `.infrastructure`, `.env` or source PDFs. No OpenAI key is configured. Google identity is seeded inside the isolated backend solely for HTTP checks; no development login bypass is added to the application.

Build the independent contexts, then start the isolated processes:

```sh
docker build -t mathpdf-backend:refactor-check back
docker build -t mathpdf-frontend:refactor-check front
docker compose -p mathpdf-refactor-check -f infrastructure/compose/acceptance.yaml --profile storage up -d --wait
```

The public test gateway uses `http://127.0.0.1:18770`. PostgreSQL and Garage fixture endpoints use loopback ports 18773 and 18774. `tests/integration/seed_fixture.py` is supplied to `docker compose exec -T app python` over stdin; write its synthetic session JSON to a temporary local file and set `MATHPDF_GATEWAY_FIXTURE` when running `tests/integration/test_gateway.py`.

The six storage migration checks in `back/tests/test_platform_migration.py` require `MATHPDF_INTEGRATION=1`, PostgreSQL host/port/user/database and the test-only password file, plus the Garage endpoint and test-only S3 credentials file copied from this disposable stack. Each check creates and removes its own synthetic PostgreSQL database. The retained source SQLite snapshot and object digests are compared before and after migration.

Run static checks and ordinary regressions separately:

```sh
uv run --python 3.12 --project back --extra dev python infrastructure/quality/architecture.py
uv run --python 3.12 --project back --extra dev python infrastructure/quality/function_inventory.py
npm --prefix front run format:check
uv run --python 3.12 --project back --extra dev pytest
```

For independent frontend checks, first build assets, then run `uv sync --python 3.12 --project front` and `uv run --python 3.12 --project front pytest front/tests`. Backend-only checks run from `back/` with its own project and copied compatibility fixtures. PDF export checks additionally need the private frontend asset server (`node front/scripts/serve.mjs --assets-only` from the repository root). The local sample-PDF extraction checks are skipped when the optional root `main.pdf` is absent.

Stop and remove only this disposable project when finished. Removing its named volumes is safe after accepting the test results; do not apply that cleanup command to the normal `mathpdf` deployment project.
