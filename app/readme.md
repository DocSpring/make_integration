# DocSpring

[DocSpring](https://docspring.com) fills, generates and e-signs PDFs. Use these modules to generate PDFs from your templates with your data, combine PDFs, send signature requests, manage templates, fields and folders, and start scenarios when something happens in DocSpring.

## Connecting to DocSpring

You need a DocSpring **API token** (a token ID and a token secret):

1. Sign in to DocSpring and open **Settings → API Tokens**.
2. Create a token and copy its **Token ID** and **Token Secret**.
3. In Make, add a DocSpring connection and enter:
   - **Region**: where your DocSpring account is hosted: United States, Europe, or Self-hosted / Enterprise.
   - **Self-hosted host**: only for Self-hosted / Enterprise, such as `docspring.example.com`. Your server needs a DocSpring release with API v2.
   - **API Token ID** and **API Token Secret** from step 2.

Your token is sent over HTTPS and never written to execution logs. A test API token generates free test PDFs with a watermark.

## Modules

### PDFs

- **Generate a PDF**: fills a template's fields with your data and generates a PDF. Choose a template and version, and its fields appear as inputs. Waits until the PDF is ready, then returns the submission with its download URL.
- **Generate a batch of PDFs**: generates up to 50 PDFs in one request, from one template or several.
- **Get a submission batch**: returns a batch and each of its submissions.
- **Check data for a template**: checks your data against a template's fields without generating a PDF, and says what's wrong.
- **Combine PDFs**: merges PDFs from submissions, templates, other combined PDFs, custom files or URLs into one PDF.
- **Get a combined PDF**: returns a combined PDF by its ID.

### Submissions

- **Get a submission**: returns a submission by its ID, with its data and files.
- **Search submissions**: finds submissions by template, live or test mode, and when they were created.
- **Generate files for a submission**: generates more files for a submission, such as a PNG image of each page.
- **Expire a submission**: deletes a submission's data and files. This can't be undone.

### Signature requests

- **Create a signature request**: creates a submission that people fill in and sign. Add the signers (name, email, the fields each one fills in, and how they sign in), and choose the link type: an email link (7 days), an API link (24 hours) or none. Returns the submission and a signing link for each signer.
- **Create a signing link**: creates a new link to a signature request's signing form.
- **Get a signature request**: returns a signature request by its ID, with its signer and state.

### Templates

- **Search templates**, **Get a template**.
- **Create a template**: from a PDF (a URL or a file) or from HTML.
- **Replace a template's PDF**, **Copy a template**, **Move a template**, **Publish a template version**.
- **Get a template's page images**: an image of each page of a template's PDF.

### Template fields

- **List template fields**, **Add fields to a template**, **Update fields in a template**, **Remove fields from a template**. Changes go to the template's draft, which Publish a template version publishes.

### Folders

- **List folders**, **Create a folder**.

### Triggers

- **Watch events**: starts a scenario as soon as something happens in DocSpring. Choose the events (submissions created, processed, failed, declined, updated or expired; signature requests viewed, completed, declined or updated; combined PDFs processed, failed or expired; batches processed or failed; templates created, updated or deleted; custom files created; folders created, updated or deleted), live or test mode, and optionally the templates to watch (for submission, signature request and template events). Each event has `event_type`, `resource_type`, `resource_id` and the record in `data`.

### Other

- **Make an API call**: calls any DocSpring API endpoint the other modules don't cover. Enter a path after `/api/v2`, such as `/templates`; authentication is added for you.

## Learn more

- [DocSpring documentation](https://docspring.com/docs)
- [DocSpring website](https://docspring.com)
