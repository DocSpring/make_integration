#!/usr/bin/env python3
"""A small evaluator for the IML that this app uses, so scripts/iml_tests.py can run expressions without Make.

It covers the operators and the built-in functions the app's files use, with Make's documented behaviour: JavaScript
operators and truthiness, 1-based array indexes, `;` or `,` between arguments, and `replace()` taking a regular
expression written as '/pattern/flags' with $1-style replacements. A function it doesn't know raises an error, so a
check never passes on a guess.

Make's docs don't say whether IML string literals process backslash escapes. `evaluate(..., escapes=False)` keeps the
backslashes; the tests run the expressions that contain backslashes both ways.
"""

import json
import re
import urllib.parse


class IMLError(Exception):
    pass


UNDEFINED = None

TOKEN = re.compile(
    r"""\s*(?:
        (?P<number>\d+(?:\.\d+)?)
      | (?P<string>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
      | (?P<backtick>`[^`]*`)
      | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
      | (?P<op>===|!==|==|!=|<=|>=|&&|\|\||[-+*/%<>=!().,;\[\]])
    )""",
    re.VERBOSE,
)


def tokenize(text):
    tokens = []
    pos = 0
    while pos < len(text):
        if text[pos:].strip() == "":
            break
        match = TOKEN.match(text, pos)
        if not match:
            raise IMLError(f"can't read {text[pos:pos + 30]!r}")
        kind = match.lastgroup
        tokens.append((kind, match.group(kind)))
        pos = match.end()
    return tokens


def unescape(literal, escapes):
    body = literal[1:-1]
    if not escapes:
        return body
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": "\r"}.get(m.group(1), m.group(1)), body)


class Parser:
    """Pratt parser: a tree of tuples, evaluated by Evaluator."""

    BINARY = {
        "||": 1, "&&": 2,
        "=": 3, "==": 3, "===": 3, "!=": 3, "!==": 3,
        "<": 4, "<=": 4, ">": 4, ">=": 4,
        "+": 5, "-": 5,
        "*": 6, "/": 6, "%": 6,
    }

    def __init__(self, text, escapes):
        self.tokens = tokenize(text)
        self.pos = 0
        self.escapes = escapes

    def peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else (None, None)

    def take(self, value=None):
        token = self.peek()
        if token[0] is None or (value is not None and token[1] != value):
            raise IMLError(f"expected {value!r}, got {token[1]!r}")
        self.pos += 1
        return token

    def parse(self):
        tree = self.expression(0)
        if self.pos != len(self.tokens):
            raise IMLError(f"unexpected {self.peek()[1]!r}")
        return tree

    def expression(self, min_power):
        left = self.unary()
        while True:
            kind, value = self.peek()
            power = self.BINARY.get(value) if kind == "op" else None
            if power is None or power <= min_power:
                return left
            self.take()
            left = ("binary", value, left, self.expression(power))

    def unary(self):
        kind, value = self.peek()
        if kind == "op" and value in ("!", "-"):
            self.take()
            return ("unary", value, self.unary())
        return self.postfix(self.primary())

    def primary(self):
        kind, value = self.take()
        if kind == "number":
            return ("literal", float(value) if "." in value else int(value))
        if kind == "string":
            return ("literal", unescape(value, self.escapes))
        if kind == "op" and value == "(":
            tree = self.expression(0)
            self.take(")")
            return tree
        if kind == "name":
            if self.peek()[1] == "(":
                self.take("(")
                args = []
                if self.peek()[1] != ")":
                    while True:
                        args.append(self.expression(0))
                        if self.peek()[1] in (";", ","):
                            self.take()
                            continue
                        break
                self.take(")")
                return ("call", value, args)
            return ("name", value)
        raise IMLError(f"unexpected {value!r}")

    def postfix(self, tree):
        while True:
            kind, value = self.peek()
            if value == ".":
                self.take()
                kind, name = self.take()
                tree = ("member", tree, name[1:-1] if kind == "backtick" else name)
            elif value == "[":
                self.take()
                tree = ("index", tree, self.expression(0))
                self.take("]")
            else:
                return tree


def truthy(value):
    return value not in (None, False, 0, "") and value == value  # NaN is falsy


def to_string(value):
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dict, list)):
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return str(value)


def js_regex(search):
    """'/pattern/flags' -> (compiled pattern, global?) or None for a plain string."""
    match = re.fullmatch(r"/(.+)/([gimsuy]*)", search, re.DOTALL)
    if not match:
        return None
    pattern, flags = match.groups()
    py_flags = (re.IGNORECASE if "i" in flags else 0) | (re.MULTILINE if "m" in flags else 0) | (
        re.DOTALL if "s" in flags else 0)
    return re.compile(pattern, py_flags), "g" in flags


def js_replacement(replacement):
    # $1..$99, $& and $$, as String.prototype.replace reads them
    def sub(match):
        token = match.group(1)
        if token == "$":
            return "$"
        if token == "&":
            return "\\g<0>"
        return f"\\g<{token}>"
    return re.sub(r"\$(\$|&|\d{1,2})", sub, replacement.replace("\\", "\\\\"))


def fn_replace(text, search, replacement):
    text, replacement = to_string(text), to_string(replacement)
    regex = js_regex(search) if isinstance(search, str) else None
    if regex is None:
        return text.replace(to_string(search), replacement)
    pattern, global_ = regex
    return pattern.sub(js_replacement(replacement), text, count=0 if global_ else 1)


def fn_length(value):
    if isinstance(value, (str, list)):
        return len(value)
    raise IMLError(f"length() of {value!r}")


def fn_distinct(array, key=None):
    seen, out = [], []
    for item in array or []:
        value = item.get(key) if key is not None else item
        if value not in seen:
            seen.append(value)
            out.append(item)
    return out


