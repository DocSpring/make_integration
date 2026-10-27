# DocSpring Make app: design notes

The Make custom app (`docspring-sspkqt`, app version 1) on DocSpring API v2, with the full operation set (sc-5981).
The behaviour follows the sc-5981 build spec shared by every DocSpring integration (Zapier, n8n, Node-RED, Pipedream,
Bubble and this app), so they behave and read the same. `app/UPLOAD.md` says how the files get into Make;
`app/APP.md` has the app's identifiers and the Make API routes.

Make apps are declarative: each module is JSON describing its HTTP requests, with IML expressions (`{{...}}`) for
mapping. There's no JavaScript: custom IML functions need Make support to enable them for the app, so this app uses
only Make's built-in IML functions.

## Connection and base

- Parameters (unchanged, so existing connections keep working): `region` (US, EU, self-hosted), `custom_host`,
  `token_id`, `token_secret`.
- Base URL: `https://api.docspring.com/api/v2`, `https://api-eu.docspring.com/api/v2`, or the self-hosted host
  (`https://` prepended when it has no scheme) + `/api/v2`.
- Every request sends `Authorization: Basic base64(token_id:token_secret)`, `Accept: application/json` and
  `User-Agent: docspring-make/2`. `log.sanitize` hides the Authorization header in the base and the connection.
- The connection test is `GET /api/v2/authentication`, valid when `body.authenticated` is true. A 401 says the token
  isn't valid. A 404 from a self-hosted host says the server doesn't have API v2 yet and needs the latest release.

## Requests

- **Hosts.** Generate a PDF, Generate a batch of PDFs, Combine PDFs, Generate files for a submission, Create a
  template and Replace a template's PDF go to the sync host (`sync.api.docspring.com`, `sync.api-eu.docspring.com`, or
  the self-hosted host) with `?wait=true`, or `wait=false` when the user turns off "Wait for the PDF". They use an
  absolute URL, so they set the auth headers themselves. Everything else uses the base URL.
- **Bodies** are flat JSON. `version` and `wait` are query parameters.
- **Empty values.** The app uses manifest 2 processing: an empty input becomes `undefined` and Make leaves it out of
  the request, so the API never gets `""` or `null` for an empty optional value. `test` is sent only when it's true
  (`{{if(parameters.test; true; undefined)}}`): v2 rejects `test: false` from a test token. `metadata` is a key/value
  list turned into an object with `toCollection()`, and left out when empty.
