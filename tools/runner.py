"""Running the local checks for a problem folder.

Python tests execute the generated test_solution.py directly (no pytest
dependency). C++ tests compile solution.cpp with -DLOCAL_TEST, which switches
on the main() driver at the bottom of the template.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from . import env


def run_python(folder: Path, log=print) -> bool | None:
    test = folder / "test_solution.py"
    if not test.exists():
        # Code pasted from LeetCode comes without local tests; LeetCode already
        # ran them, so just confirm the file is valid Python.
        src = folder / "solution.py"
        if not src.exists():
            return None
        log("Python")
        try:
            compile(src.read_text(encoding="utf-8"), str(src), "exec")
        except SyntaxError as exc:
            log("  syntax error: {}".format(exc))
            return False
        log("  parses (no local tests - LeetCode ran them)")
        return True
    log("Python")
    result = subprocess.run(
        [sys.executable, str(test)],
        cwd=str(folder), capture_output=True, text=True,
    )
    for line in (result.stdout + result.stderr).rstrip().splitlines():
        log("  " + line)
    return result.returncode == 0


def run_cpp(folder: Path, log=print) -> bool | None:
    src = folder / "solution.cpp"
    if not src.exists():
        return None
    gxx = env.which("g++")
    if not gxx:
        log("C++\n  skipped - g++ not found (run 'lc doctor')")
        return None

    log("C++")
    if "int main" not in src.read_text(encoding="utf-8", errors="replace"):
        # Pasted from LeetCode, so there is no driver to run; confirm it compiles.
        result = subprocess.run([gxx, "-std=c++20", "-fsyntax-only", str(src)],
                                capture_output=True, text=True)
        if result.returncode != 0:
            log("  does not compile:")
            for line in result.stderr.rstrip().splitlines()[:25]:
                log("    " + line)
            return False
        log("  compiles (no local tests - LeetCode ran them)")
        return True
    binary = folder / "solution_test.exe"
    compile_result = subprocess.run(
        [gxx, "-std=c++20", "-O2", "-DLOCAL_TEST", str(src), "-o", str(binary)],
        capture_output=True, text=True,
    )
    if compile_result.returncode != 0:
        log("  compile failed:")
        for line in compile_result.stderr.rstrip().splitlines()[:25]:
            log("    " + line)
        return False

    run_result = subprocess.run(
        [str(binary)], cwd=str(folder), capture_output=True, text=True, timeout=60)
    for line in (run_result.stdout + run_result.stderr).rstrip().splitlines():
        log("  " + line)
    binary.unlink(missing_ok=True)
    return run_result.returncode == 0


def run_all(folder: Path, log=print) -> bool:
    results = [run_python(folder, log), run_cpp(folder, log)]
    ran = [r for r in results if r is not None]
    if not ran:
        log("No runnable checks found in " + folder.name)
        return True
    return all(ran)