def fn_get(value, path):
    for key in to_string(path).split(".") if not isinstance(path, int) else [path]:
        if isinstance(value, list) and str(key).lstrip("-").isdigit():
            index = int(key)
            position = index - 1 if index > 0 else index
            value = value[position] if -len(value) <= position < len(value) else None
        elif isinstance(value, dict):
            value = value.get(str(key))
        else:
            return None
    return value


FUNCTIONS = {
    "contains": lambda haystack, needle: haystack is not None and needle in haystack,
    "get": fn_get,
    "length": fn_length,
    "trim": lambda text: to_string(text).strip(),
    "lower": lambda text: to_string(text).lower(),
    "upper": lambda text: to_string(text).upper(),
    "encodeURL": lambda text: urllib.parse.quote(to_string(text), safe="-_.!~*'()"),
    "decodeURL": lambda text: urllib.parse.unquote(to_string(text)),
    "replace": fn_replace,
    "createJSON": lambda value: json.dumps(value, separators=(",", ":"), ensure_ascii=False),
    "join": lambda array, separator: to_string(separator).join(to_string(x) for x in array or []),
    "split": lambda text, separator: to_string(text).split(to_string(separator)),
    "first": lambda array: (array or [None])[0],
    "keys": lambda value: list(value.keys()),
    "map": lambda array, key: [item.get(key) for item in array or []],
    "distinct": fn_distinct,
    "deduplicate": lambda array: fn_distinct(array),
    "remove": lambda array, *values: [x for x in array or [] if x not in values],
    "add": lambda array, *values: list(array or []) + list(values),
    "indexOf": lambda text, search: to_string(text).find(to_string(search)),
    "toString": to_string,
    "base64": lambda text: __import__("base64").b64encode(to_string(text).encode()).decode(),
}


class Evaluator:
    def __init__(self, context):
        self.context = context

    def eval(self, tree):
        kind = tree[0]
        if kind == "literal":
            return tree[1]
        if kind == "name":
            name = tree[1]
            if name in ("true", "false"):
                return name == "true"
            if name in ("null", "undefined"):
                return None
            if name == "emptyarray":
                return []
            return self.context.get(name)
        if kind == "member":
            target = self.eval(tree[1])
            return target.get(tree[2]) if isinstance(target, dict) else None
        if kind == "index":
            target, index = self.eval(tree[1]), self.eval(tree[2])
            if isinstance(target, list) and isinstance(index, int):
                position = index - 1 if index > 0 else index
                return target[position] if -len(target) <= position < len(target) else None
            return target.get(to_string(index)) if isinstance(target, dict) else None
        if kind == "unary":
            value = self.eval(tree[2])
            return (not truthy(value)) if tree[1] == "!" else -value
        if kind == "binary":
            return self.binary(tree[1], tree[2], tree[3])
        if kind == "call":
            return self.call(tree[1], tree[2])
        raise IMLError(f"unknown node {kind}")

    def binary(self, op, left_tree, right_tree):
        left = self.eval(left_tree)
        if op == "&&":
            return self.eval(right_tree) if truthy(left) else left
        if op == "||":
            return left if truthy(left) else self.eval(right_tree)
        right = self.eval(right_tree)
        if op in ("=", "==", "==="):
            return left == right and type(left) is type(right) or (left is None and right is None)
        if op in ("!=", "!=="):
            return not (left == right and type(left) is type(right) or (left is None and right is None))
        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return to_string(left) + to_string(right)
            return left + right
        operations = {
            "-": lambda a, b: a - b, "*": lambda a, b: a * b, "/": lambda a, b: a / b, "%": lambda a, b: a % b,
            "<": lambda a, b: a < b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, ">=": lambda a, b: a >= b,
        }
        return operations[op](left, right)

    def call(self, name, args):
        if name == "if":
            condition, yes, no = args
            return self.eval(yes) if truthy(self.eval(condition)) else self.eval(no)
        if name == "ifempty":
            value = self.eval(args[0])
            return self.eval(args[1]) if value is None or value == "" else value
        if name == "switch":
            value = self.eval(args[0])
            rest = args[1:]
            for i in range(0, len(rest) - 1, 2):
                if self.eval(rest[i]) == value:
                    return self.eval(rest[i + 1])
            return self.eval(rest[-1]) if len(rest) % 2 else None
        if name not in FUNCTIONS:
            raise IMLError(f"the evaluator doesn't know {name}()")
        return FUNCTIONS[name](*[self.eval(arg) for arg in args])


def find_expressions(text):
    """Splits a value into literal text and {{expressions}}: [(is_expression, text)]."""
    parts, pos = [], 0
    while True:
        start = text.find("{{", pos)
        if start == -1:
            parts.append((False, text[pos:]))
            return [p for p in parts if p[1] != "" or p[0]]
        end = text.find("}}", start + 2)
        if end == -1:
            raise IMLError(f"unclosed {{{{ in {text[:60]!r}")
        parts.append((False, text[pos:start]))
        parts.append((True, text[start + 2:end]))
        pos = end + 2


def evaluate(value, context, escapes=True):
    """Evaluates an IML string ("{{expr}}" keeps the expression's type; anything else is text), or a JSON value."""
    if isinstance(value, dict):
        return {evaluate(k, context, escapes): evaluate(v, context, escapes) for k, v in value.items()}
    if isinstance(value, list):
        return [evaluate(v, context, escapes) for v in value]
    if not isinstance(value, str):
        return value
    parts = find_expressions(value)
    results = [Evaluator(context).eval(Parser(text, escapes).parse()) if is_expression else text
               for is_expression, text in parts]
    if len(parts) == 1 and parts[0][0]:
        return results[0]
    return "".join(to_string(r) for r in results)
