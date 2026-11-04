#!/usr/bin/env python3
"""Runs the app's IML with scripts/iml.py and checks what it does: error messages, IDs in URLs, the signer field
picker, the Watch events checks and events, detach's paging, the signature request and Check data bodies for each Emails
to signers choice, the Word output formats and Generate files for a submission's file checks. scripts/check.py runs these; they can also run alone.

Usage: scripts/iml_tests.py
"""

import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iml import evaluate, find_expressions  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")

CONNECTION = {"region": "us", "token_id": "api_test", "token_secret": "secret"}

# The IDs that go into URL paths, and how an error names them
ID_LABELS = {
    "template_id": "template ID",
    "submission_id": "submission ID",
    "submission_batch_id": "submission batch ID",
    "combined_pdf_id": "combined PDF ID",
    "signature_request_id": "signature request ID",
}
DOT_IDS = [".", "..", " .. ", "\t.\n"]
GOOD_IDS = ["tpl_1234567890abcdef01", "...", ".a", "a.."]

# Events a webhook limited to templates can deliver (docspring app/models/webhook.rb, TEMPLATE_SCOPABLE_RESOURCES)
TEMPLATE_RESOURCES = ("submission.", "signature_request.", "template.")


def load(rel):
    with open(os.path.join(APP, rel)) as f:
        return json.load(f)


def requests_of(api):
    return api if isinstance(api, list) else [api]


def components():
    """(path, requests) for every module api, RPC and webhook attach/detach."""
    paths = sorted(glob.glob(os.path.join(APP, "modules", "*", "api.imljson")))
    paths += sorted(glob.glob(os.path.join(APP, "rpcs", "*.imljson")))
    paths += [os.path.join(APP, "webhooks", "attach.imljson"), os.path.join(APP, "webhooks", "detach.imljson")]
    return [(os.path.relpath(p, APP), requests_of(json.load(open(p)))) for p in paths]


def path_expressions(url):
    """The {{expressions}} in a URL after its host (the sync-host modules start with a host expression)."""
    parts = find_expressions(url)
    if parts and parts[0][0] and "connection." in parts[0][1]:
        parts = parts[1:]
    return [text for is_expression, text in parts if is_expression]


# 8. Error details whose message contains quotes, braces or backslashes keep all their text.
ERROR_DETAILS = [
    {"code": "enum", "message": 'must be one of: "Red", "Blue"', "pointer": "/data/colour"},
    {"code": "required", "message": "is required", "pointer": "/data/name"},
    {"code": "pattern", "message": "must match the pattern ^\\d+$", "pointer": "/data/zip"},
    {"code": "invalid", "message": "must be a version like 1.2.3 or 1, or latest or draft", "parameter": "version"},
    {"code": "not_found", "message": "isn't a field of this template. Did you mean 'colour'?",
     "pointer": "/signature_requests/0/fields/0"},
    {"code": "const", "message": 'must be {"a":"b"}', "pointer": '/data/a"b'},
    {"code": "invalid", "message": "has no pointer"},
]
ERROR_EXPECTED = "\n".join([
    "DocSpring API error 422 invalid_data: Invalid data",
    '/data/colour: must be one of: "Red", "Blue"',
    "/data/name: is required",
    "/data/zip: must match the pattern ^\\d+$",
    "version: must be a version like 1.2.3 or 1, or latest or draft",
    "/signature_requests/0/fields/0: isn't a field of this template. Did you mean 'colour'?",
    '/data/a"b: must be {"a":"b"}',
    "has no pointer",
    "Submission: sub_1",
    "Request ID: req_1",
])


def test_error_details():
    message = load("base.imljson")["response"]["error"]["message"]
    body = {"error": {"code": "invalid_data", "message": "Invalid data", "details": ERROR_DETAILS,
                      "submission_id": "sub_1", "request_id": "req_1"}}
    errors = []
    for escapes in (True, False):
        got = evaluate(message, {"statusCode": 422, "body": body}, escapes=escapes)
        if got != ERROR_EXPECTED:
            how = "with" if escapes else "without"
            errors.append(f"base.imljson: the error message ({how} backslash escapes in IML strings) is\n{got}\n"
                          f"expected\n{ERROR_EXPECTED}")
    no_details = {"error": {"code": "not_found", "message": "Template not found", "details": [], "request_id": "r"}}
    got = evaluate(message, {"statusCode": 404, "body": no_details})
    if got != "DocSpring API error 404 not_found: Template not found\nRequest ID: r":
        errors.append(f"base.imljson: an error without details reads {got!r}")
    return errors


