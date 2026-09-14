"""Starting and stopping the screen + camera captures.

Two independent recordings are produced per session:

  screen.mkv  - the desktop, video only
  camera.mkv  - the webcam, carrying the microphone as its audio track

The mic is opened exactly once, on the camera track. Post-processing muxes
that narration onto the screen video so both files stand alone.

They are written as Matroska rather than MP4 on purpose: if a capture is
killed abruptly (crash, reboot, Ctrl-C) an .mkv is still playable, whereas a
half-written .mp4 has no moov atom and is garbage. Post-processing transcodes
to .mp4 once the recording has ended cleanly.

The webcam is opened by exactly one process. That is why the OBS backend
records the screen only and leaves the camera to ffmpeg - two processes
fighting over a DirectShow video pin is a guaranteed failure.
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from . import env


def raw_root(cfg: dict) -> Path:
    """Where raw captures are written.

    Deliberately configurable and defaulting off the system drive: combined
    screen + camera capture runs several MB/s, so a long session is many GB.
    Keeping it outside the repo also means a stray multi-GB .mkv can never be
    staged by accident.
    """
    configured = (cfg.get("storage") or {}).get("raw_root")
    return Path(configured) if configured else env.REPO / "raw"


def _creationflags() -> int:
    # The supervisor outlives this command, so it must not share its console,
    # and it must not open a window either.
    #
    # CREATE_NO_WINDOW alone does both: the supervisor gets its own *hidden*
    # console, so closing the terminal that ran `lc` cannot take the recording
    # down with it. DETACHED_PROCESS looks like the obvious choice but is wrong
    # here: the venv's python.exe is a small redirector that re-launches the
    # real interpreter as a child, and a detached redirector's child has no
    # console to inherit - so Windows opens a visible terminal window for it,
    # which stays on screen for the entire recording.
    if sys.platform == "win32":
        return subprocess.CREATE_NO_WINDOW
    return 0


def _spawn(cmd: list, session_dir: Path, kind: str) -> int:
    """Launch a capture under a supervisor and return the ffmpeg PID."""
    sentinel = session_dir / (kind + ".stop")
    pidfile = session_dir / (kind + ".pid")
    log_path = session_dir / (kind + ".log")
    pidfile.unlink(missing_ok=True)
    sentinel.unlink(missing_ok=True)

    supervisor = Path(__file__).with_name("_supervise.py")
    subprocess.Popen(
        [sys.executable, str(supervisor), str(sentinel), str(pidfile),
         str(log_path)] + cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_creationflags(),
        close_fds=True,
    )

    # The supervisor publishes the real ffmpeg PID; without it we cannot
    # report liveness or fall back to a forced kill.
    for _ in range(80):  # up to ~8s
        if pidfile.exists():
            try:
                return int(pidfile.read_text(encoding="utf-8").strip())
            except (ValueError, OSError):
                pass
        time.sleep(0.1)
    return 0


def _request_stop(session_dir: Path, kind: str) -> None:
    (session_dir / (kind + ".stop")).write_text("stop", encoding="utf-8")


def _alive(pid: int) -> bool:
    """Is this PID still a live ffmpeg capture?

    The image-name filter is not cosmetic. Windows recycles PIDs aggressively,
    and a stale PID from a finished capture can belong to something else
    entirely by the time we look - including the console running this script.
    Signalling that would kill the caller instead of the recorder, so a bare
    PID check is never enough.
    """
    if not pid:
        return False
    try:
        out = subprocess.run(
            ["tasklist", "/FI", "PID eq {}".format(pid),
             "/FI", "IMAGENAME eq ffmpeg.exe", "/NH", "/FO", "CSV"],
            capture_output=True, creationflags=env.NO_WINDOW, text=True, timeout=10,
        ).stdout
        return "ffmpeg.exe" in out and str(pid) in out
    except (subprocess.SubprocessError, OSError):
        return False


def _screen_cmd(ffmpeg: str, cfg: dict, out: Path) -> list:
    """Screen capture, video only.

    The microphone is deliberately NOT opened here. Two processes opening the
    same DirectShow audio pin at once yields a corrupted clock - the captured
    streams end up several times longer than real elapsed time. The mic is
    captured once, on the camera track, and post-processing muxes that audio
    onto this video so the screen recording is still watchable on its own.
    """
    r = cfg["recorder"]["screen"]
    return [
        ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
        # Stamp frames with real arrival time so the file's duration matches
        # the wall clock even when the grabber cannot hit the target rate.
        "-use_wallclock_as_timestamps", "1",
        "-f", "gdigrab",
        "-framerate", str(r["framerate"]),
        "-draw_mouse", "1" if r.get("capture_cursor", True) else "0",
        "-i", "desktop",
        # ultrafast + a mid CRF keeps CPU free for you to actually think; the
        # file is recompressed properly later.
        "-c:v", "libx264", "-preset", "ultrafast",
        "-crf", str(r.get("capture_crf", 26)),
        "-pix_fmt", "yuv420p", "-g", str(r["framerate"] * 2),
        "-fps_mode", "vfr",
        "-an",
        str(out),
    ]


def _camera_cmd(ffmpeg: str, cfg: dict, out: Path) -> list:
    """Webcam capture, carrying the microphone as its audio track."""
    c = cfg["recorder"]["camera"]
    mic = cfg["recorder"]["audio"]["mic_device"]
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
        "-use_wallclock_as_timestamps", "1",
        "-f", "dshow",
        "-rtbufsize", "256M",
        "-framerate", str(c["framerate"]),
        "-video_size", c["size"],
    ]
    if mic:
        # One dshow input carrying both pins keeps webcam video and mic audio
        # on a shared clock, which avoids the drift two separate inputs give.
        cmd += ["-i", "video={}:audio={}".format(c["device"], mic)]
    else:
        cmd += ["-i", "video={}".format(c["device"])]
    cmd += ["-c:v", "libx264", "-preset", "ultrafast",
            "-crf", str(c.get("capture_crf", 28)),
            "-pix_fmt", "yuv420p", "-fps_mode", "vfr"]
    if mic:
        cmd += ["-c:a", "aac", "-b:a", "128k"]
    cmd += [str(out)]
    return cmd


# --------------------------------------------------------------------------
# OBS backend (screen only)
# --------------------------------------------------------------------------

def _obs_client(cfg: dict):
    import obsws_python as obs
    o = cfg["obs"]
    return obs.ReqClient(host=o["host"], port=o["port"],
                         password=o["password"], timeout=5)


def obs_start(cfg: dict) -> str:
    cl = _obs_client(cfg)
    if cl.get_record_status().output_active:
        cl.stop_record()
        time.sleep(1.0)
    cl.start_record()
    return "obs"


def obs_stop(cfg: dict):
    try:
        cl = _obs_client(cfg)
        if not cl.get_record_status().output_active:
            return None
        return cl.stop_record().output_path
    except Exception:
        return None


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def start(cfg: dict, slug: str) -> dict:
    """Begin recording. Returns a state dict describing the live session."""
    ffmpeg = env.require("ffmpeg")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    root = raw_root(cfg)
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SystemExit(
            "error: cannot write to the capture folder {}\n"
            "       {}\n"
            "       Check that the drive is connected, or change "
            "storage.raw_root in config.json.".format(root, exc))
    session_dir = root / "{}_{}".format(stamp, slug)
    session_dir.mkdir(parents=True, exist_ok=True)

    backend = cfg["recorder"].get("backend", "ffmpeg")
    state = {
        "slug": slug,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "session_dir": str(session_dir),
        "backend": backend,
        "screen_pid": 0,
        "camera_pid": 0,
        "screen_file": "",
        "camera_file": "",
        "obs_recording": False,
    }

    if cfg["recorder"]["screen"]["enabled"]:
        if backend == "obs":
            obs_start(cfg)
            state["obs_recording"] = True
        else:
            out = session_dir / "screen.mkv"
            state["screen_pid"] = _spawn(
                _screen_cmd(ffmpeg, cfg, out), session_dir, "screen")
            state["screen_file"] = str(out)

    if cfg["recorder"]["camera"]["enabled"]:
        out = session_dir / "camera.mkv"
        state["camera_pid"] = _spawn(
            _camera_cmd(ffmpeg, cfg, out), session_dir, "camera")
        state["camera_file"] = str(out)

    # Give ffmpeg a moment to fail loudly (bad device name, device already in
    # use) rather than discovering it 40 minutes later.
    time.sleep(3.0)
    problems = []
    for kind in ("screen", "camera"):
        pid = state[kind + "_pid"]
        if pid and not _alive(pid):
            log_file = session_dir / (kind + ".log")
            log = log_file.read_text(errors="replace").strip() if log_file.exists() else ""
            tail = "\n".join(log.splitlines()[-6:]) or "(no output)"
            problems.append("{} capture died on startup:\n{}".format(kind, tail))
    if problems:
        stop(cfg, state)
        raise SystemExit("error: " + "\n\nerror: ".join(problems))

    return state


def stop(cfg: dict, state: dict) -> dict:
    """End the recording, letting ffmpeg finalize its files."""
    results = {"screen": None, "camera": None}
    session_dir = Path(state.get("session_dir", "")) if state.get("session_dir") else None

    for kind in ("screen", "camera"):
        pid = state.get(kind + "_pid") or 0
        path = state.get(kind + "_file")
        if not pid or not _alive(pid) or session_dir is None:
            if path and Path(path).exists():
                results[kind] = path
            continue

        # Ask the supervisor to send ffmpeg a 'q' so it writes a proper
        # trailer. A force-kill here would leave the duration unset and make
        # every reported length wrong.
        _request_stop(session_dir, kind)
        for _ in range(200):  # up to ~40s; long captures take a moment to flush
            if not _alive(pid):
                break
            time.sleep(0.2)
        if _alive(pid):
            subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                           capture_output=True, creationflags=env.NO_WINDOW, timeout=15)
            time.sleep(0.5)
        if path and Path(path).exists():
            results[kind] = path

    if state.get("obs_recording"):
        results["screen"] = obs_stop(cfg) or results["screen"]

    return results


def status(state: dict) -> dict:
    return {
        "screen": _alive(state.get("screen_pid") or 0),
        "camera": _alive(state.get("camera_pid") or 0),
    }
