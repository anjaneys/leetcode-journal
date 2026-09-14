"""Turning raw captures into small, committable MP4s.

A 40-minute 1080p raw capture is typically 1-3 GB. GitHub hard-rejects any
single file over 100 MB, and the free Git LFS tier is 1 GB of storage and
1 GB/month of bandwidth - so the goal here is aggressive: get a screen
recording of mostly-static text down to tens of megabytes.

The knobs that do the work, in order of impact:
  - downscale (1920 -> 1600 wide)
  - drop frame rate (15 -> 12 fps; nobody needs 60fps of a text editor)
  - a high CRF, which is cheap on low-motion content
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import env


def probe(path: Path) -> dict:
    """Return duration/size info for a media file, or {} if unreadable."""
    ffprobe = env.which("ffprobe")
    if not ffprobe or not Path(path).exists():
        return {}
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries",
             "format=duration,size", "-of", "json", str(path)],
            capture_output=True, creationflags=env.NO_WINDOW, text=True, timeout=60,
        ).stdout
        fmt = json.loads(out).get("format", {})
        return {
            "duration": float(fmt.get("duration") or 0),
            "size": int(fmt.get("size") or 0),
        }
    except (subprocess.SubprocessError, ValueError, OSError):
        return {}


def human_size(n: int) -> str:
    if n <= 0:
        return "0 MB"
    mb = n / (1024 * 1024)
    return "{:.0f} MB".format(mb) if mb >= 1 else "{:.1f} MB".format(mb)


def human_duration(seconds: float) -> str:
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return "{}h {}m {}s".format(h, m, s)
    if m:
        return "{}m {}s".format(m, s)
    return "{}s".format(s)


def compress(src: Path, dest: Path, profile: dict, log=print,
             audio_from: Path | None = None, fill_gaps: bool = False) -> bool:
    """Transcode src -> dest using the given encode profile.

    audio_from borrows the audio track of another file - used to put the
    narration captured on the camera track onto the silent screen capture,
    so each video stands alone without opening the mic twice.
    """
    ffmpeg = env.require("ffmpeg")
    src, dest = Path(src), Path(dest)
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)

    # -2 keeps the height even (x264 requires it) while preserving aspect.
    vf = "scale='min({w},iw)':-2:flags=lanczos,fps={fps}".format(
        w=profile["scale_width"], fps=profile["fps"])

    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(src)]
    borrowing = bool(audio_from and Path(audio_from).exists())

    if borrowing:
        # Both captures stop at the same instant, but the webcam needs a couple
        # of seconds to warm up, so its track starts later and is shorter.
        # Aligning their END points is what keeps narration in sync - dropping
        # the audio in at t=0 would run it several seconds early.
        skew = probe(src).get("duration", 0) - probe(audio_from).get("duration", 0)
        if skew > 0.1:
            cmd += ["-itsoffset", "{:.3f}".format(skew)]
        elif skew < -0.1:
            cmd += ["-ss", "{:.3f}".format(-skew)]
        cmd += ["-i", str(audio_from)]

    cmd += ["-vf", vf,
            "-c:v", "libx264",
            "-preset", profile["preset"],
            "-crf", str(profile["crf"]),
            "-pix_fmt", "yuv420p"]

    if borrowing:
        # '?' makes the audio mapping optional, so a camera track that failed
        # to capture audio degrades to a silent screen video instead of an error.
        cmd += ["-map", "0:v:0", "-map", "1:a:0?"]

    if fill_gaps:
        # Joined segments leave small holes in the audio between pieces. MP4
        # audio cannot represent a hole, so without padding them with silence
        # the narration would slide earlier after every pause.
        cmd += ["-af", "aresample=async=1:first_pts=0"]

    cmd += ["-c:a", "aac", "-b:a", "{}k".format(profile["audio_kbps"]), "-ac", "1",
            # faststart puts the index at the front so GitHub can stream it
            # inline instead of downloading the whole file before playback.
            "-movflags", "+faststart",
            str(dest)]
    result = subprocess.run(cmd, capture_output=True, creationflags=env.NO_WINDOW, text=True)
    if result.returncode != 0 or not dest.exists():
        log("  ! compression failed for {}".format(src.name))
        tail = (result.stderr or "").strip().splitlines()[-4:]
        for line in tail:
            log("    " + line)
        return False
    return True


def poster(src: Path, dest: Path, at_seconds: float = 3.0) -> bool:
    """Grab a single frame to use as the README thumbnail."""
    ffmpeg = env.which("ffmpeg")
    if not ffmpeg or not Path(src).exists():
        return False
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-ss", str(at_seconds), "-i", str(src),
        "-frames:v", "1", "-vf", "scale=640:-2", "-q:v", "4",
        str(dest),
    ]
    subprocess.run(cmd, capture_output=True, creationflags=env.NO_WINDOW)
    return Path(dest).exists()


def has_audio(path: Path) -> bool:
    ffprobe = env.which("ffprobe")
    if not ffprobe or not Path(path).exists():
        return False
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            capture_output=True, creationflags=env.NO_WINDOW, text=True, timeout=60,
        ).stdout
    except (subprocess.SubprocessError, OSError):
        return False
    return bool(out.strip())


def join(files, dest: Path) -> Path | None:
    """Concatenate recorded segments end to end without re-encoding.

    Every segment comes from the same capture command, so the streams match
    and a stream copy is safe.
    """
    files = [Path(f) for f in files if Path(f).exists()]
    if not files:
        return None
    if len(files) == 1:
        return files[0]
    ffmpeg = env.require("ffmpeg")
    dest = Path(dest)
    listing = dest.with_suffix(".txt")
    # Forward slashes sidestep the concat list's backslash escaping rules.
    listing.write_text("".join(
        "file '{}'\n".format(str(f).replace("\\", "/").replace("'", "'\\''"))
        for f in files), encoding="utf-8")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-f", "concat",
         "-safe", "0", "-i", str(listing), "-c", "copy", str(dest)],
        capture_output=True, creationflags=env.NO_WINDOW, text=True)
    return dest if result.returncode == 0 and dest.exists() else None


def mux_aligned(screen: Path, camera: Path, dest: Path) -> Path | None:
    """Give one silent screen segment its camera segment's audio, aligned by
    end point (both stop together; the webcam starts late), without
    re-encoding either stream."""
    screen, camera, dest = Path(screen), Path(camera), Path(dest)
    if not screen.exists() or not camera.exists():
        return None
    ffmpeg = env.require("ffmpeg")
    skew = probe(screen).get("duration", 0) - probe(camera).get("duration", 0)
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(screen)]
    if skew > 0.1:
        cmd += ["-itsoffset", "{:.3f}".format(skew)]
    elif skew < -0.1:
        cmd += ["-ss", "{:.3f}".format(-skew)]
    cmd += ["-i", str(camera), "-map", "0:v:0", "-map", "1:a:0?", "-c", "copy", str(dest)]
    result = subprocess.run(cmd, capture_output=True, creationflags=env.NO_WINDOW, text=True)
    return dest if result.returncode == 0 and dest.exists() else None
