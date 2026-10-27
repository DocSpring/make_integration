# DocSpring app for Make

The DocSpring custom app for [Make](https://www.make.com) (formerly Integromat). It's a public app, `docspring-sspkqt`
(app version 1), in Make's US2 zone.

The app is on DocSpring API v2 with the full operation set (sc-5981): 29 modules for PDFs, submissions, signature
requests, templates, template fields and folders, a Watch events trigger and a universal "Make an API call" module.
It behaves like DocSpring's other integrations (Zapier, n8n, Node-RED, Pipedream, Bubble), which follow the same
spec. A self-hosted DocSpring server needs a release with API v2.

## Status

The API v2 version is live in Make: it was uploaded with `app/UPLOAD.md` on 27 Oct 2026, tested live, and its 29
modules are public. Anyone can install it from its public link,
https://www.make.com/en/hq/app-invitation/68c6ec31b2b25382cfa7ad917caa7420, which docspring.com/integrations/make
links to. Make's review, requested in September 2026 for the v1 app (`DESIGN.md`), is still pending, so the app isn't
in Make's app directory yet.

## Layout

Make apps are JSON with IML expressions, stored in Make. This repo keeps a copy of every section:

```
app/base.imljson           base URL (region + /api/v2), auth headers, error messages
app/connections/           the connection: api (the authentication test) and parameters (region, host, token)
app/modules/<id>/          one folder per module: api, expect (inputs), interface (outputs), samples
app/rpcs/                  pickers: templates, folders, template fields, field IDs
app/webhooks/              the Watch events webhook: api, parameters, attach, detach
app/groups.imljson         the module groups shown in Make
app/readme.md              the app's documentation in Make's listing
app/UPLOAD.md              how to upload everything with the Make API, and each module's label, type and binding
app/APP.md                 the app's identifiers and the Make API routes
scripts/check.py           checks every file before an upload, and runs the IML tests
scripts/iml_tests.py       runs the app's IML with scripts/iml.py, a small IML evaluator
scripts/generate_interfaces.py  writes interfaces and samples from DocSpring's OpenAPI spec
```

Labels, descriptions, module types and visibility live only in Make; `app/UPLOAD.md` records them.

## Checks

Make runs the IML, so there's no test framework. Before an upload:

```bash
python3 scripts/check.py
```

It checks that every file is valid JSON with closed `{{ }}`, that nothing calls `/api/v1`, Make's URL and error
message limits, each module's sections, every `rpc://` reference, the groups, and that `app/UPLOAD.md` names every
module and RPC. It also runs `scripts/iml_tests.py`, which runs the app's own expressions (error messages, IDs in
URLs, no RPC inside an array item, the Watch events checks, detach) with a small IML evaluator, `scripts/iml.py`.

After a change to DocSpring's API v2 responses, regenerate the module outputs and samples from the docspring repo
checked out next to this one:

```bash
python3 scripts/generate_interfaces.py ../docspring/openapi/v2/openapi.json
```

## Requirements

- A Make API token with the SDK apps scopes, in `.env` (never committed), for the upload.
- A DocSpring test API token on our account for the live tests.

See `DESIGN.md` for how the app works and where it differs from the spec, and `CHANGELOG.md` for what changed.
