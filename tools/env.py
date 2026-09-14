"""Locating the external binaries this project depends on.

winget installs land in per-user package directories that are added to the
*user* PATH, which a shell started before the install will not see. So every
lookup falls back to the known winget install roots before giving up.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Console programs (git, ffmpeg, tasklist, ...) started from a process with no
# console of its own - the pythonw launcher, the detached recording supervisor -
# each get a brand-new visible terminal window. CREATE_NO_WINDOW suppresses it.
# Every call site captures or redirects output, so nothing is lost.
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_WINGET = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"

_FALLBACKS = {
    "ffmpeg": [
        _WINGET / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
    ],
    "ffprobe": [
        _WINGET / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe",
    ],
    "g++": [
        _WINGET / "BrechtSanders.WinLibs.POSIX.UCRT_Microsoft.Winget.Source_8wekyb3d8bbwe",
    ],
    "gh": [
        Path(r"C:\Program Files\GitHub CLI"),
    ],
    "code": [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Microsoft VS Code",
    ],
}


def which(name: str) -> str | None:
    """Resolve an executable, searching PATH then known winget install roots."""
    found = shutil.which(name)
    if found:
        return found
    exe = name if name.endswith(".exe") else name + ".exe"
    for root in _FALLBACKS.get(name, []):
        if not root.exists():
            continue
        # winget nests the real binary a few levels down; rglob finds it
        # regardless of the version number in the path.
        for candidate in root.rglob(exe):
            if candidate.is_file():
                return str(candidate)
    return None


def require(name: str) -> str:
    path = which(name)
    if not path:
        raise SystemExit(
            f"error: '{name}' not found on PATH.\n"
            f"       Run 'lc doctor' to see what is missing and how to install it."
        )
    return path


def load_config() -> dict:
    with open(REPO / "config.json", encoding="utf-8") as fh:
        return json.load(fh)


def save_config(cfg: dict) -> None:
    with open(REPO / "config.json", "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, indent=2)
        fh.write("\n")


STATE = REPO / ".lc_state.json"


def load_state() -> dict:
    if not STATE.exists():
        return {}
    try:
        with open(STATE, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    with open(STATE, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)


def clear_state() -> None:
    STATE.unlink(missing_ok=True)
