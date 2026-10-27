# Uploading the app to Make

How to put this repo's app into Make with the Make API (the SDK Apps endpoints), one component at a time. The API v2
version (sc-5981) was uploaded to the live app with these steps on 27 Oct 2026 and tested live, then its 29 modules
were made public.

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

`names` prints the name of each component Make lists at a path, one per line. The steps below use it to create what's
missing and update what's there, so the same steps work on the live app and on an empty testing app:

```bash
names() {  # names <path>
  mk GET "$1" | python3 -c 'import json, sys
for value in json.load(sys.stdin).values():
    if isinstance(value, list):
        print("\n".join(item["name"] for item in value))'
}
```

Run `scripts/check.py` first. It checks every file, runs the IML tests and checks that this guide names every module
and RPC.

### A testing app first (recommended)

Run every step against a testing app first, test it (see [Testing](#testing)), then run the same steps against
`docspring-sspkqt`:

1. Create an empty app in Make (Custom apps > Create a new app), such as "DocSpring Testing", and set `MAKE_APP` to
   its name. Check that its manifest version is 2 like the live app's (`mk GET "/$MAKE_APP/$V"`, `manifestVersion`):
   the modules rely on manifest 2 leaving empty inputs out of requests.
2. Create its connection (basic, like the live one) and set `MAKE_CONNECTION` to the name Make gives it:

```bash
MAKE_CONNECTION=$(BODY='{"type": "basic", "label": "DocSpring"}' mk POST "/$MAKE_APP/connections" |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["appConnection"]["name"])')
echo "$MAKE_CONNECTION"
```

3. Follow steps 1 to 6 and 8. Step 7 is only for the live app.

## 1. Read what's in Make now

```bash
mk GET "/$MAKE_APP/$V/modules"        # module IDs, labels, types, visibility
mk GET "/$MAKE_APP/$V/rpcs"           # in the live app: listTemplates and templateFields
mk GET "/$MAKE_APP/webhooks"          # the Watch events webhook
mk GET "/$MAKE_APP/connections"       # in the live app: docspring-sspkqt
```

Set `WEBHOOK` to the Watch events webhook's name. In the live app it's `docspring-sspkqt` (Make named it after the
app when it was created, in September 2026); check it in the list. A new testing app has no webhook yet: leave
`WEBHOOK` empty and step 5 creates one.

```bash
WEBHOOK=$(names "/$MAKE_APP/webhooks")   # one name; empty in a new app
echo "$WEBHOOK"   # more than one name: set WEBHOOK to the one watchEvents uses
```

In the live app, check that `watchEvents` uses that webhook, and read the live attach:

```bash
mk GET "/$MAKE_APP/$V/modules/watchEvents"
mk GET "/webhooks/$WEBHOOK/attach"     # it may still read body.uid (see below)
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
| base | `PUT /{app}/{version}/base` (Set App Section) | `app/base.imljson` |

```bash
mk PUT "/$MAKE_APP/$V/base" app/base.imljson
```

## 4. RPCs

Every RPC uses the app's connection (`docspring-sspkqt` in the live app), like the modules that call it. The script
creates each RPC Make doesn't list (`POST /{app}/{version}/rpcs`), then sets every RPC's `api` section
(`PUT /{app}/{version}/rpcs/{rpc}/api`). None has a `parameters` section.

| Make ID | Label | Connection | In the live app | File |
|---|---|---|---|---|
| `listTemplates` | List templates | `docspring-sspkqt` | changed | `app/rpcs/listTemplates.imljson` |
| `listFolders` | List folders | `docspring-sspkqt` | new | `app/rpcs/listFolders.imljson` |
| `templateFields` | Template fields | `docspring-sspkqt` | changed | `app/rpcs/templateFields.imljson` |
| `templateFieldIds` | Template field IDs | `docspring-sspkqt` | new | `app/rpcs/templateFieldIds.imljson` |

```bash
RPCS=$(names "/$MAKE_APP/$V/rpcs")
python3 - "$MAKE_CONNECTION" <<'EOF' | while IFS=$'\t' read -r rpc body; do
import json, sys
for line in open("app/UPLOAD.md"):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) == 5 and cells[0].startswith("`") and cells[4].startswith("`app/rpcs/"):
        name = cells[0].strip("`")
        print(name, json.dumps({"name": name, "label": cells[1], "connection": sys.argv[1]}), sep="\t")
EOF
  grep -qx "$rpc" <<<"$RPCS" || BODY=$body mk POST "/$MAKE_APP/$V/rpcs" </dev/null
  mk PUT "/$MAKE_APP/$V/rpcs/$rpc/api" "app/rpcs/$rpc.imljson" </dev/null
done
```

## 5. Webhook

The Watch events webhook stays the same component in the live app (a dedicated webhook with attach and detach,
bound to the connection `docspring-sspkqt`); its sections change. In a new app there's none yet, so this creates a
dedicated webhook (type `web`, as the live one was created) on the app's connection, and Make names it:

```bash
if [ -z "$WEBHOOK" ]; then
  WEBHOOK=$(BODY="{\"label\": \"DocSpring events\", \"type\": \"web\", \"connection\": \"$MAKE_CONNECTION\"}" \
    mk POST "/$MAKE_APP/webhooks" | python3 -c 'import json, sys; print(json.load(sys.stdin)["appWebhook"]["name"])')
fi
echo "$WEBHOOK"
```

Then set its sections:

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
trigger) after this step. On 27 Oct 2026 our September test scenario got a new hook this way, and deleting its old
hook deleted the version 3 webhook in DocSpring.

## 6. Modules

Every module except `watchEvents` uses the app's connection (`docspring-sspkqt` in the live app). `watchEvents` uses
the webhook from step 5. Every module is public (visible) once its sections are in.

| Make ID | Type (`typeId`) | Label | Description | `crud` | Binding | In the live app |
|---|---|---|---|---|---|---|
| `generatePdf` | Action (4) | Generate a PDF | Generates a PDF from a template with your data, and waits until it's ready. | create | connection `docspring-sspkqt` | changed |
| `generatePdfBatch` | Action (4) | Generate a batch of PDFs | Generates up to 50 PDFs in one request, and waits until they're ready. | create | connection `docspring-sspkqt` | new |
| `getSubmissionBatch` | Action (4) | Get a submission batch | Returns a batch of submissions by its ID, with each submission's state and files. | read | connection `docspring-sspkqt` | new |
| `checkData` | Action (4) | Check data for a template | Checks data against a template's fields without generating a PDF, and returns whether it's valid and why not. | read | connection `docspring-sspkqt` | new |
| `combinePdfs` | Action (4) | Combine PDFs | Merges PDFs from submissions, templates, combined PDFs, custom files or URLs into one PDF. | create | connection `docspring-sspkqt` | changed |
| `getCombinedPdf` | Action (4) | Get a combined PDF | Returns a combined PDF by its ID, with its state and files. | read | connection `docspring-sspkqt` | new |
| `getSubmission` | Action (4) | Get a submission | Returns a submission by its ID, with its data and files. | read | connection `docspring-sspkqt` | new |
| `findSubmission` | Search (9) | Search submissions | Finds submissions by template, live or test mode and when they were created. | - | connection `docspring-sspkqt` | changed |
| `generateSubmissionFiles` | Action (4) | Generate files for a submission | Generates more files for a submission, such as a PNG image of each page. | update | connection `docspring-sspkqt` | new |
| `expireSubmission` | Action (4) | Expire a submission | Expires a submission, which deletes its data and files. This action cannot be undone. | delete | connection `docspring-sspkqt` | new |
| `createSignatureRequest` | Action (4) | Create a signature request | Creates a submission that people fill in and sign, and a signing link for each signer. | create | connection `docspring-sspkqt` | new (replaces `createDataRequest`) |
| `createSigningLink` | Action (4) | Create a signing link | Creates a link that opens a signature request's signing form. | create | connection `docspring-sspkqt` | changed |
| `getSignatureRequest` | Action (4) | Get a signature request | Returns a signature request by its ID, with its signer and state. | read | connection `docspring-sspkqt` | new |
| `findTemplate` | Search (9) | Search templates | Finds templates by name and folder. | - | connection `docspring-sspkqt` | changed |
| `getTemplate` | Action (4) | Get a template | Returns a template by its ID, with its settings and published versions. | read | connection `docspring-sspkqt` | new |
| `createTemplate` | Action (4) | Create a template | Creates a template from a PDF (a URL or a file) or from HTML. | create | connection `docspring-sspkqt` | new |
| `replaceTemplatePdf` | Action (4) | Replace a template's PDF | Replaces a template's PDF with a new one from a URL or a file. | update | connection `docspring-sspkqt` | new |
| `copyTemplate` | Action (4) | Copy a template | Copies a template, or one of its published versions. | create | connection `docspring-sspkqt` | new |
| `moveTemplate` | Action (4) | Move a template | Moves a template and its published versions to a folder. | update | connection `docspring-sspkqt` | new |
| `publishTemplateVersion` | Action (4) | Publish a template version | Publishes a template's draft as a new version. | create | connection `docspring-sspkqt` | new |
| `getTemplatePageImages` | Action (4) | Get a template's page images | Returns an image of each page of a template's PDF. | read | connection `docspring-sspkqt` | new |
| `listTemplateFields` | Search (9) | List template fields | Lists a template's fields with all their settings. | - | connection `docspring-sspkqt` | new |
| `addTemplateFields` | Action (4) | Add fields to a template | Adds fields to a template's draft. | update | connection `docspring-sspkqt` | new |
| `updateTemplateFields` | Action (4) | Update fields in a template | Updates fields of a template's draft by their IDs. | update | connection `docspring-sspkqt` | new |
| `removeTemplateFields` | Action (4) | Remove fields from a template | Removes fields from a template's draft. | delete | connection `docspring-sspkqt` | new |
| `listFolders` | Search (9) | List folders | Lists all folders, or the folders in one folder. | - | connection `docspring-sspkqt` | new |
| `createFolder` | Action (4) | Create a folder | Creates a folder. | create | connection `docspring-sspkqt` | new |
| `watchEvents` | Instant trigger (10) | Watch events | Triggers when an event occurs in DocSpring, such as a PDF being generated or a signature request being completed. | - | webhook `$WEBHOOK` | changed |
| `makeApiCall` | Universal (12) | Make an API call | Performs an arbitrary authorized API call. | - | connection `docspring-sspkqt` | changed |

The labels are the sc-5981 spec's labels in sentence case, which Make's naming conventions ask for. The descriptions
follow Make's third-person style. `watchEvents` is bound to the webhook from step 5 (`"webhook": "$WEBHOOK"` when
creating it), not to a connection.

This prints each module's name and request body from the table above, so the table is the only list:

```bash
module_bodies() {
  python3 - "$MAKE_CONNECTION" "$WEBHOOK" <<'EOF'
import json, sys
connection, webhook = sys.argv[1], sys.argv[2]
types = {"Action (4)": 4, "Search (9)": 9, "Instant trigger (10)": 10, "Universal (12)": 12}
for line in open("app/UPLOAD.md"):
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if len(cells) != 7 or not cells[0].startswith("`") or cells[1] not in types:
        continue
    body = {"name": cells[0].strip("`"), "typeId": types[cells[1]], "label": cells[2], "description": cells[3]}
    if cells[4] != "-":
        body["crud"] = cells[4]
    if body["typeId"] == 10:
        if not webhook:
            sys.exit("Set WEBHOOK first (steps 1 and 5)")
        body["webhook"] = webhook
    else:
        body["connection"] = connection
    print(body["name"], json.dumps(body), sep="\t")
EOF
}
```

**Create each module Make doesn't list** with `POST /{app}/{version}/modules` (Create Module), and **relabel each one
it does** with `PATCH /{app}/{version}/modules/{module}` (Patch Module). Patch Module changes only the label,
description and connection, so a module's type, `crud` and webhook can only be set when it's created. Searches and
the universal module have no `crud`.

```bash
MODULES=$(names "/$MAKE_APP/$V/modules")
module_bodies | while IFS=$'\t' read -r m body; do
  if grep -qx "$m" <<<"$MODULES"; then
    BODY=$(python3 -c 'import json, sys; b = json.loads(sys.argv[1]); print(json.dumps({k: b[k] for k in ("label", "description")}))' "$body") \
      mk PATCH "/$MAKE_APP/$V/modules/$m" </dev/null
  else
    BODY=$body mk POST "/$MAKE_APP/$V/modules" </dev/null
  fi
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

Create a signature request has a new module ID, `createSignatureRequest`. The old `createDataRequest` module has no
folder in this repo any more. Make doesn't delete a module from a published app, so:

1. Try `DELETE /{app}/{version}/modules/createDataRequest` (Delete Module). If Make deletes it, you're done.
2. If Make refuses, replace its code with the new module's, so nothing calls API v1, then hide and deprecate it. On 27
   Oct 2026 Make refused (`IM016`, "Module used in scenarios": a September test scenario in our team used it). Once
   that scenario used the new module, Make still refused (`IM005`, "Can't delete module from public app"), so the live
   app's `createDataRequest` stays this hidden, deprecated copy:

```bash
for s in api expect interface samples; do
  mk PUT "/$MAKE_APP/$V/modules/createDataRequest/$s" "app/modules/createSignatureRequest/$s.imljson"
done
BODY='{"label": "Create a signature request (deprecated)", "description": "Use Create a signature request instead."}' \
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
- Each module once. Generate a PDF and Check data for a template with a template that has a date, a number, a checkbox
  and an image field: the Template fields collection shows typed inputs (date fields as text asking for YYYY-MM-DD).
- Create a signature request with two signers: one link per signer in Signing links, and `first_signing_url`. Each
  link must belong to its signer: `signing_links[1].signature_request_id` equals `signature_requests[1].id`, and
  `signing_links[2].signature_request_id` equals `signature_requests[2].id`. If both links have signer 1's ID, Make
  didn't re-read the token URL on each repeat, and signer 2 would get signer 1's form: don't publish.
- Signer Fields, with a template whose field names have a `/` (such as `address/street` and `items/0/name`): type
  those full names in a signer's Fields in Create a signature request and in Check data for a template, and both
  succeed. Fields is a list of names, not a picker: an RPC called from inside the Signers list gets only that item's
  inputs, so it can't read the module's template (tried 27 Oct 2026: DocSpring was asked for a template with ID
  `fields`). The live app had a `templateFieldNames` RPC for that picker until then; it was deleted.
- Errors: Generate a PDF with a wrong value for a field. The message reads
  `DocSpring API error 422 invalid_data: ...`, a line per field, `Submission: sub_...` and `Request ID: req_...`.
  Then a dropdown (or radio) field set to a value that isn't one of its options: its line reads
  `/data/<field>: must be one of: "Red", "Blue"`, with the field and every option.
- IDs: Get a submission with the ID `..` fails with `The submission ID can't be "." or ".."`, and the execution log
  shows no request. With the ID `a/b` it fails with DocSpring's 404 (the request went to `/submissions/a%2Fb`).
- Remove fields from a template with a field ID typed in Map mode removes the field (Make sends the ID as a number).
- Watch events: create a hook (DocSpring gets a version 4 webhook named "Make"), generate a test PDF (the scenario
  runs with `event_type`, `resource_type` and `resource_id`), delete the hook (the DocSpring webhook is deleted).
  Then create a hook, delete its webhook in DocSpring, and delete the hook: Make should delete it without an error.
  Then a hook with a template and the "Combined PDF processed" event: it fails with "Templates only limit submission,
  signature request and template events. ... combined_pdf.processed", and DocSpring gets no webhook.

Make behaviour these files rely on that hasn't been tried yet (each is from Make's documentation, and
`scripts/iml_tests.py` runs the IML as the docs describe it):

