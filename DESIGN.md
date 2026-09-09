# DocSpring Make.com App — Design Notes

Port specification for the Make custom app. Companion to `README.md`. The
source of truth for behavior is the Zapier integration
(`DocSpring/zapier_integration`); this doc records what carries over verbatim
and what changes because Make apps are **declarative JSON + IML**, not Node.js.

## The core difference from Zapier

Zapier apps are Node.js: `perform` functions run arbitrary JS. Make apps are
**declarative** — each module is JSON describing the HTTP request (`url`,
`method`, `body`, `qs`, `headers`) plus **IML** expressions (`{{...}}`) for
mapping. Non-trivial logic (payload flattening, JSON-Schema → parameters) lives
in **IML functions** (`functions/`) or **RPCs** (`rpcs/`), not inline JS.

So: the *design* below ports directly; the *implementation* is re-expressed in
IML. Build and test each module against the live API before moving on — IML
mistakes are easiest to catch module-by-module.

## Connection (auth)

Mirror the Zapier custom auth (`authentication.js` + `lib/regions.js`):

- Parameters: `region` (US / EU / AU / Self-hosted), `custom_host`, `token_id`,
  `token_secret`.
- Base URL resolved from region (IML in `general/base`):
  - US `api.docspring.com` / sync `sync.api.docspring.com`
  - EU `api-eu.docspring.com` / sync `sync.api-eu.docspring.com`
  - AU `api-au.docspring.com` / sync `sync.api-au.docspring.com`
  - Self-hosted → `custom_host` (single origin, validated like `normalizeHost`)
- `Authorization: Basic base64(token_id:token_secret)` — Make computes the
  header in the connection/base (IML `base64()`).
- Connection validation → `GET /api/v1/authentication` (200 `{status:success}`).

## Modules

### Instant triggers (webhooks) — 13 events

Make "instant trigger" modules backed by a **shared webhook** with attach /
detach IML (the Zapier `performSubscribe` / `performUnsubscribe`):

- **attach** → `POST /api/v1/webhooks` with
  `{ webhook: { url, event_types:[<event>], include_submission_data:true,
  version:3, mode, template_uids, folder_uids } }`. `version:3` is pinned so the
  delivery shape matches the flattener.
- **detach** → `DELETE /api/v1/webhooks/{uid}`; tolerate 404.
- **payload** → an IML function `flattenDelivery` mirroring `lib/payload.js`:
  the top-level `id` stays the **event** id (uuid, stable across retries); the
  resource's own id is exposed as `resource_id`. (Dedup-correctness — never let
  the resource id overwrite the event id.)

Events: `submission.processed` / `.failed` / `.created` / `.expired`,
`submission_data_request.completed` / `.viewed`,
`combined_submission.processed` / `.failed`,
`submission_batch.processed` / `.failed`,
`template.created` / `.updated` / `.deleted`.

Scope parameters per event mirror `lib/scopeFields.js`:
- submission / data-request: Templates + Folders + Mode.
- template: Templates + Folders (no Mode — mode-agnostic events).
- combined / batch: Mode only (not template/folder scopable — the API rejects it).

### Actions

- **Generate PDF** — `POST {sync}/api/v1/templates/{template_id}/submissions?wait=true`.
  Template dropdown via RPC (`list_templates`); dynamic per-template fields via
  RPC over `GET /templates/{id}/schema`. Template-field inputs namespaced
  `data__<field>` so a field named `test`/`metadata`/etc. can't collide with a
  control input; the action strips the prefix to rebuild `data`. `pdf_passphrase`
  keyed (not "password") → mapped to the API's `password`.
- **Combine PDFs** — `POST {sync}/api/v1/combined_submissions?wait=true` with a
  line-item `source_pdfs` (`type` + `id` + optional `template_version`).
