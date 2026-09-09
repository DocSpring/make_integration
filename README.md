# DocSpring Integration for Make.com

The DocSpring custom app for [Make.com](https://www.make.com) (formerly
Integromat — the platforms merged in 2022; there is no separate Integromat).

This is the Make counterpart to the Zapier integration
([`DocSpring/zapier_integration`](https://github.com/DocSpring/zapier_integration)).
The **design** (auth, endpoints, module set, field mapping) ports almost 1:1
from Zapier; the **implementation** is re-expressed in Make's declarative
**JSON + IML** (Integromat Markup Language) rather than Node.js. See
[`DESIGN.md`](./DESIGN.md) for the full port spec.

## Status

✅ **All modules built and validated** against the live DocSpring API (via the
Make API v2 — see `DESIGN.md` for the method). Confirmed working: the Connection,
**Find Template**, **Find Submission**, **Generate PDF**, **Combine PDFs**,
**Create Data Request**, **Create Signing Link**, and the **Watch Events** instant
trigger (attach → deliver → flatten → detach). Next: submit for Make app
verification to list it publicly.

Known follow-up: enum template fields render as free text (DocSpring still
validates the value); the dropdown fix needs a custom IML function, which requires
an "apps edit" token permission not currently granted. See `DESIGN.md`.

## Requirements

- A **Make account** (free tier is fine for building/testing a custom app).
- A DocSpring **API token** (region + token id + secret) for testing.
- The **Make Apps SDK** (`@makehq/sdk`, or the "Make Apps SDK" VS Code
  extension) to sync the local app definition to Make. The exact push
  mechanism (SDK vs Make API vs the web "Custom apps" editor) is confirmed
  during setup.

## Layout (once scaffolded)

Make apps are a set of JSON/IML files synced to the Make cloud:

```
makecomapp.json        # manifest: components + which remote app/version they map to
general/base           # base URL (per region) + Authorization header
connections/           # API-key connection (region, custom_host, token id/secret)
modules/               # actions + searches + instant triggers
webhooks/              # webhook attach/detach for the instant triggers
rpcs/                  # dynamic dropdowns + dynamic template-schema fields
functions/             # IML helper functions (payload flattening, schema mapping)
```