# 1. Every ID in a URL path is encoded, and "." or ".." is rejected before the request.
def test_ids_in_paths():
    errors = []
    for rel, requests in components():
        if rel == "modules/makeApiCall/api.imljson":
            continue  # its URL is the path the user enters
        for request in requests:
            url = request.get("url")
            if not isinstance(url, str):
                continue
            for expression in path_expressions(url):
                if not re.fullmatch(r"encodeURL\(.*\)", expression.strip()):
                    errors.append(f"{rel}: {{{{{expression}}}}} goes into the URL path without encodeURL()")
    return errors


def id_params(url):
    return sorted(set(re.findall(r"parameters\.([a-z_]+_id)\b", url)))


def test_id_values():
    """Runs each URL with an ID that would climb out of its path, and checks the guards."""
    errors = []
    for rel, requests in components():
        guards = [r for r in requests if "url" not in r]
        for request in requests:
            url = request.get("url")
            if not isinstance(url, str):
                continue
            for param in id_params(url):
                if param not in ID_LABELS:
                    errors.append(f"{rel}: {param} has no label in iml_tests.ID_LABELS")
                    continue
                value = "../templates/tpl_x"
                got = evaluate(url, {"parameters": {param: value, "version": "latest"}, "connection": CONNECTION})
                if "/../" in got or "%2Ftemplates%2Ftpl_x" not in got:
                    errors.append(f"{rel}: {param} = {value!r} gives the URL {got}")
                if rel.startswith("rpcs/"):
                    errors += check_rpc_condition(rel, request, param)
                else:
                    errors += check_guard(rel, guards, requests, param)
    return errors


def check_guard(rel, guards, requests, param):
    errors = []
    guard = next((g for g in guards if f"parameters.{param}" in str(g.get("condition"))), None)
    if guard is None or requests.index(guard) != 0:
        return [f"{rel}: no request-less check of {param} before the requests"]
    valid = guard.get("response", {}).get("valid", {})
    expected = f"The {ID_LABELS[param]} can't be \".\" or \"..\"."
    if valid.get("condition") != "{{false}}" or valid.get("message") != expected or valid.get("type") != "DataError":
        errors.append(f"{rel}: the {param} check should fail with {expected!r} (a DataError)")
    for value in DOT_IDS + GOOD_IDS:
        rejected = bool(evaluate(guard["condition"], {"parameters": {param: value}}))
        if rejected != (value in DOT_IDS):
            errors.append(f"{rel}: {param} = {value!r} is {'rejected' if rejected else 'accepted'}")
    return errors


def check_rpc_condition(rel, request, param):
    """A picker makes no request for "." or ".." (it shows no options)."""
    errors = []
    if "condition" not in request:
        return [f"{rel}: makes its request even when {param} is \".\" or \"..\""]
    for value in DOT_IDS + GOOD_IDS:
        runs = bool(evaluate(request["condition"], {"parameters": {param: value}}))
        if runs == (value in DOT_IDS):
            errors.append(f"{rel}: {param} = {value!r} {'makes' if runs else 'skips'} the request")
    return errors


# 2. No field inside an array item takes its options from an RPC: Make calls it with only that item's inputs, so it
# can't read the module's template (tried 27 Oct 2026: the signer Fields picker asked for template ID "fields").
# Each signer's Fields is a list of typed field names instead.
def walk_fields(fields, in_array=False):
    for field in fields if isinstance(fields, list) else [fields]:
        if not isinstance(field, dict):
            continue
        yield field, in_array
        spec = field.get("spec")
        if spec:
            yield from walk_fields(spec, in_array or field.get("type") == "array")
        options = field.get("options")
        if isinstance(options, dict):
            yield from walk_fields(options.get("nested", []), in_array)
            for option in options.get("store", []) if isinstance(options.get("store"), list) else []:
                yield from walk_fields(option.get("nested", []), in_array)
        elif isinstance(options, list):
            for option in options:
                if isinstance(option, dict):
                    yield from walk_fields(option.get("nested", []), in_array)


