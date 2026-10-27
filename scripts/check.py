#!/usr/bin/env python3
"""Checks the Make app's files before an upload. There's no test framework: Make runs the IML, not us.

- Every .imljson file is valid JSON, and every {{ in it is closed.
- Every module has the sections its type needs, every rpc:// it names exists, and groups.imljson lists each
  module once.
- app/UPLOAD.md names every module and RPC, so none is left out of an upload.
- Nothing calls API v1, and the values Make limits fit (a request URL: 512 characters, an error message: 1024).
- The IML does what it should, run by scripts/iml.py (scripts/iml_tests.py): error messages, IDs in URLs, the
  signer field picker, the Watch events checks and detach's paging.

Usage: scripts/check.py
"""

import glob
import json
import os
import re
import sys

import iml_tests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = os.path.join(ROOT, "app")

# Modules without the usual api + expect + interface sections.
SECTIONS = {
    "watchEvents": {"interface", "samples"},  # an instant trigger: the webhook does the work
}
DEFAULT_SECTIONS = {"api", "expect", "interface"}

errors = []


def error(message):
    errors.append(message)


def strings(value, path=""):
    """Yields (path, string) for every string in a JSON value, keys included."""
    if isinstance(value, dict):
        for key, item in value.items():
            yield f"{path}.{key}", key
            yield from strings(item, f"{path}.{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from strings(item, f"{path}[{i}]")
    elif isinstance(value, str):
        yield path, value


def unclosed_iml(text):
    """True if an IML expression's {{ has no }} before the next {{. A }} on its own is plain text (a JSON example)."""
    start = text.find("{{")
    while start != -1:
        end = text.find("}}", start + 2)
        following = text.find("{{", start + 2)
        if end == -1 or (following != -1 and following < end):
            return True
        start = text.find("{{", end + 2)
    return False


def check_limits(rel, value):
    """Make's SDK rejects a request url over 512 characters and an error message over 1024."""
    requests = value if isinstance(value, list) else [value]
    for request in requests:
        if not isinstance(request, dict):
            continue
        url = request.get("url")
        if isinstance(url, str) and len(url) > 512:
            error(f"{rel}: url is {len(url)} characters (Make allows 512)")
        response_error = request.get("response", {}).get("error") if isinstance(request.get("response"), dict) else None
        messages = []
        if isinstance(response_error, str):
            messages.append(response_error)
        elif isinstance(response_error, dict):
            for key, item in response_error.items():
                if key == "message":
                    messages.append(item)
                elif isinstance(item, dict) and "message" in item:
                    messages.append(item["message"])
        for message in messages:
            if len(message) > 1024:
                error(f"{rel}: an error message is {len(message)} characters (Make allows 1024)")


def main():
    files = sorted(glob.glob(os.path.join(APP, "**", "*.imljson"), recursive=True))
    parsed = {}
    for path in files:
        rel = os.path.relpath(path, ROOT)
        try:
            with open(path) as f:
                parsed[rel] = json.load(f)
        except json.JSONDecodeError as e:
            error(f"{rel}: not valid JSON: {e}")
            continue
        for where, text in strings(parsed[rel]):
            if unclosed_iml(text):
                error(f"{rel}{where}: a {{{{ isn't closed in {text[:80]!r}")
            if "/api/v1" in text:
                error(f"{rel}{where}: calls API v1")
        check_limits(rel, parsed[rel])

    rpcs = {os.path.basename(p)[: -len(".imljson")] for p in glob.glob(os.path.join(APP, "rpcs", "*.imljson"))}
    modules = sorted(os.listdir(os.path.join(APP, "modules")))

    for name in modules:
        have = {os.path.basename(p).split(".")[0] for p in glob.glob(os.path.join(APP, "modules", name, "*.imljson"))}
        missing = SECTIONS.get(name, DEFAULT_SECTIONS) - have
        if missing:
            error(f"app/modules/{name}: missing {', '.join(sorted(missing))}")

    for rel, value in parsed.items():
        for _, text in strings(value):
            for rpc in re.findall(r"rpc://([A-Za-z0-9]+)", text):
                if rpc not in rpcs:
                    error(f"{rel}: names rpc://{rpc}, which isn't in app/rpcs")

    grouped = [m for group in parsed.get(os.path.join("app", "groups.imljson"), []) for m in group["modules"]]
    for name in modules:
        if grouped.count(name) != 1:
            error(f"app/groups.imljson lists {name} {grouped.count(name)} times")
    for name in set(grouped) - set(modules):
        error(f"app/groups.imljson lists {name}, which has no folder in app/modules")

    with open(os.path.join(APP, "UPLOAD.md")) as f:
        upload = f.read()
    for name in modules + sorted(rpcs):
        if f"`{name}`" not in upload:
            error(f"app/UPLOAD.md doesn't name `{name}`")

    errors.extend(iml_tests.run())

    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} problem(s) in {len(files)} files")
        sys.exit(1)
    print(f"OK: {len(files)} IML files, {len(modules)} modules, {len(rpcs)} RPCs, {len(iml_tests.TESTS)} IML tests")


if __name__ == "__main__":
    main()
