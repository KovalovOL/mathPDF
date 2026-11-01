# Acadence branding audit

Acadence is the product name. This change updates the existing application without changing its behavior or saved formats. It does not rename a repository or deploy the application.

## User-facing changes

- Library, reading workspace, sign-in and administration headings and browser titles use Acadence.
- First-login welcome copy uses Acadence; its existing per-account receipt is unchanged.
- Application name, description and Open Graph metadata use Acadence on these pages. No unconfigured domain, social image or canonical URL is introduced.
- FastAPI application/service titles and the CLI description use Acadence.
- README product description and navigation instructions use Acadence.

The existing mathematical favicon is a symbol, not an old wordmark, and is retained. The standalone PDF viewer and print template have neutral titles. No separate registration page, email templates, PWA manifest or service worker was found. Login uses Google OAuth; externally configured consent-screen branding is outside this repository.

## Intentional old references

| Reference | Why it remains |
| --- | --- |
| `mathpdf.site`, default origin and OAuth callback | Existing production domain and authorized redirect must continue working. |
| `mathpdf_session`, `mathpdf_oauth`, including secure cookie variants | Renaming would invalidate active sessions or in-flight sign-ins. |
| `MATHPDF_*` environment variables | Existing server secrets, deployment settings and export configuration depend on them. |
| `MathPDF`, `MathPDFSession` JavaScript globals | Shared rendering, authentication, export and browser tests use these internal contracts. |
| `X-MathPDF-*` headers, `mathpdf-build` metadata and diagnostic context/log names | Browser/server/service correlation and account-change checks use these identifiers. |
| Browser storage, cache, channel, event and drag payload names | Preserve drafts, reading preferences, cache coordination and older open tabs. |
| `/MathPDFCopy`, `/MathPDFRevision` PDF metadata | Preserve annotation-copy compatibility. |
| `mathpdf-assets`, `mathpdf-formula-lab`, `formula_lab`, `formula-lab` | Package names, imports, lockfiles and the installed CLI remain compatible. |
| Database/user/bucket `mathpdf`, `/opt/mathPDF`, secret paths, image/service/router and workflow identifiers | Existing persistent data, credentials, containers and routing depend on these. |
| `mathpdf.local` | Isolated, intercepted PDF-export origin; not a public product domain. |
| Old repository/action URLs in historical verification records | Preserve accurate provenance; do not invent new URLs before a rename. |
| OpenSpec historical documents, frozen fixtures and diagnostic examples | Historical evidence and technical contracts, not current UI copy. |

No technical migration is required for this branding change. Do not rename these identifiers as part of the repository rename. The separate metrics repository and its historical experiments are outside this application change.

## Changed files

- `README.md`: current product name, description and audit link.
- `formula_lab/app.py`: OpenAPI title and CLI description.
- `formula_lab/platform_services.py`: administration/report service titles.
- `formula_lab/static/admin.html`, `home.html`, `index.html`, `login.html`: visible brand, accessible labels, titles and metadata.
- `formula_lab/static/welcome.js`: welcome heading.
- `tests/test_welcome.py`: expected accessible dialog name.
- `docs/rebranding.md`: audit, compatibility decisions and manual actions.

## Manual GitHub rename

The checked-out remote is `https://github.com/KovalovOL/mathPDF.git`; do not assume the owner's separate `olexandratabakova` account owns this application repository.

1. With administrator access, open the existing `KovalovOL/mathPDF` repository, then **Settings → General → Repository name**.
2. Set the name to `acadence` and select **Rename**. If transferring ownership is also desired, plan it separately; a rename does not transfer ownership.
3. After confirming the rename, update each application checkout:

   ```sh
   git remote set-url origin https://github.com/KovalovOL/acadence.git
   git remote -v
   git ls-remote origin HEAD
   ```

4. Use `https://github.com/KovalovOL/acadence` for new links and clone instructions. Review external CI integrations, webhooks, badges, GitHub Apps and any repository-scoped deploy-key configuration against the new location. Historical Actions links may stay as provenance; verify their redirect after renaming.
5. Retain repository Actions secrets (`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`, `APP_ENV`) and confirm the deployment workflow is enabled. The workflow deploys pushes to `main`; merging/pushing these changes there initiates production deployment.

## Manual deployment and external branding

- Review and release the branding change using the existing workflow; this task does not initiate production deployment.
- Keep `APP_BASE_URL`, DNS, TLS routing and Google's authorized redirect URI at `https://mathpdf.site/auth/google/callback` until a new domain is explicitly approved and configured.
- If the Google consent screen displays the old product name, update its app name to Acadence in the existing Google Cloud project's OAuth branding settings. Retain client IDs, secrets and redirect URIs; complete any provider-required review.
- Update the GitHub repository description manually to “Acadence — an AI-assisted learning environment for students.” Repository settings are not changed by this patch.
- After release, smoke-test sign-in, an existing account's library, PDF opening/annotations and PDF export. No database, bucket, filesystem or account-data migration is required.

## Verification (1 November 2026)

- `python -B -X utf8 -m pytest -q`, using local Chrome through the existing `MATHPDF_CHROMIUM_EXECUTABLE`: **179 passed, 6 skipped**. Skipped checks require disposable PostgreSQL/Garage infrastructure. Authentication/session, ownership, PDF rendering/export/annotations, historical saved formats and welcome desktop/mobile checks passed with synthetic data.
- The initial run without UTF-8 mode had four Windows CP1252 test-harness failures; the UTF-8 run resolved them without application changes.
- One existing Starlette/httpx deprecation warning remains; dependency changes are outside this branding task.
- `uv build --offline --out-dir output/rebrand-build`: source distribution and wheel built successfully. Packaged login/welcome branding and the four pages' metadata were inspected.
- `git diff --check`: passed. No configured lint or type-check command was found in `pyproject.toml` or `package.json`.
- No paid generation, live Google OAuth exchange, production data access or deployment was performed. Existing tests mock provider responses; live provider behavior is not newly certified.
