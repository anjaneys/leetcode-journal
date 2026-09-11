"""Recognising a solution pasted from LeetCode's browser editor.

Code arrives via the clipboard, so the only signal for which file it belongs
in is the code itself. The checks lean on what LeetCode's starter code always
contains: C++ solutions declare `public:` inside `class Solution`, and Python
ones are `class` / `def` blocks that end in colons.
"""
from __future__ import annotations

import re
from pathlib import Path

LANGS = {
    "python": {"label": "Python", "file": "solution.py"},
    "cpp": {"label": "C++", "file": "solution.cpp"},
}

_CPP = re.compile(
    r"^\s*(public|private|protected)\s*:|#include\s*<|\bstd::"
    r"|\bvector\s*<|\bunordered_(map|set)\s*<", re.M)
_PY_BLOCK = re.compile(
    r"^\s*(class\s+\w+\s*(\([^)]*\))?|def\s+\w+\s*\(.*\)\s*(->\s*[^:]+)?)\s*:\s*(#.*)?$",
    re.M)
_TRAILING_SEMICOLON = re.compile(r";\s*$", re.M)

# Only consulted to give a helpful message when the code is not Python or C++.
_OTHER = (
    ("Java or C#", re.compile(r"\bpublic\s+[^\n;=]*\w+\s*\([^)]*\)\s*\{")),
    ("JavaScript or TypeScript", re.compile(r"\bfunction\s*\w*\s*\(|=>")),
    ("Go or Swift", re.compile(r"^\s*func\s", re.M)),
    ("Kotlin", re.compile(r"^\s*fun\s", re.M)),
    ("Rust", re.compile(r"\bfn\s+\w+|\bimpl\s+Solution\b")),
    ("C", re.compile(r"^\s*(struct\s+)?\w+\s*\**\s+\**\w+\s*\([^)]*\)\s*\{", re.M)),
)

NOT_CODE = ("No Python or C++ code on the clipboard. In LeetCode's editor "
            "press Ctrl+A, then Ctrl+C.")


def normalize(code: str) -> str:
    """Unify line endings and trim trailing whitespace and blank edges."""
    code = (code or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in code.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def detect(code: str):
    """Return (language key or None, label or the reason it was rejected)."""
    text = normalize(code)
    if not text:
        return None, "The clipboard is empty. In LeetCode's editor press Ctrl+A, then Ctrl+C."
    if _CPP.search(text):
        return "cpp", LANGS["cpp"]["label"]
    python_like = bool(_PY_BLOCK.search(text))
    if python_like and not _TRAILING_SEMICOLON.search(text):
        return "python", LANGS["python"]["label"]
    for name, pattern in _OTHER:
        if pattern.search(text):
            return None, "That looks like {} - only Python and C++ are set up.".format(name)
    if python_like:
        return "python", LANGS["python"]["label"]
    return None, NOT_CODE


def saved_languages(folder: Path) -> list:
    return [lang for lang, info in LANGS.items() if (folder / info["file"]).exists()]


def is_saved(folder: Path, lang: str, code: str) -> bool:
    """Is exactly this code already in the solution file for its language?"""
    path = folder / LANGS[lang]["file"]
    if not path.exists():
        return False
    return normalize(code) in path.read_text(encoding="utf-8").replace("\r\n", "\n")
