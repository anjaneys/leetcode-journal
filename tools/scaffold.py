"""Creating a problem folder: statement, solution stubs, and local tests.

The interesting part is example extraction. LeetCode statements embed their
examples as plain text like:

    Input: nums = [2,7,11,15], target = 9
    Output: [0,1]

Parsing those into real Python literals means `lc test` has something to run
the moment the folder is created, instead of an empty stub you have to fill
in by hand. It is best-effort by design: anything it cannot parse becomes a
TODO rather than a crash.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

from . import env

TEMPLATES = env.REPO / "templates"
SOLUTIONS = env.REPO / "solutions"


def _split_top_level(s: str) -> list:
    """Split on commas that are not inside brackets, braces, or quotes."""
    parts, depth, buf, quote = [], 0, [], None
    for ch in s:
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "([{":
            depth += 1
            buf.append(ch)
        elif ch in ")]}":
            depth -= 1
            buf.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf))
    return [p.strip() for p in parts if p.strip()]


def _to_literal(text: str):
    """Convert a LeetCode literal into a Python object. Raises on failure."""
    text = text.strip().strip("*").strip().rstrip(",")
    # LeetCode writes JSON-flavoured booleans and nulls.
    text = re.sub(r"\btrue\b", "True", text)
    text = re.sub(r"\bfalse\b", "False", text)
    text = re.sub(r"\bnull\b", "None", text)
    return ast.literal_eval(text)


def extract_examples(statement: str) -> list:
    """Return [(args_tuple, expected), ...] parsed from the text.

    The labels arrive wrapped in markdown bold from the HTML conversion
    (`**Input:**`), so the markers have to be optional on both sides.
    """
    pairs = re.findall(
        r"\*{0,2}Input:?\*{0,2}\s*(.+?)\s*(?:\r?\n)+\s*\*{0,2}Output:?\*{0,2}\s*(.+?)(?:\r?\n|$)",
        statement, flags=re.S,
    )
    cases = []
    for raw_in, raw_out in pairs:
        raw_in = raw_in.strip().replace("\n", " ")
        raw_out = raw_out.strip()
        try:
            args = []
            for piece in _split_top_level(raw_in):
                if "=" not in piece:
                    raise ValueError("unnamed argument")
                _, _, value = piece.partition("=")
                args.append(_to_literal(value))
            expected = _to_literal(raw_out)
        except (ValueError, SyntaxError):
            continue
        cases.append((tuple(args), expected))
    return cases


def ensure_python_body(snippet: str) -> str:
    """LeetCode's Python stubs end at the signature with an empty body, which
    is a SyntaxError. Give the method a `pass` so the file imports cleanly."""
    text = (snippet or "").rstrip()
    if not text:
        return ""
    try:
        ast.parse(text)
        return text
    except SyntaxError:
        pass
    indent = 0
    for line in reversed(text.splitlines()):
        if line.strip():
            indent = len(line) - len(line.lstrip())
            break
    patched = text + "\n" + " " * (indent + 4) + "pass  # TODO"
    try:
        ast.parse(patched)
        return patched
    except SyntaxError:
        return text


def guess_method(python_snippet: str) -> str:
    m = re.search(r"def\s+(\w+)\s*\(\s*self", python_snippet or "")
    return m.group(1) if m else "solve"


def render_cases(cases: list) -> str:
    if not cases:
        return (
            "# TODO: the examples could not be parsed automatically.\n"
            "# Each entry is ((arg1, arg2, ...), expected_result).\n"
            "CASES = []\n"
        )
    lines = ["CASES = ["]
    for args, expected in cases:
        lines.append("    ({!r}, {!r}),".format(args, expected))
    lines.append("]")
    return "\n".join(lines) + "\n"


def folder_name(meta: dict) -> str:
    return "{}-{}".format(meta["id"], meta["slug"])


def _read_template(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


def create(meta: dict, languages: list, force: bool = False) -> Path:
    """Build solutions/<id>-<slug>/ and return the path."""
    dest = SOLUTIONS / folder_name(meta)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "media").mkdir(exist_ok=True)

    subs = {
        "{ID}": meta["id"],
        "{TITLE}": meta["title"],
        "{DIFFICULTY}": meta["difficulty"],
        "{URL}": meta["url"],
    }

    def fill(text: str) -> str:
        for key, val in subs.items():
            text = text.replace(key, str(val))
        return text

    py_snippet = meta["snippets"].get("python3") or meta["snippets"].get("python") or ""
    method = guess_method(py_snippet)

    if "python" in languages:
        target = dest / "solution.py"
        if force or not target.exists():
            body = ensure_python_body(py_snippet) or (
                "class Solution:\n    def {}(self):\n        pass  # TODO".format(method))
            target.write_text(
                fill(_read_template("solution.py.tmpl")).replace("{SNIPPET}", body),
                encoding="utf-8")

        target = dest / "test_solution.py"
        if force or not target.exists():
            cases = extract_examples(meta["statement"])
            text = _read_template("test_solution.py.tmpl")
            text = fill(text).replace("{CASES}", render_cases(cases))
            text = text.replace("{METHOD}", method)
            target.write_text(text, encoding="utf-8")

    if "cpp" in languages:
        target = dest / "solution.cpp"
        if force or not target.exists():
            body = (meta["snippets"].get("cpp") or "").strip() or (
                "class Solution {\npublic:\n    // TODO\n};")
            target.write_text(
                fill(_read_template("solution.cpp.tmpl")).replace("{SNIPPET}", body),
                encoding="utf-8")

    notes = dest / "NOTES.md"
    if force or not notes.exists():
        notes.write_text(
            "# Notes - {} {}\n\n"
            "## First instinct\n\nTODO\n\n"
            "## What I got stuck on\n\nTODO\n\n"
            "## The insight\n\nTODO\n\n"
            "## If I saw this again\n\nTODO\n".format(meta["id"], meta["title"]),
            encoding="utf-8")

    (dest / ".meta.json").write_text(
        __import__("json").dumps(meta, indent=2), encoding="utf-8")

    return dest
