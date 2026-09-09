"""Babysits one ffmpeg capture so it can be stopped gracefully.

Why this exists: `lc start` and `lc stop` are separate processes, so `lc stop`
has no handle on the ffmpeg it needs to end. The obvious approach - sending a
console CTRL_BREAK by PID - does not work here. ffmpeg is launched without a
console, so console control events are never delivered to it, and it ends up
being force-killed instead. A force-killed capture leaves the container
without a finalized duration, which makes every downstream length wrong.

So each capture gets a supervisor that keeps ffmpeg's stdin open. Writing "q"
there is ffmpeg's documented graceful shutdown: it flushes buffers and writes
proper trailers. The supervisor waits for a sentinel file to appear, which is
how `lc stop` reaches across the process boundary.

Usage:  python _supervise.py <sentinel> <pidfile> <log> <ffmpeg> [args...]
"""
import subprocess
import sys
import time
from pathlib import Path

POLL_SECONDS = 0.25
GRACE_SECONDS = 30


def main() -> int:
    sentinel = Path(sys.argv[1])
    pidfile = Path(sys.argv[2])
    logfile = Path(sys.argv[3])
    cmd = sys.argv[4:]

    sentinel.unlink(missing_ok=True)

    with open(logfile, "wb") as log:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        pidfile.write_text(str(proc.pid), encoding="utf-8")

        try:
            while proc.poll() is None:
                if sentinel.exists():
                    try:
                        proc.stdin.write(b"q")
                        proc.stdin.flush()
                    except OSError:
                        pass
                    try:
                        proc.wait(timeout=GRACE_SECONDS)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        try:
                            proc.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                    break
                time.sleep(POLL_SECONDS)
        finally:
            try:
                proc.stdin.close()
            except OSError:
                pass
            pidfile.unlink(missing_ok=True)
            sentinel.unlink(missing_ok=True)

    return proc.returncode or 0


if __name__ == "__main__":
    sys.exit(main())
