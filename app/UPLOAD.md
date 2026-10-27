# Uploading the app to Make

How to put this repo's app into Make with the Make API (the SDK Apps endpoints), one component at a time. Nothing
here has been uploaded yet: the API v2 version (sc-5981) is files only until someone runs these steps with a Make API
token.

The app is `docspring-sspkqt`, version 1, in Make's US2 zone (`APP.md`). It's public, and only apps Make has approved
get versioned releases, so **every change is live at once in every scenario that uses it**. Make won't delete a
module or other component once an app is published. Nobody uses the app yet, so the modules change in place.

Labels, descriptions, module types, `crud`, connection and webhook bindings and visibility live only in Make, not in
the IML files. This guide is where the repo records them.

## Before you start

You need a Make API token with the SDK apps scopes (`sdk-apps:read`, `sdk-apps:write`), in `.env` (never committed):

```bash
MAKE_API_TOKEN=...
MAKE_API_BASE=https://us2.make.com/api/v2
MAKE_APP=docspring-sspkqt
MAKE_CONNECTION=docspring-sspkqt
```

Load it and define a helper. Every call below is `mk <METHOD> <path> [file]`, with the path after `/sdk/apps`:

```bash
set -a; . ./.env; set +a
V=1
mk() {
  local method=$1 path=$2 file=$3 type=${4:-application/json}
  if [ -n "$file" ]; then
    curl -sS -X "$method" -H "Authorization: Token $MAKE_API_TOKEN" -H "Content-Type: $type" \
      --data-binary @"$file" "$MAKE_API_BASE/sdk/apps$path"
  else
    curl -sS -X "$method" -H "Authorization: Token $MAKE_API_TOKEN" -H "Content-Type: $type" \
      ${BODY:+--data "$BODY"} "$MAKE_API_BASE/sdk/apps$path"
  fi
  echo
}
```

Run `scripts/check.py` first. It checks that every file is valid JSON and that this guide names every module and RPC.