def test_no_rpc_inside_arrays():
    errors = []
    for module in sorted(os.listdir(os.path.join(APP, "modules"))):
        rel = f"modules/{module}/expect.imljson"
        if not os.path.exists(os.path.join(APP, rel)):
            continue
        for field, in_array in walk_fields(load(rel)):
            options = field.get("options")
            store = options.get("store") if isinstance(options, dict) else options
            if in_array and isinstance(store, str) and store.startswith("rpc://"):
                errors.append(f"{rel}: {field.get('name')} is inside an array but takes its options from {store}")
    for module in ("createSignatureRequest", "checkData"):
        rel = f"modules/{module}/expect.imljson"
        signers = next(f for f in load(rel) if f.get("name") == "signature_requests")
        fields = next(f for f in signers["spec"] if f.get("name") == "fields")
        if fields.get("type") != "array" or fields.get("spec", {}).get("type") != "text":
            errors.append(f"{rel}: a signer's fields aren't a list of typed names: {fields}")
    return errors


# 3. Templates on Watch events: events that can't be limited to templates fail before DocSpring is called.
def test_watch_events_templates():
    attach = requests_of(load("webhooks/attach.imljson"))
    events = [o["value"] for p in load("webhooks/parameters.imljson") if p["name"] == "event_types" for o in p["options"]]
    scopable = [e for e in events if e.startswith(TEMPLATE_RESOURCES)]
    guard = attach[0]
    if "url" in guard or "condition" not in guard:
        return ["webhooks/attach.imljson: no request-less check of the events before POST /webhooks"]
    errors = []
    listed = re.findall(r"'([a-z_]+\.[a-z_]+)'", guard["condition"])
    if sorted(set(listed)) != sorted(scopable):
        errors.append(f"webhooks/attach.imljson: the check lists {sorted(set(listed))}, the template events are "
                      f"{sorted(scopable)}")
    cases = [
        (["tpl_1"], ["submission.processed", "combined_pdf.processed", "folder.created"],
         "combined_pdf.processed, folder.created"),
        (["tpl_1"], scopable, None),
        (None, events, None),
        ([], ["folder.created"], None),
    ]
    for templates, chosen, named in cases:
        context = {"parameters": {"template_ids": templates, "event_types": chosen}}
        fails = bool(evaluate(guard["condition"], context))
        if fails != (named is not None):
            errors.append(f"webhooks/attach.imljson: templates {templates} with {chosen} "
                          f"{'fail' if fails else 'pass'} the check")
        valid = guard.get("response", {}).get("valid", {})
        if named and valid.get("condition") == "{{false}}":
            message = evaluate(valid.get("message", ""), context)
            if named not in message:
                errors.append(f"webhooks/attach.imljson: the message {message!r} doesn't name {named}")
        elif named:
            errors.append("webhooks/attach.imljson: the check doesn't fail with a message (valid: {{false}})")
    return errors


# 11. Remove template fields: IDs typed by hand become numbers.
def test_remove_field_ids():
    expect = load("modules/removeTemplateFields/expect.imljson")
    field_ids = [p for p in expect[0]["options"]["nested"] if p["name"] == "field_ids"][0]
    if field_ids.get("spec", {}).get("type") != "number":
        return ["modules/removeTemplateFields/expect.imljson: field_ids has no spec {\"type\": \"number\"}, so typed "
                "IDs are sent as text"]
    return []


# 11. Detach finds the webhook on any page of GET /webhooks, as Make's repeat runs it.
def run_detach(pages, hook_id):
    detach = requests_of(load("webhooks/detach.imljson"))
    listing, delete = detach[0], detach[-1]
    webhook = {"externalHookId": hook_id, "eventType": "submission.processed"}
    temp, cursors = {}, []
    for _ in range(listing.get("repeat", {}).get("limit", 1)):
        context = {"webhook": webhook, "temp": temp}
        qs = evaluate(listing.get("qs", {}), context)
        cursors.append(qs.get("cursor"))
        body = pages[qs.get("cursor")]
        temp = {**temp, **evaluate(listing["response"].get("temp", {}), {**context, "body": body})}
        if "repeat" not in listing or not evaluate(listing["repeat"]["condition"], {"temp": temp}):
            break
    deletes = bool(evaluate(delete["condition"], {"webhook": webhook, "temp": temp}))
    url = evaluate(delete["url"], {"webhook": webhook, "temp": temp})
    return cursors, deletes, url