- **Template data.** Template fields are mappable inputs from the `templateFields` RPC, which reads
  `GET /templates/{id}/schema?version=`. They go in one `data` collection (the RPC's `wrapper`), so a field named
  `test` or `metadata` can't clash with the module's own inputs, and the module sends `data` as the user mapped it.
  Each field gets its type from the schema (boolean, integer, number or text, so Make sends real booleans and numbers;
  JSON for objects and arrays such as image fields), `required` from the schema, and help: `YYYY-MM-DD` for a date
  field, the enum values, the description, or a JSON example. Check data for a template and Create a signature request
  load the same fields as optional.
- **Dates.** v2 takes `YYYY-MM-DD` for date fields. Make converts a `date` input to a UTC timestamp, which can move
  the day, so date fields are text inputs whose help says `YYYY-MM-DD` and suggests `formatDate()` for a mapped
  date. Search submissions' `created_after` and `created_before` are Make `date` inputs: the API takes timestamps
  (`date-time`) there.
- **IDs in paths.** Every ID that goes into a URL path goes through `encodeURL(trim(...))`, so an ID such as
  `../templates/tpl_x` stays one path segment. `encodeURL()` leaves dots alone, and a URL parser turns a `.` or `..`
  segment into the current or parent path, so each module whose path takes an ID starts with a request-less step
  that fails first for an ID of `.` or `..` (after trimming): "The submission ID can't be "." or ".."." (a
  DataError, from `response.valid`). The template field pickers make no request for such an ID.
- **Lists.** `limit` (up to 100) and `cursor`; responses are `{data, next_cursor}`. The pickers (`listTemplates`,
  `listFolders`) follow `next_cursor` up to 1,000 items. The searches (Search submissions, Search templates, List
  folders) follow it up to their Limit input.

## Failures

- **An HTTP error** (base `response.error`): `DocSpring API error <status> <code>: <message>`, a line per detail
  (`<pointer or parameter>: <message>`), then `Submission: <id>` (or the batch, combined PDF or template ID) and
  `Request ID: <id>`. The details come from `createJSON(body.error.details)` reshaped with `replace()` and regular
  expressions; if Make reads those differently, the details show as JSON, never `[object Object]`. The captures skip
  JSON-escaped characters, so a message with quotes (`must be one of: "Red", "Blue"`) keeps its text, and the quotes
  and backslashes are unescaped at the end. Every backslash in those regular expressions is inside a character
  class, so they read the same whether or not IML strings process backslash escapes, which Make doesn't document.
- **A 201 with a failure state** (`error`, `syntax_error`, `image_download_failed`, `image_processing_failed`, or a
  template `document.state` of `password_required`, `malformed_pdf`, `unknown_error` or `download_failed`): the
  module's `response.valid` fails with the state, `error_message` and the record ID.
- **A 504 `polling_timeout`**: "The PDF wasn't ready in time. Get it later with Get a submission (<id>), or use the
  submission.processed trigger." (and the combined PDF, batch and template versions). It's a RuntimeError rather
  than Make's default for a 5xx (a connection error, which Make retries), so a retry can't generate a second PDF.

## Modules

29 modules. Labels, descriptions, types and bindings are in `app/UPLOAD.md`; groups in `app/groups.imljson`.

| Group | Modules |
|---|---|
| PDFs | Generate a PDF, Generate a batch of PDFs, Get a submission batch, Check data for a template, Combine PDFs, Get a combined PDF |
| Submissions | Get a submission, Search submissions, Generate files for a submission, Expire a submission |
| Signature requests | Create a signature request, Create a signing link, Get a signature request |
| Templates | Search templates, Get a template, Create a template, Replace a template's PDF, Copy a template, Move a template, Publish a template version, Get a template's page images |
| Template fields | List template fields, Add fields to a template, Update fields in a template, Remove fields from a template |
| Folders | List folders, Create a folder |
| Triggers | Watch events |
| Other | Make an API call |

Each module returns the v2 resource as the API returns it. Interfaces and samples are generated from the OpenAPI
spec by `scripts/generate_interfaces.py`.

- **Template pickers.** A template select (`rpc://listTemplates`) nests a version select (`latest` by default, which
  is the latest published version, or the draft when nothing is published), which nests the template fields.
- **Create a signature request** makes three requests: it creates the submission with `signature_requests`, makes a
  signing link for each signature request (a `repeat` over the IDs, with the chosen link type: email, 7 days, by
  default; API, 24 hours; or none), and returns the submission plus `signing_links`, `first_signature_request_id` and
  `first_signing_url`. Each signer's `fields` is a list of field names to type or map (also in Check data for a
  template), as List template fields shows them: the full `name`, such as `address/street`, which a signature request
  needs (the schema nests it under `address`). It isn't a picker because Make calls an RPC inside an array item with
  only that item's inputs, so the RPC can't read the module's template (tried 27 Oct 2026).
- **Make an API call** takes a path relative to `/api/v2`, a method, query string, headers and a body.

## Watch events

One instant trigger on a dedicated webhook, as in v1.

- **Parameters:** Events (every v4 event except `webhook.*`: 22 events), Mode (live, test, or both), Templates
  (`rpc://listTemplates`), Include submission data (default on).
- **attach:** `POST /webhooks` with `url`, `event_types`, `name: "Make"`, `mode`, `template_ids` and
  `include_submission_data`, never `version`, so DocSpring sends version 4 events. It stores the webhook's `id` and
  first event type. Only submission, signature request and template events can be limited to templates (DocSpring
  rejects the others with a 422), so with templates chosen, a request-less step first fails with the events that
  can't be: "Templates only limit submission, signature request and template events. Clear Templates, or remove
  these events: combined_pdf.processed, ...".
- **detach:** lists the webhooks with that event type, 100 a page (a `repeat` that follows `next_cursor` until it
  finds the webhook, up to 20 pages), and deletes the stored webhook only if it's in the list. Make can't treat an
  HTTP 404 as success, so this is how detach tolerates a webhook someone already deleted in DocSpring.
- **Output:** the version 4 event as delivered (`id` = the event ID, `event_type`, `created_at`, `data` = the v2
  resource) plus `resource_type` (the event name before the first dot) and `resource_id` (`data.id`).

## Where this differs from the spec, and why