Recommended: run every step against a testing app first (create an empty app in Make, such as "DocSpring Testing",
set `MAKE_APP` to its name, create its connection with `POST /{app}/connections` and set `MAKE_CONNECTION` to that
connection's name, then create its RPCs, webhook and modules as below), test it (see
[Testing](#testing)), then run the same steps against `docspring-sspkqt`.

## 1. Read what's in Make now

```bash
mk GET "/$MAKE_APP/$V/modules"        # module IDs, labels, types, visibility
mk GET "/$MAKE_APP/$V/rpcs"           # listTemplates and templateFields exist today
mk GET "/$MAKE_APP/webhooks"          # the Watch events webhook's name
mk GET "/$MAKE_APP/connections"       # docspring-sspkqt
```

Set `WEBHOOK` to the webhook's name from that list (the repo never recorded it), and check which webhook
`watchEvents` uses:

```bash
WEBHOOK=<name from the list>
mk GET "/$MAKE_APP/$V/modules/watchEvents"
mk GET "/webhooks/$WEBHOOK/attach"     # the live attach; it may still read body.uid (see below)
```

If the live attach reads `body.uid`, hooks attached with it have no stored webhook ID, and their DocSpring webhooks
can't be detached by Make: delete them in DocSpring (Settings > Webhooks, named "Make") once the new attach is up.

## 2. Connection

The connection keeps its name, type (basic) and parameters' names, so existing connections keep working.

| Section | Method + path | File |
|---|---|---|
| api | `PUT /connections/docspring-sspkqt/api` | `app/connections/api.imljson` |
| parameters | `PUT /connections/docspring-sspkqt/parameters` | `app/connections/parameters.imljson` |

```bash
mk PUT "/connections/$MAKE_CONNECTION/api" app/connections/api.imljson
mk PUT "/connections/$MAKE_CONNECTION/parameters" app/connections/parameters.imljson
```

## 3. Base

| Section | Method + path | File |
|---|---|---|
| base | `POST /{app}/{version}/base` (Set App Base) | `app/base.imljson` |

```bash
mk POST "/$MAKE_APP/$V/base" app/base.imljson
```

## 4. RPCs

Every RPC uses the connection `docspring-sspkqt`, like the modules that call it. Create the new ones, then set each
one's `api` section (`PUT /{app}/{version}/rpcs/{rpc}/api`). None has a `parameters` section.

| Make ID | Label | Connection | In Make today | File |
|---|---|---|---|---|
| `listTemplates` | List templates | `docspring-sspkqt` | changed | `app/rpcs/listTemplates.imljson` |
| `listFolders` | List folders | `docspring-sspkqt` | new | `app/rpcs/listFolders.imljson` |
| `templateFields` | Template fields | `docspring-sspkqt` | changed | `app/rpcs/templateFields.imljson` |
| `templateFieldNames` | Template field names | `docspring-sspkqt` | new | `app/rpcs/templateFieldNames.imljson` |
| `templateFieldIds` | Template field IDs | `docspring-sspkqt` | new | `app/rpcs/templateFieldIds.imljson` |

```bash
# Create the new RPCs: POST /{app}/{version}/rpcs
for rpc in "listFolders:List folders" "templateFieldNames:Template field names" "templateFieldIds:Template field IDs"; do
  BODY="{\"name\": \"${rpc%%:*}\", \"label\": \"${rpc#*:}\", \"connection\": \"$MAKE_CONNECTION\"}" \
    mk POST "/$MAKE_APP/$V/rpcs"
done
# Set each RPC's code: PUT /{app}/{version}/rpcs/{rpc}/api
for f in app/rpcs/*.imljson; do
  rpc=$(basename "$f" .imljson)
  mk PUT "/$MAKE_APP/$V/rpcs/$rpc/api" "$f"
done
```

## 5. Webhook

The Watch events webhook stays the same component (a dedicated webhook with attach and detach, bound to the
connection `docspring-sspkqt`); its sections change.

| Section | Method + path | File |
|---|---|---|
| api (incoming events) | `PUT /webhooks/{webhook}/api` | `app/webhooks/api.imljson` |
| parameters | `PUT /webhooks/{webhook}/parameters` | `app/webhooks/parameters.imljson` |
| attach | `PUT /webhooks/{webhook}/attach` | `app/webhooks/attach.imljson` |
| detach | `PUT /webhooks/{webhook}/detach` | `app/webhooks/detach.imljson` |

```bash
for s in api parameters attach detach; do
  mk PUT "/webhooks/$WEBHOOK/$s" "app/webhooks/$s.imljson"
done
```

Hooks that already exist keep the version 3 DocSpring webhook they were attached with, and its events now arrive in a
version 3 shape the new `api` section doesn't read. Delete and re-create any such hook in Make (or its scenario's
trigger) after this step.

## 6. Modules

Every module except `watchEvents` uses the connection `docspring-sspkqt`. `watchEvents` uses the webhook from step 5.
Every module is public (visible) once its sections are in.

| Make ID | Type (`typeId`) | Label | Description | `crud` | Binding | In Make today |
|---|---|---|---|---|---|---|
| `generatePdf` | Action (4) | Generate PDF | Generates a PDF from a template with your data, and waits until it's ready. | create | connection `docspring-sspkqt` | changed |
| `generatePdfBatch` | Action (4) | Generate PDFs in a batch | Generates up to 50 PDFs in one request, and waits until they're ready. | create | connection `docspring-sspkqt` | new |
| `getSubmissionBatch` | Action (4) | Get submission batch | Returns a batch of submissions by its ID, with each submission's state and files. | read | connection `docspring-sspkqt` | new |
| `checkData` | Action (4) | Check data | Checks data against a template's fields without generating a PDF, and returns whether it's valid and why not. | read | connection `docspring-sspkqt` | new |
| `combinePdfs` | Action (4) | Combine PDFs | Merges PDFs from submissions, templates, combined PDFs, custom files or URLs into one PDF. | create | connection `docspring-sspkqt` | changed |
| `getCombinedPdf` | Action (4) | Get combined PDF | Returns a combined PDF by its ID, with its state and files. | read | connection `docspring-sspkqt` | new |
| `getSubmission` | Action (4) | Get submission | Returns a submission by its ID, with its data and files. | read | connection `docspring-sspkqt` | new |
| `findSubmission` | Search (9) | Find submissions | Finds submissions by template, live or test mode and when they were created. | - | connection `docspring-sspkqt` | changed |
| `generateSubmissionFiles` | Action (4) | Generate submission files | Generates more files for a submission, such as a PNG image of each page. | update | connection `docspring-sspkqt` | new |
| `expireSubmission` | Action (4) | Expire submission | Expires a submission, which deletes its data and files. This action cannot be undone. | delete | connection `docspring-sspkqt` | new |
| `createSignatureRequest` | Action (4) | Create signature request | Creates a submission that people fill in and sign, and a signing link for each signer. | create | connection `docspring-sspkqt` | new (replaces `createDataRequest`) |
| `createSigningLink` | Action (4) | Create signing link | Creates a link that opens a signature request's signing form. | create | connection `docspring-sspkqt` | changed |
| `getSignatureRequest` | Action (4) | Get signature request | Returns a signature request by its ID, with its signer and state. | read | connection `docspring-sspkqt` | new |
| `findTemplate` | Search (9) | Find templates | Finds templates by name and folder. | - | connection `docspring-sspkqt` | changed |
| `getTemplate` | Action (4) | Get template | Returns a template by its ID, with its settings and published versions. | read | connection `docspring-sspkqt` | new |
| `createTemplate` | Action (4) | Create template | Creates a template from a PDF (a URL or a file) or from HTML. | create | connection `docspring-sspkqt` | new |
| `replaceTemplatePdf` | Action (4) | Replace template PDF | Replaces a template's PDF with a new one from a URL or a file. | update | connection `docspring-sspkqt` | new |
| `copyTemplate` | Action (4) | Copy template | Copies a template, or one of its published versions. | create | connection `docspring-sspkqt` | new |
| `moveTemplate` | Action (4) | Move template | Moves a template and its published versions to a folder. | update | connection `docspring-sspkqt` | new |
| `publishTemplateVersion` | Action (4) | Publish template version | Publishes a template's draft as a new version. | create | connection `docspring-sspkqt` | new |
| `getTemplatePageImages` | Action (4) | Get template page images | Returns an image of each page of a template's PDF. | read | connection `docspring-sspkqt` | new |
| `listTemplateFields` | Search (9) | List template fields | Lists a template's fields with all their settings. | - | connection `docspring-sspkqt` | new |
| `addTemplateFields` | Action (4) | Add template fields | Adds fields to a template's draft. | update | connection `docspring-sspkqt` | new |
| `updateTemplateFields` | Action (4) | Update template fields | Updates fields of a template's draft by their IDs. | update | connection `docspring-sspkqt` | new |
| `removeTemplateFields` | Action (4) | Remove template fields | Removes fields from a template's draft. | delete | connection `docspring-sspkqt` | new |
| `listFolders` | Search (9) | List folders | Lists all folders, or the folders in one folder. | - | connection `docspring-sspkqt` | new |
| `createFolder` | Action (4) | Create folder | Creates a folder. | create | connection `docspring-sspkqt` | new |
| `watchEvents` | Instant trigger (10) | Watch events | Triggers when an event occurs in DocSpring, such as a PDF being generated or a signature request being completed. | - | webhook `$WEBHOOK` | changed |
| `makeApiCall` | Universal (12) | Make an API call | Performs an arbitrary authorized API call. | - | connection `docspring-sspkqt` | changed |

The labels are the sc-5981 spec's labels in sentence case, which Make's naming conventions ask for. The descriptions
follow Make's third-person style. `watchEvents` is bound to the webhook from step 5 (`"webhook": "$WEBHOOK"` when
creating it), not to a connection.