- **Create Data Request** — `POST {standard}/api/v1/templates/{id}/submissions`
  **with no `wait`** (a data-request submission returns immediately in
  `waiting_for_data_requests`; it doesn't produce a PDF until recipients finish).
  Recipients are a line-item (`email`, `name`, `fields`, `auth_type` — default
  `email_link`). Template pre-fill fields are all **optional**. After creating,
  mint a 30-day `email` token per recipient (`POST /data_requests/{id}/tokens`,
  `type:email`) and expose each `signing_url` (+ `first_signing_url`).

### Searches

- **Find Template** — `GET /api/v1/templates?query=…` (also backs the template
  dropdown RPC).
- **Find Submission** — by id (`GET /api/v1/submissions/{id}`; 404 → empty) or
  recent list filtered by mode/date.

## RPCs (dynamic data)

- `list_templates` — `GET /templates?per_page=100` → dropdown options.
- `list_folders` — `GET /folders` → dropdown options.
- `template_schema_fields` — `GET /templates/{id}/schema` → Make parameters
  (the `jsonSchemaToZapierFields` logic re-expressed for Make: scalar/enum/list
  → parameter types; nested objects → a JSON "collection"; `data__` namespacing).
  Optional-variant for Create Data Request (all fields non-required).

## IML functions (`functions/`)

- `flattenDelivery(body)` — v3 delivery envelope → flat object (see triggers).
- `toDeliveryShape(type, obj, event)` — wrap a list item so RPC/search output
  matches live deliveries (parity with `lib/payload.js`).
- `jsonSchemaToParams(schema, opts)` — JSON Schema → Make parameter definitions.
- small helpers: `asArray`, `parseDict`, `normalizeHost` equivalents.

## Gotchas carried over

- `version:3` pinned on webhook subscribe.
- `data__` field namespacing on Generate PDF / Create Data Request.
- `pdf_passphrase` field key (not "password").
- Sync host + `?wait=true` for Generate PDF / Combine PDFs; **standard host, no
  wait** for Create Data Request.
- Self-hosted `custom_host` validation (only `[scheme://]host[:port]`).

## Publishing

Build as a **private** app first (usable by our org), test every module against
the DocSpring test account, then submit for **Make app verification** to list it
in the public app directory (review process, like Zapier's).

## Open items (resolve during setup)

- Confirm the Make Apps SDK local file layout + the push mechanism (SDK CLI vs
  Make API vs web "Custom apps" editor) once the Make account/API token exists.
- Confirm Make's line-item (array) parameter UX for `source_pdfs` / recipients.
- Confirm whether Make strips empty values before requests (Zapier's
  `cleanInputData`); if so, handle blanks in IML as the Zapier performs do.

## Implementation decisions (v1, built via SDK API)

- **One "Watch Events" instant trigger**, not 13 discrete triggers. It offers an
  `event_types` multi-select (all 13 events) + a Mode filter, and subscribes to
  the chosen events in one DocSpring webhook. This is the idiomatic Make pattern
  (cf. Stripe's "Watch Events") and far less to maintain than 13 near-identical
  modules. Output is the flattened envelope (`id` = event id, `resource_id` =
  the resource's id) + the full `data` object.
- **Create Signing Link is its own action** (not folded into Create Data
  Request), because a Make module makes exactly one HTTP request — so minting the
  30-day `email` token per recipient (`POST /data_requests/{id}/tokens`) is a
  separate, chainable module (map over Create Data Request's `data_requests`).
- **Dynamic template fields** via the `templateFields` RPC: `keys(body.properties)`
  from `GET /templates/{id}/schema` → one `data__<field>` text input per field,
  bound to the Generate PDF / Create Data Request `data` collection.
- **Sync host + `?wait=true`** for Generate PDF / Combine PDFs (absolute URL in
  the module, base auth headers still applied); **standard host, no wait** for
  Create Data Request.

## Validation status
- ✅ Find Template + the connection (region base URL + Basic auth IML) — tested
  live in a Make scenario; returned the Demo template.
- ⏳ Generate PDF (dynamic fields), Create Data Request, and Watch Events
  (attach/detach + flatten) — built, need a live spot-test to confirm the more
  involved IML (RPC-driven fields, webhook subscribe/flatten).
