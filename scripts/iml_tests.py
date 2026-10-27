#!/usr/bin/env python3
"""Runs the app's IML with scripts/iml.py and checks what it does: error messages, IDs in URLs, the signer field
picker, the Watch events checks and detach's paging. scripts/check.py runs these; they can also run alone.

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


# 2. The signer field picker lists the template version's field names from GET /templates/{id}/fields.
FIELDS = [
    {"id": 1, "name": "address/street", "type": "string", "static": False},
    {"id": 2, "name": "address/street", "type": "string", "static": False},
    {"id": 3, "name": "items/0/name", "type": "string", "static": False},
    {"id": 4, "name": "logo", "type": "image", "static": True},
    {"id": 5, "name": "full_name", "type": "combined", "static": False},
    {"id": 6, "name": "@@date", "type": "date", "static": False},
    {"id": 7, "name": None, "type": "string", "static": False},
    {"id": 8, "name": "signature", "type": "signature", "static": False},
    {"id": 9, "name": "notes#0", "type": "string", "static": False},
]
FIELD_NAMES = ["address/street", "items/0/name", "signature", "notes#0"]


def test_signer_field_picker():
    rpc = load("rpcs/templateFieldNames.imljson")
    errors = []
    if not re.fullmatch(r"/templates/\{\{.*\}\}/fields", rpc.get("url", "")):
        errors.append(f"rpcs/templateFieldNames.imljson: reads {rpc.get('url')}, not /templates/{{id}}/fields")
    for version, expected in ((None, "latest"), ("", "latest"), ("draft", "draft"), ("1.2.0", "1.2.0")):
        got = evaluate(rpc.get("qs", {}).get("version"), {"parameters": {"template_id": "tpl_1", "version": version}})
        if got != expected:
            errors.append(f"rpcs/templateFieldNames.imljson: version {version!r} asks for {got!r}, not {expected!r}")
    iterate = rpc["response"]["iterate"]
    body = {"template_id": "tpl_1", "version": "1.0.0", "fields": FIELDS}
    if isinstance(iterate, dict):
        container = evaluate(iterate["container"], {"body": body})
        items = [i for i in container if evaluate(iterate.get("condition", "{{true}}"), {"body": body, "item": i})]
    else:
        items = evaluate(iterate, {"body": body})
    values = [evaluate(rpc["response"]["output"]["value"], {"body": body, "item": i}) for i in items]
    if values != FIELD_NAMES:
        errors.append(f"rpcs/templateFieldNames.imljson: offers {values}, expected {FIELD_NAMES}")
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


TESTS = [test_error_details, test_ids_in_paths, test_id_values, test_signer_field_picker]


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
