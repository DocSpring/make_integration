# DocSpring

[DocSpring](https://docspring.com) turns structured data into filled, downloadable, and **signable** PDFs. Use these modules to generate PDFs from your templates, merge documents, request data or signatures from other people, and react to DocSpring events as they happen.

## Connecting to DocSpring

To create a connection you need a **DocSpring API token** (a Token ID and Token Secret):

1. Sign in to DocSpring and open **Settings → API Tokens**.
2. Create a token and copy the **Token ID** and **Token Secret**.
3. In Make, add a DocSpring connection and enter:
   - **Region** — where your DocSpring account is hosted: United States, Europe, Australia, or **Self-hosted / Enterprise**.
   - **Self-hosted Host** — only for the Self-hosted / Enterprise region, e.g. `docspring.example.com`.
   - **API Token ID** and **API Token Secret** from step 2.

Your credentials are sent as HTTP Basic authentication over HTTPS and are never written to execution logs.

## Modules

### Actions

- **Generate PDF** — Fill a template's fields and generate a finished PDF. Choose a template, then fill the fields defined by that template (they appear automatically). Optionally generate a watermarked **test** PDF, encrypt it with a passphrase, or set an expiry. Returns the submission ID, state, and download URLs.
- **Combine PDFs** — Merge several PDFs into a single document. Add one or more **Source PDFs**, each referencing a submission, a template, or a custom file by ID. Returns the combined submission ID and download URL.
- **Create Data Request** — Create a submission that waits for one or more people to fill out and/or sign it. Choose a template and add **recipients** (email, name, the fields each person may edit, and an authentication method). Returns a submission in the `waiting_for_data_requests` state along with a data request for each recipient. Follow it with **Create Signing Link** to send people their link.
- **Create Signing Link** — Generate an authenticated link a recipient can use to complete their data request. Provide the **Data Request ID** from *Create Data Request* and choose a link type (an email link that lasts 30 days, or a short-lived API link). Returns the signing URL.

### Searches

- **Find Template** — Look up templates by name or ID.
- **Find Submission** — Look up a single submission by ID, or list recent submissions filtered by mode (live/test) and creation date.

### Triggers

- **Watch Events** — Starts a scenario the moment a DocSpring event occurs. Choose which events to watch — submission processed / failed / created / expired, data request completed / viewed, combined submission processed / failed, submission batch processed / failed, and template created / updated / deleted — and optionally limit to live or test mode. DocSpring delivers each event to Make as it happens.

### Universal

- **Make an API Call** — Perform an authorized call to any DocSpring API endpoint that the other modules don't cover. Enter a path relative to the API base (for example `/templates`), a method, and optional query string, headers, and body. Authentication is added for you.

## Learn more

- [DocSpring documentation](https://docspring.com/docs)
- [DocSpring website](https://docspring.com)