This prints a request body per module from the table above, so the table is the only list:

```bash
module_bodies() {  # module_bodies new|changed
  python3 - "$1" "$MAKE_CONNECTION" <<'EOF'
import json, sys
want, connection = sys.argv[1], sys.argv[2]
types = {"Action (4)": 4, "Search (9)": 9, "Instant trigger (10)": 10, "Universal (12)": 12}
for line in open("app/UPLOAD.md"):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) != 7 or not cells[0].startswith("`") or not cells[6].startswith(want):
        continue
    body = {"name": cells[0].strip("`"), "typeId": types[cells[1]], "label": cells[2], "description": cells[3]}
    if cells[4] != "-":
        body["crud"] = cells[4]
    if body["typeId"] != 10:
        body["connection"] = connection
    print(json.dumps(body))
EOF
}
```

**Create each new module** with `POST /{app}/{version}/modules` (Create Module). Its `crud` can only be set here:
Patch Module changes only the label, description and connection. Searches and the universal module have no `crud`.

```bash
module_bodies new | while IFS= read -r body; do BODY=$body mk POST "/$MAKE_APP/$V/modules"; done
```

**Relabel each changed module** with `PATCH /{app}/{version}/modules/{module}` (Patch Module), which takes only the
label, description and connection:

```bash
module_bodies changed | while IFS= read -r body; do
  m=$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["name"])' "$body")
  BODY=$(python3 -c 'import json,sys; b=json.loads(sys.argv[1]); print(json.dumps({k: b[k] for k in ("label", "description")}))' "$body") \
    mk PATCH "/$MAKE_APP/$V/modules/$m"