- `templateFields` uses `toArray()` and a `wrapper` to put the fields in one collection, and reads `body.required`
  while iterating. If the collection doesn't appear, the fallback is the old flat list: iterate
  `keys(body.properties)` without the wrapper, and build `data` with `omit(parameters; ...)` in the modules.
- `createSignatureRequest` runs three requests: the submission, a token request that `repeat`s once per signature
  request (reading the next ID from `temp`), and a request-less output. `detach` uses a `repeat` the same way: each
  list request reads the next page's cursor from `temp`.
- Request-less steps whose `response.valid` is `false`: the `.`/`..` ID checks at the start of 20 modules, and the
  template check at the start of `attach`. Make's docs list `valid` as available without a request. If Make ignores
  it there, the request goes ahead: an ID of `.` or `..` gets DocSpring's 404 (the ID is still encoded), and attach
  gets DocSpring's 422, which names the events too. To make the checks fail in Make anyway, give each check
  `"url": "/authentication"`, so `valid` runs on a response.
- `encodeURL()` encodes `/`, `?` and `#` (Make documents it as encoding special characters in a text for a URL, as
  JavaScript's `encodeURIComponent` does).
- The base error message uses `replace()` with regular expressions and `decodeURL('%0A')` for line breaks. The
  regular expressions keep each backslash inside a character class, so they work whether or not IML strings process
  backslash escapes. If Make doesn't read the regular expressions, the details show as JSON instead (still readable).
- `detach` makes up to 21 requests: it lists the webhooks with the hook's first event, 100 a page (up to 20 pages),
  and deletes the webhook only if it's in the list.
- Remove fields from a template' `spec: {"type": "number"}` on a multiple select converts each typed ID to a number.
- A select's `placeholder` (Move a template's "Root folder (/)"), and `null` from `ifempty(...; null)` for the root.
- Modules give up after Make's 40-second timeout (Make's default). A PDF that takes longer fails in Make, not with
  DocSpring's 504; turning off Wait for the PDF avoids it. Make support can raise the timeout for an app.
