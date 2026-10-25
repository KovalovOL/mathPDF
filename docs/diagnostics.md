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

Logs use UTC timestamps ending in `Z`. Every application line includes `request=` and `job=` fields. The originating request context is retained by its background generation task, so planning, provider calls, validation and completion can be traced from one reference. A startup line identifies the running build and confirms that HTTP diagnostics are enabled.

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