def test_detach_paging():
    pages = {
        None: {"data": [{"id": "whk_1"}], "next_cursor": "c2"},
        "c2": {"data": [{"id": "whk_2"}], "next_cursor": "c3"},
        "c3": {"data": [{"id": "whk_3"}], "next_cursor": None},
    }
    errors = []
    cursors, deletes, url = run_detach(pages, "whk_3")
    if not deletes or cursors != [None, "c2", "c3"] or url != "/webhooks/whk_3":
        errors.append(f"webhooks/detach.imljson: a webhook on page 3 read pages {cursors}, deletes={deletes}, {url}")
    cursors, deletes, _ = run_detach(pages, "whk_1")
    if not deletes or cursors != [None]:
        errors.append(f"webhooks/detach.imljson: a webhook on page 1 read pages {cursors}, deletes={deletes}")
    cursors, deletes, _ = run_detach(pages, "whk_gone")
    if deletes or cursors != [None, "c2", "c3"]:
        errors.append(f"webhooks/detach.imljson: a deleted webhook read pages {cursors}, deletes={deletes}")
    return errors


# 12. Create a signature request: with DocSpring's emails it sends send_email and the email options, and makes no
# signing links (the signers get theirs by email); when you send the links, it sends none of the email options.
# Email options a scenario could still hold after switching to "I send the links": the API refuses each one then
STALE_EMAIL_OPTIONS = {"email_subject": "Please sign", "email_message": "Hi", "reply_to": "team@example.com",
                       "cc": ["cc@example.com"], "reminders": {"interval_days": 3, "max_count": 2},
                       "notification_emails": ["n@example.com"], "notify_when_signed": True}


def run_token_requests(step, parameters, ids):
    """The token request URLs Make sends for the signature requests `ids`, and Make's error if any. Make checks the
    step's condition on each pass, but goes on repeating while the repeat's own condition holds, skipped passes too, up
    to its limit, then stops the module with "Maximum number of repeats exceeded" (seen live on 4 Nov 2026: with
    DocSpring's emails the skipped token step never moved temp.index)."""
    temp = {"signature_request_ids": ids, "signing_links": [], "index": 1}
    urls = []
    for _ in range(step.get("repeat", {}).get("limit", 1)):
        context = {"parameters": parameters, "temp": temp}
        if evaluate(step["condition"], context):
            urls.append(evaluate(step["url"], context))
            body = {"signature_request_url": f"https://app.docspring.com/sign/{len(urls)}"}
            temp = {**temp, **evaluate(step["response"]["temp"], {**context, "body": body})}
        if "repeat" not in step or not evaluate(step["repeat"]["condition"], {"parameters": parameters, "temp": temp}):
            return urls, None
    return urls, "Maximum number of repeats exceeded"


def run_signature_request(parameters):
    api = requests_of(load("modules/createSignatureRequest/api.imljson"))
    create, links = api[1], api[2]
    context = {"parameters": parameters}
    body = {k: evaluate(v, context) for k, v in create["body"].items() if k != "data"}
    urls, error = run_token_requests(links, parameters, ["srq_1", "srq_2"])
    if error:
        raise AssertionError(f"modules/createSignatureRequest/api.imljson: {error} with {parameters}")
    makes_links = bool(urls)
    if makes_links and urls != ["/signature_requests/srq_1/tokens", "/signature_requests/srq_2/tokens"]:
        raise AssertionError(f"modules/createSignatureRequest/api.imljson: token requests {urls}, not one per signer")
    return {k: v for k, v in body.items() if v is not None}, makes_links


