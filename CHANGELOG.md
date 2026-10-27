# Changelog

The app's version in Make stays 1: Make changes a public app in place.

## API v2 (sc-5981, uploaded 27 Oct 2026)

The app now calls DocSpring API v2 (`/api/v2`) for everything, and adds the full set of operations.

**Self-hosted DocSpring servers need a release with API v2.** On an older server the connection test fails with
"This DocSpring server doesn't have API v2 yet. Upgrade it to the latest release to use this app."

### Changed

- Every module calls API v2 and returns the v2 resource as the API returns it.
- Errors read `DocSpring API error <status> <code>: <message>`, with a line per invalid field, the record's ID and
  the request ID. A PDF that fails (or a template whose PDF can't be read) is an error naming its state.
- Every request sends the User-Agent `docspring-make/2`.
- Template fields are typed inputs (boolean, number, text or JSON) in a "Template fields" collection, for the chosen
  template version. Date fields take `YYYY-MM-DD`.
- The template and folder pickers page through every template and folder (up to 1,000).
- Watch events uses version 4 webhooks: each event has `id`, `event_type`, `created_at` and `data` (the v2 record),
  plus `resource_type` and `resource_id`. It offers every API v2 event and can be limited to templates.
- Search submissions and Search templates use cursor paging up to their Limit.
- Labels are in sentence case.
- IDs in URL paths are encoded, and an ID of `.` or `..` fails before any request.
- Error details that contain quotes keep their text, such as a dropdown's options:
  `/data/colour: must be one of: "Red", "Blue"`.
- Create a signature request and Check data for a template: a signer's Fields is a list of field names to type or map,
  whole (`address/street`, not `address`), as List template fields shows them. Make can't fill a picker inside the
  Signers list from the module's template.
- Watch events: with templates chosen, events that can't be limited to templates (combined PDF, batch, custom file
  and folder events) fail before the webhook is created, naming those events. Deleting a hook finds its DocSpring
  webhook past the first 100.
- Remove fields from a template sends field IDs typed in Map mode as numbers.

### Renamed

- **Create data request** is **Create a signature request**, a new module (`createSignatureRequest`). It takes signers
  (name, email, fields, role, authentication), and creates a signing link for each (email, 7 days; API, 24 hours; or
  none). The old `createDataRequest` module is removed, or hidden and deprecated if Make keeps it.
- Data requests are signature requests, and combined submissions are combined PDFs, in every input and output.
- Create a signing link: email links last 7 days, API links 24 hours.

### Added

- PDFs: Generate a batch of PDFs, Get a submission batch, Check data for a template, Get a combined PDF.
- Submissions: Get a submission, Generate files for a submission, Expire a submission.
- Signature requests: Get a signature request.
- Templates: Get a template, Create a template, Replace a template's PDF, Copy a template, Move a template, Publish
  template version, Get a template's page images.
- Template fields: List template fields, Add fields to a template, Update fields in a template, Remove fields from a
  template.
- Folders: List folders, Create a folder.
- Watch events: signature request declined and updated, submission declined and updated, combined PDF expired,
  custom file created, and folder created, updated and deleted.

## 1 (September 2026)

The first version, on API v1: Generate PDF, Combine PDFs, Create data request, Create signing link, Find template,
Find submission, Watch events and Make an API call.
