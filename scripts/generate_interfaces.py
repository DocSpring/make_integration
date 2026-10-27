#!/usr/bin/env python3
"""Writes each module's interface.imljson and samples.imljson from DocSpring's API v2 OpenAPI spec.

The modules return the API v2 resource as the API returns it, so their output fields (the interface) and their
samples come from the resource schemas and the response examples in the spec.

Usage:
    scripts/generate_interfaces.py [path/to/openapi.json]

The default path is the docspring repo checked out next to this one (../docspring/openapi/v2/openapi.json).
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULES = os.path.join(ROOT, "app", "modules")
DEFAULT_SPEC = os.path.join(os.path.dirname(ROOT), "docspring", "openapi", "v2", "openapi.json")

# Nested collections deeper than this become a collection without a spec (Make still shows what arrives).
MAX_DEPTH = 3

ACRONYMS = {
    "id": "ID",
    "ids": "IDs",
    "url": "URL",
    "urls": "URLs",
    "pdf": "PDF",
    "pdfs": "PDFs",
    "png": "PNG",
    "html": "HTML",
    "scss": "SCSS",
    "css": "CSS",
    "sha256": "SHA-256",
    "md5": "MD5",
    "ip": "IP",
    "api": "API",
    "ldap": "LDAP",
    "saml": "SAML",
    "oauth": "OAuth",
    "json": "JSON",
    "ai": "AI",
}

# module -> (method, path, response status, schema name, example name, how the sample is taken)
# "item:<key>" takes the first element of the example's <key> list (search modules output one bundle per item).
MODULES_FROM_SPEC = {
    "generatePdf": ("post", "/templates/{template_id}/submissions", "201", "Submission", "submission created", None),
    "generatePdfBatch": ("post", "/submissions/batches", "201", "SubmissionBatch", "batch created", None),
    "getSubmissionBatch": ("get", "/submissions/batches/{submission_batch_id}", "200", "SubmissionBatch", "batch", None),
    "checkData": ("post", "/templates/{template_id}/submissions/validate", "200", "SubmissionValidation", "valid submission", None),
    "getSubmission": ("get", "/submissions/{submission_id}", "200", "Submission", "processed submission", None),
    "findSubmission": ("get", "/submissions", "200", "Submission", "submissions", "item:data"),
    "generateSubmissionFiles": ("post", "/submissions/{submission_id}/generate_files", "200", "Submission", "images of the pages requested", None),
    "expireSubmission": ("delete", "/submissions/{submission_id}", "200", "Submission", "submission expired", None),
    "combinePdfs": ("post", "/combined_pdfs", "201", "CombinedPdf", "combined PDF created", None),
    "getCombinedPdf": ("get", "/combined_pdfs/{combined_pdf_id}", "200", "CombinedPdf", "combined PDF", None),
    "createSigningLink": ("post", "/signature_requests/{signature_request_id}/tokens", "201", "SignatureRequestToken", "token created", None),
    "getSignatureRequest": ("get", "/signature_requests/{signature_request_id}", "200", "SignatureRequest", "signature request", None),
    "findTemplate": ("get", "/templates", "200", "TemplateSummary", "templates", "item:data"),
    "getTemplate": ("get", "/templates/{template_id}", "200", "Template", "PDF template", None),
    "createTemplate": ("post", "/templates", "201", "Template", "PDF template created from a URL", None),
    "replaceTemplatePdf": ("put", "/templates/{template_id}/document", "200", "Template", "PDF replaced", None),
    "copyTemplate": ("post", "/templates/{template_id}/copy", "201", "Template", "template copied", None),
    "moveTemplate": ("post", "/templates/{template_id}/move", "200", "Template", "template moved", None),
    "publishTemplateVersion": ("post", "/templates/{template_id}/publish_version", "201", "TemplateVersion", "version published", None),
    "listTemplateFields": ("get", "/templates/{template_id}/fields", "200", "Field", "fields", "item:fields"),
    "addTemplateFields": ("post", "/templates/{template_id}/fields", "201", "TemplateFields", "fields added", None),
    "updateTemplateFields": ("put", "/templates/{template_id}/fields", "200", "TemplateFields", "fields updated", None),
    "removeTemplateFields": ("post", "/templates/{template_id}/fields/remove", "200", "TemplateFields", "fields removed", None),
    "getTemplatePageImages": ("get", "/templates/{template_id}/page_images", "200", "TemplatePageImages", "page images", None),
    "listFolders": ("get", "/folders", "200", "Folder", "all folders", "item:data"),
    "createFolder": ("post", "/folders", "201", "Folder", "folder created at the root", None),
}


def load_spec(path):
    with open(path) as f:
        return json.load(f)


def resolve(spec, schema):
    while isinstance(schema, dict) and "$ref" in schema:
        node = spec
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


def label(name):
    words = name.split("_")
    out = [ACRONYMS.get(w, w) for w in words]
    first = out[0]
    if first == words[0]:
        first = first[:1].upper() + first[1:]
    return " ".join([first] + out[1:])


def main_type(schema):
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    if t is None and "properties" in schema:
        t = "object"
    return t


def to_param(spec, name, schema, depth):
    schema = resolve(spec, schema)
    t = main_type(schema)
    param = {"name": name, "label": label(name)}
    if t == "string":
        param["type"] = "date" if schema.get("format") == "date-time" else "text"
    elif t in ("integer", "number"):
        param["type"] = "number"
    elif t == "boolean":
        param["type"] = "boolean"
    elif t == "array":
        items = resolve(spec, schema.get("items", {}))
        item_type = main_type(items)
        param["type"] = "array"
        if item_type == "object" and items.get("properties") and depth < MAX_DEPTH:
            param["spec"] = to_spec(spec, items, depth + 1)
        elif item_type in ("integer", "number"):
            param["spec"] = {"type": "number"}
        elif item_type == "string":
            param["spec"] = {"type": "text"}
        elif item_type == "boolean":
            param["spec"] = {"type": "boolean"}
        else:
            param["spec"] = {"type": "any"}
    elif t == "object" and schema.get("properties") and depth < MAX_DEPTH:
        param["type"] = "collection"
        param["spec"] = to_spec(spec, schema, depth + 1)
    elif t == "object":
        param["type"] = "collection"
        param["spec"] = []
    else:
        param["type"] = "any"
    return param


def to_spec(spec, schema, depth):
    schema = resolve(spec, schema)
    return [to_param(spec, name, prop, depth) for name, prop in schema.get("properties", {}).items()]


def example(spec, method, path, status, example_name):
    response = resolve(spec, spec["paths"][path][method]["responses"][status])
    examples = response["content"]["application/json"]["examples"]
    if example_name not in examples:
        raise SystemExit(f"{method.upper()} {path} has no example named {example_name!r}: {sorted(examples)}")
    return examples[example_name]["value"]


def write_json(module, section, value):
    folder = os.path.join(MODULES, module)
    if not os.path.isdir(folder):
        raise SystemExit(f"No module folder {folder}")
    with open(os.path.join(folder, f"{section}.imljson"), "w") as f:
        json.dump(value, f, indent=4, ensure_ascii=False)
        f.write("\n")


def main():
    spec_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SPEC
    spec = load_spec(spec_path)
    schemas = spec["components"]["schemas"]

    for module, (method, path, status, schema_name, example_name, take) in MODULES_FROM_SPEC.items():
        interface = to_spec(spec, schemas[schema_name], 0)
        sample = example(spec, method, path, status, example_name)
        if take:
            key = take.split(":", 1)[1]
            sample = sample[key][0]
        write_json(module, "interface", interface)
        write_json(module, "samples", sample)

    # Create signature request: the submission, plus a signing link for each signature request.
    submission = to_spec(spec, schemas["Submission"], 0)
    token = to_spec(spec, schemas["SignatureRequestToken"], 1)
    write_json(
        "createSignatureRequest",
        "interface",
        submission
        + [
            {"name": "signing_links", "label": "Signing links", "type": "array", "spec": token},
            {"name": "first_signature_request_id", "label": "First signature request ID", "type": "text"},
            {"name": "first_signing_url", "label": "First signing URL", "type": "text"},
        ],
    )
    sample = example(spec, "post", "/templates/{template_id}/submissions", "201", "submission with signature requests created")
    link = example(spec, "post", "/signature_requests/{signature_request_id}/tokens", "201", "token created")
    first = sample["signature_requests"][0]["id"]
    link = dict(link, signature_request_id=first)
    link["signature_request_url"] = link["signature_request_url"].replace("srq_1234567890abcdef01", first)
    sample = dict(sample, signing_links=[link], first_signature_request_id=first, first_signing_url=link["signature_request_url"])
    write_json("createSignatureRequest", "samples", sample)

    # Watch events: the version 4 event as delivered, plus resource_type and resource_id.
    write_json(
        "watchEvents",
        "interface",
        [
            {"name": "id", "label": "Event ID", "type": "text"},
            {"name": "event_type", "label": "Event type", "type": "text"},
            {"name": "created_at", "label": "Created at", "type": "date"},
            {"name": "resource_type", "label": "Resource type", "type": "text"},
            {"name": "resource_id", "label": "Resource ID", "type": "text"},
            {"name": "data", "label": "Data", "type": "collection", "spec": []},
        ],
    )
    processed = example(spec, "get", "/submissions/{submission_id}", "200", "processed submission")
    write_json(
        "watchEvents",
        "samples",
        {
            "id": "6f1c2e8a-3b4d-4c5e-9f60-7a8b9c0d1e2f",
            "event_type": "submission.processed",
            "created_at": processed["processed_at"],
            "data": processed,
            "resource_type": "submission",
            "resource_id": processed["id"],
        },
    )

    print(f"Wrote the interfaces and samples of {len(MODULES_FROM_SPEC) + 2} modules from {spec_path}")


if __name__ == "__main__":
    main()
