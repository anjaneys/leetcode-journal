"""Generating the per-problem README and the repo-root index.

A note on embedding video: GitHub will not play a <video> tag whose source is
a path inside the repo - its content proxy blocks it. What *does* work is
linking a poster image to the video file, because GitHub's blob view renders
an actual player for .mp4 files (including LFS-backed ones). So every entry
here is a clickable thumbnail rather than an inline player.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from . import env, postprocess, scaffold

SOLUTIONS = env.REPO / "solutions"

_BADGE = {
    "Easy": "brightgreen",
    "Medium": "orange",
    "Hard": "red",
}


def _difficulty_badge(difficulty: str) -> str:
    color = _BADGE.get(difficulty, "lightgrey")
    return "![{d}](https://img.shields.io/badge/{d}-{c}?style=flat-square)".format(
        d=difficulty, c=color)


def _media_table(folder: Path, media: dict) -> str:
    """media maps 'screen'/'camera' -> {'file': name, 'poster': name|None}."""
    cells, heads = [], []
    labels = {"screen": "Screen recording", "camera": "Camera"}
    for kind in ("screen", "camera"):
        info = media.get(kind)
        if not info:
            continue
        heads.append(labels[kind])
        link = "media/" + info["file"]
        if info.get("poster"):
            cell = "[<img src=\"media/{}\" width=\"380\">]({})".format(
                info["poster"], link)
        else:
            cell = "[Watch]({})".format(link)
        meta = []
        if info.get("duration"):
            meta.append(postprocess.human_duration(info["duration"]))
        if info.get("size"):
            meta.append(postprocess.human_size(info["size"]))
        if meta:
            cell += "<br><sub>{}</sub>".format(" &middot; ".join(meta))
        cells.append(cell)

    if not cells:
        return "_No recording attached to this solve._"

    return "\n".join([
        "| " + " | ".join(heads) + " |",
        "|" + "|".join([":--:"] * len(heads)) + "|",
        "| " + " | ".join(cells) + " |",
    ])


def problem_readme(folder: Path) -> str:
    meta_path = folder / ".meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    record = _load_record(folder)

    title = "{}. {}".format(meta.get("id", "----"), meta.get("title", folder.name))
    lines = ["# " + title, ""]

    bits = [_difficulty_badge(meta.get("difficulty", "Unknown"))]
    if meta.get("url"):
        bits.append("[Open on LeetCode]({})".format(meta["url"]))
    if record.get("solved_on"):
        bits.append("Solved **{}**".format(record["solved_on"]))
    lines += [" &nbsp;&middot;&nbsp; ".join(bits), ""]

    if meta.get("tags"):
        lines += ["`" + "`  `".join(meta["tags"]) + "`", ""]

    lines += ["## Walkthrough", "", _media_table(folder, record.get("media", {})), ""]

    notes = notes_body(folder)
    if notes:
        lines += ["## Notes", "", notes, ""]

    # The code goes inline so the problem page reads on its own, with a link
    # to the file for copying.
    blocks = []
    for name, label, fence in (("solution.py", "Python", "python"),
                               ("solution.cpp", "C++", "cpp")):
        path = folder / name
        if path.exists():
            code = _without_header(path.read_text(encoding="utf-8"), meta, fence)
            blocks += ["### {} <sub>[{}]({})</sub>".format(label, name, name), "",
                       "```" + fence, code, "```", ""]
    if blocks:
        lines += ["## Solution", ""] + blocks

    lines += ["## Problem", "", meta.get("statement", "_Statement unavailable._"), ""]
    lines += ["---", "",
              "<sub>Recorded and published with the "
              "[leetcode-journal](../../README.md) setup.</sub>", ""]
    return "\n".join(lines)


def _without_header(text: str, meta: dict, lang: str) -> str:
    """Drop the title/import header scaffold wraps around the code, since the
    README already shows the title. Files in any other shape are shown whole."""
    text = text.replace("\r\n", "\n").rstrip()
    try:
        header = scaffold.render_solution(meta, lang, "").rstrip()
    except (KeyError, OSError):
        return text
    if header and text.startswith(header):
        return text[len(header):].strip("\n")
    return text


def notes_body(folder: Path) -> str:
    """NOTES.md minus its heading, or '' when there are no notes."""
    path = folder / "NOTES.md"
    if not path.exists():
        return ""
    # utf-8-sig: Notepad and PowerShell can prepend a BOM, which would hide
    # the heading from the check below.
    lines = path.read_text(encoding="utf-8-sig").strip().splitlines()
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip()


def _load_record(folder: Path) -> dict:
    path = folder / ".record.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def save_record(folder: Path, record: dict) -> None:
    (folder / ".record.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")


def write_problem_readme(folder: Path) -> Path:
    out = folder / "README.md"
    out.write_text(problem_readme(folder), encoding="utf-8")
    return out


def rebuild_index(cfg: dict) -> Path:
    """Regenerate the repo-root README from every solutions/ folder."""
    rows, counts = [], {"Easy": 0, "Medium": 0, "Hard": 0}
    folders = sorted(
        [p for p in SOLUTIONS.iterdir() if p.is_dir()],
        key=lambda p: p.name,
    ) if SOLUTIONS.exists() else []

    for folder in folders:
        meta_path = folder / ".meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        record = _load_record(folder)
        media = record.get("media", {})

        langs = []
        if (folder / "solution.py").exists():
            langs.append("Py")
        if (folder / "solution.cpp").exists():
            langs.append("C++")

        vids = []
        for kind, label in (("screen", "screen"), ("camera", "cam")):
            if media.get(kind):
                vids.append("[{}](solutions/{}/media/{})".format(
                    label, folder.name, media[kind]["file"]))

        counts[meta.get("difficulty", "")] = counts.get(meta.get("difficulty", ""), 0) + 1
        rows.append("| {id} | [{title}]({folder}/) | {diff} | {langs} | {vids} | {date} |".format(
            id=meta.get("id", ""),
            title=meta.get("title", folder.name),
            folder="solutions/" + folder.name,
            diff=meta.get("difficulty", "-"),
            langs=", ".join(langs) or "-",
            vids=" ".join(vids) or "-",
            date=record.get("solved_on", "-"),
        ))

    total = len(rows)
    repo = cfg.get("github", {}).get("repo", "")

    lines = [
        "# LeetCode Journal",
        "",
        "Every problem I solve, recorded start to finish: the screen, the camera, "
        "the code, and what I was actually thinking.",
        "",
        "**{}** solved &nbsp;&middot;&nbsp; {} Easy &nbsp;&middot;&nbsp; {} Medium "
        "&nbsp;&middot;&nbsp; {} Hard".format(
            total, counts.get("Easy", 0), counts.get("Medium", 0), counts.get("Hard", 0)),
        "",
    ]

    if total:
        lines += [
            "| # | Problem | Difficulty | Lang | Recording | Date |",
            "|--:|---------|------------|------|-----------|------|",
        ] + rows + [""]
    else:
        lines += ["_Nothing solved yet. Run `lc new <problem>` to start._", ""]

    lines += [
        "## How this repo is produced",
        "",
        "Each solve starts from a one-click desktop launcher that opens the "
        "problem, starts recording, and publishes when I hit Finish. "
        "Underneath it is a small CLI:",
        "",
        "```",
        "lc new two-sum      pull the statement, open it on LeetCode, start recording",
        "lc save             save the solution copied from LeetCode's editor",
        "lc finish           stop recording, compress, commit, push",
        "```",
        "",
        "Recordings are compressed with ffmpeg and stored via Git LFS. Click any",
        "thumbnail to play the video on GitHub.",
        "",
        "Full setup notes are in [SETUP.md](SETUP.md).",
        "",
    ]
    if repo:
        lines += ["<sub>github.com/{}</sub>".format(repo), ""]

    out = env.REPO / "README.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