- **Labels follow Make's naming conventions**, not the spec's names: an action is a verb and an item with "a" or "an"
  ("Generate a PDF", "Create a signature request"), a search a plural without one ("Search templates", "List
  folders"), all in sentence case. The v1 review asked for it. The module IDs keep the spec's names (`findTemplate`).
- **Signing links are a separate `signing_links` list**, not a `signing_url` added to each signature request. IML
  can't merge a value into each item of a list without custom IML functions. `first_signing_url` and
  `first_signature_request_id` are as specified.
- **Date fields are text inputs** with `YYYY-MM-DD` help (the spec's first option). Formatting each dynamic date field
  with `formatDate()` would need custom IML functions.
- **The self-hosted 404 message doesn't offer a previous version:** the app changes in place, so there's none.
- **Pickers stop at 1,000 items**, as the spec says. Make's best practice suggests 300 to 500 for an RPC that pages
  100 at a time, so a reviewer may ask for less.

## Make limits that shape the app

- A module times out after 40 seconds (Make's default; Make support can raise it for an app). A PDF that takes
  longer fails in Make, not with DocSpring's 504; turning off "Wait for the PDF" avoids it.
- A request URL can be at most 512 characters and an error message 1,024. `scripts/check.py` checks both.
- A module makes at most 100 requests, 50 of them pages. Create a signature request's link loop stops at 100 signers.

## Custom IML functions: the upgrade path

If Make enables custom IML functions for the app (or the token gets the "apps edit" permission), they would allow:
a `signing_url` on each signature request, date fields as Make `date` inputs formatted to `YYYY-MM-DD`, and enum
fields as dropdowns.

## Checks

Make runs the IML, so there's no test framework. `scripts/check.py` checks that every file is valid JSON with closed
`{{ }}`, that nothing calls `/api/v1`, Make's URL and error-message limits, each module's sections, every `rpc://`
reference, the groups, and that `app/UPLOAD.md` names every module and RPC.

It also runs `scripts/iml_tests.py`, which runs the app's own expressions with `scripts/iml.py`, a small IML evaluator
that follows Make's documented behaviour (JavaScript operators, 1-based indexes, `replace()` with `/regex/flags`). The
tests cover the error message (with and without backslash escapes in IML strings), encoded IDs and the `.`/`..` checks
in every URL, that no field inside an array item calls an RPC, the Watch events template check, Remove template
fields' typed IDs and detach's paging. The evaluator knows only the functions the tests need, and fails on any other.

## Validation status

The API v2 version hasn't run in Make yet. `app/UPLOAD.md` ("Testing") lists the live tests and the Make behaviour
these files rely on that hasn't been tried.

The v1 app (API v1) was validated live in Make in September 2026: the connection, Find template, Find submission,
Generate a PDF, Combine PDFs, Create a signature request, Create a signing link and Watch events (attach, delivery,
detach).

## How modules are tested without the canvas

All v1 modules were run through the Make API (token in `.env`), driven from the shell:

1. Clone the connection binding from a working scenario: flow module `app#docspring-sspkqt:<module>`,
   `parameters: {"__IMTCONN__": <connId>}`, `mapper`.
2. `POST /scenarios` (or `PATCH /scenarios/{id}`) with the blueprint as a JSON string.
3. `POST /scenarios/{id}/start` to activate it (on-demand scenarios must be active to run).
4. `POST /scenarios/{id}/run` `{responsive:true}` returns an `executionId`; poll `GET /scenarios/{id}/logs` for
   `status:1`.
5. Check the result in DocSpring (the submission, combined PDF or webhook).

For the instant trigger: `POST /hooks` `{typeName:"app#docspring-sspkqt", __IMTCONN__, event_types, mode}` creates the
hook (runs `attach`); a scenario with `metadata.instant:true` and `parameters:{"__IMTHOOK__":<hookId>}` binds to it;
`DELETE /hooks/{id}` runs `detach`. Team `2910546`, connection `10972788`.

## IML lessons from v1

- There's no `array()`: build a one-element array with `add(emptyarray; x)`.
- `get(body.properties; item)` inside an RPC's `iterate` output failed in v1: `body` wasn't reliably in scope there.
  `templateFields` now iterates `toArray(body.properties)`, so each item carries its own schema, and reads
  `body.required` through `ifempty(...; emptyarray)`, so at worst every field is optional.
- Custom IML functions need an "apps edit" permission the API token lacks.

## Make review (v1)

The v1 app went through Make's review in September 2026. What still applies:

- Review prerequisites: a universal "Make an API call" module, `log.sanitize` on the Authorization header and a
  password-type token secret, a label, description and interface on every module, base and connection error
  handling, a `limit` on every search, samples on searches and the trigger, `crud` on actions, meaningful groups,
  sentence-case labels and third-person descriptions.
- Demo scenarios: one per module with a successful run and clean data (`Jane Doe` / `jane.doe@example.com`), and a
  scenario that shows a handled API error (the review form's "Scenario with an API Error" field). The Make plan caps
  active scenarios, so on-demand demos can be off as long as they keep their green run logs.
- The review request is UI-only: in the app editor, Publish, make every module visible in the Modules tab, then the
  Review tab: paste the API docs link and the demo scenario links and request a review. Prepared answers: we are the
  vendor; support `support@docspring.com`; category Files & Documents; service URL https://docspring.com; API docs
  https://docspring.com/docs; trademark and third-party terms: yes (our own API).
- The reviewer asked for the signing link `type` in the query string. v2 takes it only in the body (a query
  parameter is a 422), so it's in the body again.
