# Changelog

The app's version in Make stays 1: Make changes a public app in place.

## API v2 (sc-5981, not uploaded yet)

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
- Find submissions and Find templates use cursor paging up to their Limit.
- Labels are in sentence case.

### Renamed

- **Create data request** is **Create signature request**, a new module (`createSignatureRequest`). It takes signers
  (name, email, fields, role, authentication), and creates a signing link for each (email, 7 days; API, 24 hours; or
  none). The old `createDataRequest` module is removed, or hidden and deprecated if Make keeps it.
- Data requests are signature requests, and combined submissions are combined PDFs, in every input and output.
- Create signing link: email links last 7 days, API links 24 hours.

### Added

- PDFs: Generate PDFs in a batch, Get submission batch, Check data, Get combined PDF.
- Submissions: Get submission, Generate submission files, Expire submission.
- Signature requests: Get signature request.
- Templates: Get template, Create template, Replace template PDF, Copy template, Move template, Publish template
  version, Get template page images.
- Template fields: List template fields, Add template fields, Update template fields, Remove template fields.
- Folders: List folders, Create folder.
- Watch events: signature request declined and updated, submission declined and updated, combined PDF expired,
  custom file created, and folder created, updated and deleted.

## 1 (September 2026)

The first version, on API v1: Generate PDF, Combine PDFs, Create data request, Create signing link, Find template,
Find submission, Watch events and Make an API call.