def test_signature_request_emails():
    rel = "modules/createSignatureRequest/api.imljson"
    signers = [{"name": "Jane Doe", "email": "jane.doe@example.com", "fields": ["signature"], "auth_type": "email_link"}]
    errors = []
    body, makes_links = run_signature_request({
        "signature_requests": signers, "send_email": "docspring", "signing_order": "sequential",
        "email_subject": "Please sign", "cc": ["cc@example.com"], "notification_emails": [],
        "reminders": {"interval_days": 3, "max_count": 2}, "notify_when_signed": True, "signing_link_type": "email"})
    expected = {"signature_requests": signers, "send_email": True, "signing_order": "sequential",
                "email_subject": "Please sign", "cc": ["cc@example.com"],
                "reminders": {"interval_days": 3, "max_count": 2}, "notify_when_signed": True}
    if body != expected or makes_links:
        errors.append(f"{rel}: DocSpring's emails sent {body} and makes_links={makes_links}")
    body, makes_links = run_signature_request({
        "signature_requests": signers, "send_email": "docspring", "cc": [], "reminders": {}, "notify_when_signed": False})
    if body != {"signature_requests": signers, "send_email": True} or makes_links:
        errors.append(f"{rel}: empty email options sent {body} and makes_links={makes_links}")
    body, makes_links = run_signature_request({
        "signature_requests": signers, "send_email": "self", "signing_link_type": "api"})
    if body != {"signature_requests": signers, "send_email": False} or not makes_links:
        errors.append(f"{rel}: sending the links yourself sent {body} and makes_links={makes_links}")
    _, makes_links = run_signature_request({"signature_requests": signers, "send_email": "self", "signing_link_type": "none"})
    if makes_links:
        errors.append(f"{rel}: No links still makes links")
    # Blank or unexpected is DocSpring's emails, as in Check data and the API: never nobody emailed and no links
    for mode in (None, "", "DocSpring", True):
        body, makes_links = run_signature_request({"signature_requests": signers, "send_email": mode,
                                                   "signing_link_type": "email"})
        if body != {"signature_requests": signers, "send_email": True} or makes_links:
            errors.append(f"{rel}: Emails to signers {mode!r} sent {body} and makes_links={makes_links}")
    body, makes_links = run_signature_request({**STALE_EMAIL_OPTIONS, "signature_requests": signers, "send_email": "self",
                                               "signing_order": "sequential", "signing_link_type": "api"})
    if body != {"signature_requests": signers, "send_email": False, "signing_order": "sequential"} or not makes_links:
        errors.append(f"{rel}: email options left from DocSpring's emails were sent with I send the links: {body}")
    body, _ = run_signature_request({"signature_requests": signers, "send_email": "docspring",
                                     "cc": ["a@example.com", "b@example.com", "a@example.com"],
                                     "notification_emails": ["n@example.com", "n@example.com"]})
    if body.get("cc") != ["a@example.com", "b@example.com"] or body.get("notification_emails") != ["n@example.com"]:
        errors.append(f"{rel}: repeated addresses (a 422) were sent: {body}")
    return errors


# 13. Check data sends the email settings Create a signature request sends, only with signers: the API refuses them
# without.
def check_data_body(parameters):
    check = requests_of(load("modules/checkData/api.imljson"))[1]
    body = {k: evaluate(v, {"parameters": parameters}) for k, v in check["body"].items() if k != "data"}
    return {k: v for k, v in body.items() if v is not None}


def test_check_data_emails():
    rel = "modules/checkData/api.imljson"
    signers = [{"email": "jane.doe@example.com", "fields": ["signature"], "auth_type": "email_link"}]
    settings = {"signing_order": "sequential", "email_subject": "Please sign", "cc": ["cc@example.com"],
                "reminders": {"interval_days": 3, "max_count": 2}, "notify_when_signed": True}
    errors = []
    body = check_data_body({**settings, "signature_requests": signers})
    if body != {**settings, "signature_requests": signers, "send_email": True}:
        errors.append(f"{rel}: DocSpring's emails (the default) sent {body}")
    body = check_data_body({"signature_requests": signers, "send_email": "self", "signing_order": "sequential"})
    if body != {"signature_requests": signers, "send_email": False, "signing_order": "sequential"}:
        errors.append(f"{rel}: sending the links yourself sent {body}")
    body = check_data_body({**settings, "send_email": "docspring", "cc": [], "reminders": {}, "notify_when_signed": False,
                            "signature_requests": signers})
    if body != {"signature_requests": signers, "send_email": True, "signing_order": "sequential",
                "email_subject": "Please sign"}:
        errors.append(f"{rel}: empty email options sent {body}")
    body = check_data_body({**STALE_EMAIL_OPTIONS, "signature_requests": signers, "send_email": "self"})
    if body != {"signature_requests": signers, "send_email": False}:
        errors.append(f"{rel}: email options left from DocSpring's emails were sent with I send the links: {body}")
    body = check_data_body({"signature_requests": signers, "cc": ["a@example.com", "a@example.com"]})
    if body.get("cc") != ["a@example.com"]:
        errors.append(f"{rel}: repeated CC addresses (a 422) were sent: {body}")
    for no_signers in (None, []):
        body = check_data_body({**settings, "send_email": "docspring", "signature_requests": no_signers})
        if {k: v for k, v in body.items() if k != "signature_requests"}:
            errors.append(f"{rel}: without signers it sent {body}")
    return errors


