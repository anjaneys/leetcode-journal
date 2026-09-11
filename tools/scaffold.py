"""Creating a problem folder and turning code into solution files.

The normal flow solves on leetcode.com: `lc new` only records the problem's
metadata, and the solution file is written when the code comes back from
LeetCode's editor via `lc save`.

`lc new --stubs` is the local-editing alternative. It writes LeetCode's
starter code plus a test file whose cases are parsed from the examples in
the statement, e.g.

    Input: nums = [2,7,11,15], target = 9
    Output: [0,1]

That parsing is best-effort by design: anything it cannot parse becomes a
TODO rather than a crash.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from . import codeimport, env

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


def _fill(text: str, meta: dict) -> str:
    for key, val in (("{ID}", meta["id"]), ("{TITLE}", meta["title"]),
                     ("{DIFFICULTY}", meta["difficulty"]), ("{URL}", meta["url"])):
        text = text.replace(key, str(val))
    return text


def render_solution(meta: dict, lang: str, code: str, local_driver: bool = False) -> str:
    """Wrap code in the language's header template. The metadata placeholders
    are filled before the code goes in, so braces in the code are never
    mistaken for placeholders."""
    template = "solution.py.tmpl" if lang == "python" else "solution.cpp.tmpl"
    text = _fill(_read_template(template), meta).replace("{SNIPPET}", code.rstrip())
    if lang == "cpp" and local_driver:
        text = text.rstrip() + "\n\n" + _read_template("cpp_local_driver.tmpl")
    return text.rstrip() + "\n"


def create(meta: dict, languages: list, force: bool = False, stubs: bool = False) -> Path:
    """Build solutions/<id>-<slug>/ and return the path."""
    dest = SOLUTIONS / folder_name(meta)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "media").mkdir(exist_ok=True)
    if stubs:
        _write_stubs(dest, meta, languages, force)
    (dest / ".meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return dest


def _write_stubs(dest: Path, meta: dict, languages: list, force: bool) -> None:
    """Local-editing mode: LeetCode's starter code plus example-based tests."""
    py_snippet = meta["snippets"].get("python3") or meta["snippets"].get("python") or ""
    method = guess_method(py_snippet)

    if "python" in languages:
        target = dest / "solution.py"
        if force or not target.exists():
            body = ensure_python_body(py_snippet) or (
                "class Solution:\n    def {}(self):\n        pass  # TODO".format(method))
            target.write_text(render_solution(meta, "python", body), encoding="utf-8")

        target = dest / "test_solution.py"
        if force or not target.exists():
            text = _fill(_read_template("test_solution.py.tmpl"), meta)
            text = text.replace("{CASES}", render_cases(extract_examples(meta["statement"])))
            text = text.replace("{METHOD}", method)
            target.write_text(text, encoding="utf-8")

    if "cpp" in languages:
        target = dest / "solution.cpp"
        if force or not target.exists():
            body = (meta["snippets"].get("cpp") or "").strip() or (
                "class Solution {\npublic:\n    // TODO\n};")
            target.write_text(render_solution(meta, "cpp", body, local_driver=True),
                              encoding="utf-8")


def save_solution(folder: Path, lang: str, code: str) -> Path:
    """Write code pasted from LeetCode as this problem's solution file."""
    meta = json.loads((folder / ".meta.json").read_text(encoding="utf-8"))
    target = folder / codeimport.LANGS[lang]["file"]
    target.write_text(render_solution(meta, lang, codeimport.normalize(code)),
                      encoding="utf-8")
    return target