done
```

**Set every module's sections** with `PUT /{app}/{version}/modules/{module}/{section}` (Set Module Section), for
each file in its folder. The sections are `api` (communication), `expect` (mappable parameters), `interface` (output)
and `samples`; `watchEvents` has only `interface` and `samples`. No module has static `parameters`, `scope` or
`epoch`.

```bash
for dir in app/modules/*/; do
  m=$(basename "$dir")
  for f in "$dir"*.imljson; do
    mk PUT "/$MAKE_APP/$V/modules/$m/$(basename "$f" .imljson)" "$f"
  done
done
```

**Make every module visible** with `POST /{app}/{version}/modules/{module}/public` (Set Module Visibility):

```bash
for dir in app/modules/*/; do mk POST "/$MAKE_APP/$V/modules/$(basename "$dir")/public"; done
```

## 7. The old `createDataRequest` module

Create signature request has a new module ID, `createSignatureRequest`. The old `createDataRequest` module has no
folder in this repo any more. Make doesn't delete a module from a published app, so:

1. Try `DELETE /{app}/{version}/modules/createDataRequest` (Delete Module). If Make deletes it, you're done.
2. If Make refuses, replace its code with the new module's, so nothing calls API v1, then hide and deprecate it:

```bash
for s in api expect interface samples; do
  mk PUT "/$MAKE_APP/$V/modules/createDataRequest/$s" "app/modules/createSignatureRequest/$s.imljson"
done
BODY='{"label": "Create signature request (deprecated)", "description": "Use Create signature request instead."}' \
  mk PATCH "/$MAKE_APP/$V/modules/createDataRequest"
mk POST "/$MAKE_APP/$V/modules/createDataRequest/private"     # hidden from new scenarios
mk POST "/$MAKE_APP/$V/modules/createDataRequest/deprecate"
```

## 8. Groups and the app's readme

| Section | Method + path | File |
|---|---|---|
| groups | `PUT /{app}/{version}/groups` | `app/groups.imljson` |
| readme (the listing's documentation) | `PUT /{app}/{version}/readme` (`text/markdown`) | `app/readme.md` |

```bash
mk PUT "/$MAKE_APP/$V/groups" app/groups.imljson
mk PUT "/$MAKE_APP/$V/readme" app/readme.md text/markdown
```

The icon (`app/icon.png`, `PUT /{app}/{version}/icon`) hasn't changed.

## Testing

With a DocSpring **test** API token on our own account (test PDFs are free), in a Make scenario:

- The connection: a valid token connects; a wrong secret says the token isn't valid.
- Each module once. Generate PDF and Check data with a template that has a date, a number, a checkbox and an image
  field: the Template fields collection shows typed inputs (date fields as text asking for YYYY-MM-DD).
- Create signature request with two signers: one link per signer in Signing links, and `first_signing_url`.
- An error: Generate PDF with a wrong value for a field. The message reads
  `DocSpring API error 422 invalid_data: ...`, a line per field, `Submission: sub_...` and `Request ID: req_...`.
- Watch events: create a hook (DocSpring gets a version 4 webhook named "Make"), generate a test PDF (the scenario
  runs with `event_type`, `resource_type` and `resource_id`), delete the hook (the DocSpring webhook is deleted).
  Then create a hook, delete its webhook in DocSpring, and delete the hook: Make should delete it without an error.

Make behaviour these files rely on that hasn't been tried yet (each is from Make's documentation):

- `templateFields` uses `toArray()` and a `wrapper` to put the fields in one collection, and reads `body.required`
  while iterating. If the collection doesn't appear, the fallback is the old flat list: iterate
  `keys(body.properties)` without the wrapper, and build `data` with `omit(parameters; ...)` in the modules.
- `createSignatureRequest` runs three requests: the submission, a token request that `repeat`s once per signature
  request (reading the next ID from `temp`), and a request-less output.
- The base error message uses `replace()` with regular expressions and `decodeURL('%0A')` for line breaks. If
  Make doesn't read the regular expressions, the details show as JSON instead (still readable).
- `detach` makes two requests: it lists the webhooks with the hook's first event and deletes the webhook only if
  it's in the list.
- A select's `placeholder` (Move template's "Root folder (/)"), and `null` from `ifempty(...; null)` for the root.
- Modules give up after Make's 40-second timeout (Make's default). A PDF that takes longer fails in Make, not with
  DocSpring's 504; turning off Wait for the PDF avoids it. Make support can raise the timeout for an app.