# 14. Make an API call offers only the methods API v2 has: it answers PATCH with a 405.
def test_api_call_methods():
    expect = load("modules/makeApiCall/expect.imljson")
    method = next(p for p in expect if p["name"] == "method")
    values = [o["value"] for o in method["options"]]
    if values != ["GET", "POST", "PUT", "DELETE"]:
        return [f"modules/makeApiCall/expect.imljson: offers {values}"]
    return []


# 15. A Word template's submission can make its Word document and OpenDocument file, and Generate files for a
# submission fails when any file it was asked for couldn't be made, naming which one and why.
def options_of(module, name):
    parameter = next(p for p in load(f"modules/{module}/expect.imljson") if p["name"] == name)
    return [o["value"] for o in parameter["options"]]


def test_word_outputs():
    errors = []
    for module in ("generatePdf", "generatePdfBatch"):
        values = options_of(module, "output_formats")
        if sorted(values) != ["docx", "odt", "pdf", "png"]:
            errors.append(f"modules/{module}/expect.imljson: Output formats offers {values}")
    values = options_of("generateSubmissionFiles", "formats")
    if sorted(values) != ["docx", "odt", "pdf", "png"]:
        errors.append(f"modules/generateSubmissionFiles/expect.imljson: Formats offers {values}")

    rel = "modules/generateSubmissionFiles/api.imljson"
    valid = requests_of(load(rel))[1]["response"]["valid"]
    processed = {"state": "processed", "error_message": None}
    pending = {"state": "pending", "error_message": None}
    failed = {"state": "error", "error_message": "LibreOffice couldn't convert it"}
    for formats, files in ((["png"], {"pdf": processed, "png": pending}), (["docx", "odt"], {"docx": processed, "odt": pending}),
                           (["pdf"], {"pdf": processed}),
                           # A file that failed earlier, from a request for another format, isn't this request's
                           (["png"], {"png": processed, "odt": failed}), (["docx"], {"docx": pending, "pdf": failed})):
        context = {"parameters": {"formats": formats}, "body": {"id": "sub_1", "files": files}}
        if evaluate(valid["condition"], context) is not True:
            errors.append(f"{rel}: formats {formats} with files {files} fail the check")
    for name, label in (("pdf", "PDF"), ("docx", "Word document"), ("odt", "OpenDocument file"),
                        ("png", "Page images")):
        context = {"parameters": {"formats": ["docx", name]}, "body": {"id": "sub_1", "files": {"docx": processed, name: failed}}}
        if evaluate(valid["condition"], context) is not False:
            errors.append(f"{rel}: a {name} error passes the check")
        message = evaluate(valid["message"], context)
        expected = f"DocSpring couldn't make some of the files. {label}: LibreOffice couldn't convert it\nSubmission: sub_1"
        if message != expected:
            errors.append(f"{rel}: a {name} error reads {message!r}")
    return errors


# 16. Watch events offers sc-2878's signer email events, and Templates can limit them
def test_signer_email_events():
    events = [o["value"] for p in load("webhooks/parameters.imljson") if p["name"] == "event_types" for o in p["options"]]
    missing = [e for e in ("signature_request.sent", "signature_request.email_bounced") if e not in events]
    return [f"webhooks/parameters.imljson: Events doesn't offer {missing}"] if missing else []


TESTS = [test_error_details, test_ids_in_paths, test_id_values, test_no_rpc_inside_arrays,
         test_watch_events_templates, test_remove_field_ids, test_detach_paging, test_signature_request_emails,
         test_check_data_emails, test_api_call_methods, test_word_outputs, test_signer_email_events]


def run():
    errors = []
    for test in TESTS:
        try:
            errors += test()
        except Exception as e:  # report which test broke, then fail
            errors.append(f"{test.__name__}: {type(e).__name__}: {e}")
    return errors


if __name__ == "__main__":
    problems = run()
    print("\n".join(problems) if problems else f"OK: {len(TESTS)} IML tests")
    sys.exit(1 if problems else 0)
