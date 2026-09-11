"""Opening the problem page and the solution files for a solve."""
from __future__ import annotations

import subprocess
import webbrowser
from pathlib import Path

from . import env


def open_problem(url: str | None) -> None:
    if url:
        webbrowser.open(url)


def open_editor(cfg: dict, folder: Path) -> bool:
    """Open the problem folder in the configured editor, solutions as tabs."""
    editor = env.which(cfg.get("editor", "code"))
    if not editor:
        return False
    files = [str(folder / name) for name in ("solution.py", "solution.cpp")
             if (folder / name).exists()]
    subprocess.Popen(
        [editor, str(folder)] + files,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return True
