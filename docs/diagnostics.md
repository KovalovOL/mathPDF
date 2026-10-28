# API and generation diagnostics

## Read VPS logs

All application diagnostics go to the container's standard error stream, available through Docker:

```sh
cd /opt/mathPDF
docker compose logs -f --tail=200 app
```

To locate a reference from an error message:

```sh
cd /opt/mathPDF
docker compose logs --since=30m --no-color app | grep -F 'PASTE_REFERENCE_HERE'
```

Application, admin/report service and Uvicorn logs use one JSON object per line, with an ISO UTC `timestamp`, `level`, `logger`, `event`, `request_id` and `job_id`. Request logs add `method`, normalized `route`, authenticated `user_id`, `status` and `duration_ms`. Failures add a stable `error_code`, controlled English `summary`, `error_type`, safe application `location` and SQLSTATE when available. Raw exception messages, local values, request bodies and source contents are excluded from stdout. Access logs drop query strings, including OAuth codes.

The originating request context is retained by its background generation task, so provider calls and completion can be traced from one reference. A startup line identifies the running build and confirms that HTTP diagnostics are enabled. Docker prefixes are separate from each application's JSON; use `--no-log-prefix` when piping to a JSON reader:

```sh
docker compose logs --since=30m --no-color --no-log-prefix app reports admin
```

The bounded `ui` object comes from `X-MathPDF-UI-Context`: screen, last action, target, document/study-set identifier, filename, PDF page and card index when available. The header is an untrusted diagnostic hint, never authorization. It excludes text inputs and document content. A fresh library load has a screen and route even if no click occurred yet.

API request entries record method, normalized route, status, content type, response length and time to response headers. Successful job polls stay at DEBUG to avoid flooding INFO logs. Failed polls and other API failures are visible. Provider entries record phase, status, output token count when available, duration and safe exception types. Unexpected exceptions include stack file/line/function locations, without exception messages or local values.

The app container uses the Docker `json-file` driver with three rotating files of up to 10 MB. Container replacement starts a new container log history; no external log service is introduced.

## Browser diagnostics

API calls include `X-MathPDF-Request-ID`. Responses echo the validated identifier and include `X-MathPDF-Build`. Unreadable responses display HTTP status, content type and a Reference, rather than only “unreadable response”. Failed generation jobs also display their originating request reference. The browser console records the metadata event `mathPDF API failure` for failed API responses.

When signed in, the browser reports failure metadata through `POST /api/client-errors`, using the existing session, account header and same-origin checks. Reports contain only an allowlisted event type, normalized route/method, status, content type, redirect/final-route metadata, response sizes when known, build identifiers and request reference. They contain no response bodies, request payloads, filenames, PDF content, formulas, prompts, credentials, cookies or OAuth query strings. Received size measures decoded text; the HTTP content length can describe compressed bytes.

Reports are limited to ten per page and ten per account per minute, have a 4 KB body limit, and do not recursively report their own failures. If a session or network outage prevents submission, the console event and visible reference remain available. The absence of a matching server HTTP entry alone does not prove a particular proxy or network cause.

## Asset versions

Application HTML is served with `Cache-Control: no-store`, a build meta tag, and content-versioned local JS/CSS URLs. JavaScript, modules and CSS require revalidation with `Cache-Control: no-cache`. Existing open tabs still need a reload to load the new code. The build identifier hashes application code/assets/prompts; it is not a Git commit SHA and does not include environment secrets.

The exact cause of the previously reported unreadable response was not captured. Current public API inspection returned JSON and matching deployed code hashes. These diagnostics make a recurrence traceable; they do not establish successful authenticated generation by themselves.

## Formula renderer health

Generation no longer initializes Chromium or rejects a complete set for mathematical formatting. It makes one provider request and validates count/source ownership; KaTeX runs on display with a readable raw-text fallback. Successful metadata records `math_check: on_display` and `formatting_policy: best_effort`. This prioritizes usability and removes preflight browser latency. PDF export still uses Chromium, with the same raw-text fallback for unsupported TeX.

The October 25 zero-progress failure was reproduced locally: the previous blank validation document used quirks mode, causing KaTeX to reject even `x+1`. Logs showed every candidate rejected as `invalid_math`. Missing PDF.js source maps are browser debugging files and do not cause this failure.

The later reference `c7f8c8ee266b400a87fefa2c6004238c` produced five problems in about 13 seconds but was rejected as `math_in_text`. The non-blocking display policy removes that rejection rather than making another provider request.

## Private tester reports

The metadata-only `/api/client-errors` logger remains supported. The separate `/api/reports` system additionally collects sanitized business context and private owner-checked source snapshots for administrators. See [platform reports and retention limits](platform.md#automatic-and-manual-reports).

Report details start with a computed incident summary: cause/code, user, screen, action, request/status, safe stack location, page/card and referenced files. Repeated request entries are compacted into a timeline, followed by recent actions. Full original evidence remains in collapsed **Advanced: full diagnostic JSON** and the private download bundle. Historical reports get the same summary without rewriting their stored payloads.

## Library conversion incident

The October 28 library failure was PostgreSQL `UntranslatableCharacter`, SQLSTATE `22P05`: a valid saved TEXT JSON payload contained an escaped NUL. Casting the whole payload to JSONB for library metadata rejected that character. Library projection now parses the required metadata in Python; canonical saved payloads, formulas and source references are unchanged. Invalid metadata in one set no longer hides all files. The diagnostic identity is `library_metadata_decode_failed` for historical instances of this error.

### Verified rollout

The urgent library fix `d6f0811` and monitoring/card release `85c04f0df2987c729b429477597637d004f611a8` deployed successfully; the latter is [Actions run 40772721676](https://github.com/KovalovOL/mathPDF/actions/runs/40772721676), build `d72b51b49806`. Public health returned HTTP 200 and all five persistent services were healthy. The affected account's library returned 4 files and 30 sets, including the original set with a NUL character. Its historical incident now returns `library_metadata_decode_failed`, `UntranslatableCharacter`, the library screen and a safe application location, with original evidence retained.

Post-release hashes matched all 7 documents, 31 study sets, 12 folders, 33 placements, 3 role assignments and the daily-limit row. All 7 binaries verified, and all prior usage identifiers and known token observations were retained. The administrator's configured daily limit remained 100,000 tokens. A harmless anonymous API request verified JSON log correlation, frontend screen/action context and typed error fields on production without recording a user bug report.

Verification passed 159 default tests plus all 6 separate real PostgreSQL/Garage checks. Synthetic browser checks cover 320-pixel touch layout, drag-versus-tap, source links, keyboard navigation, classic workspace entrypoint parsing, review persistence/retry and collapsed original report evidence. A 390-pixel real workspace preview confirmed the compact footer and answer-to-next-card flow; the admin preview confirmed historical incident presentation. No external AI requests or private document transfers were required.
