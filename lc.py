"""lc - the LeetCode journal CLI.

    lc new two-sum        scaffold the folder, fetch the statement, start recording
    lc status             is anything recording right now?
    lc test               run the local Python and C++ checks
    lc finish             stop recording, compress, commit, push
    lc doctor             check the toolchain
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from tools import (env, leetcode, postprocess, publish, recorder, runner,
                   scaffold, workspace, writeup)


def log(msg=""):
    print(msg, flush=True)


def rule(title: str):
    log("\n" + title)
    log("-" * len(title))


# ---------------------------------------------------------------------------


def cmd_new(args) -> int:
    cfg = env.load_config()
    state = env.load_state()
    if state and any(recorder.status(state).values()):
        log("A recording is already running for '{}'.".format(state.get("slug")))
        log("Run 'lc finish' before starting another problem.")
        return 1

    if args.problem.strip().lower() == "daily":
        slug = leetcode.daily()
        if not slug:
            log("Could not look up today's daily problem. Pass one explicitly.")
            return 1
        log("Today's daily problem is {}.".format(slug))
    else:
        slug = leetcode.slugify(args.problem)
    log("Fetching {} ...".format(slug))
    meta = leetcode.fetch(slug)
    if not meta["ok"]:
        log("  ! could not reach LeetCode; scaffolding with a stub you can edit.")
        if meta.get("error"):
            log("    " + meta["error"][:140])
    else:
        log("  {} {}  [{}]".format(meta["id"], meta["title"], meta["difficulty"]))

    folder = scaffold.create(meta, cfg["languages"], force=args.force)
    log("  created solutions/{}/".format(folder.name))
    for f in sorted(folder.iterdir()):
        if f.is_file() and not f.name.startswith("."):
            log("    " + f.name)

    if args.open:
        workspace.open_problem(meta["url"])
        if workspace.open_editor(cfg, folder):
            log("  opened the problem in your browser and the code in your editor")
        else:
            log("  opened the problem in your browser (editor not found)")

    if args.no_record:
        log("\nRecording skipped (--no-record). Start it later with 'lc start'.")
        env.save_state({"slug": slug, "folder": str(folder), "recording": False})
        return 0

    rule("Recording")
    log("Starting screen + camera capture...")
    rec = recorder.start(cfg, slug)
    rec["folder"] = str(folder)
    rec["recording"] = True
    env.save_state(rec)
    log("  screen  -> {}".format(Path(rec["screen_file"]).name if rec["screen_file"] else "OBS"))
    log("  camera  -> {}".format(Path(rec["camera_file"]).name if rec["camera_file"] else "off"))
    log("\nGo solve it. When you are done:  lc finish")
    return 0


def cmd_start(args) -> int:
    cfg = env.load_config()
    state = env.load_state()
    if not state.get("folder"):
        log("No active problem. Run 'lc new <problem>' first.")
        return 1
    if any(recorder.status(state).values()):
        log("Already recording.")
        return 0
    rec = recorder.start(cfg, state["slug"])
    rec["folder"] = state["folder"]
    rec["recording"] = True
    env.save_state(rec)
    log("Recording started for {}.".format(state["slug"]))
    return 0


def cmd_stop(args) -> int:
    cfg = env.load_config()
    state = env.load_state()
    if not state:
        log("Nothing is recording.")
        return 1
    files = recorder.stop(cfg, state)
    state["recording"] = False
    state["raw"] = files
    env.save_state(state)
    log("Recording stopped.")
    for kind, path in files.items():
        if path:
            info = postprocess.probe(Path(path))
            log("  {:<7} {}  ({})".format(
                kind, Path(path).name, postprocess.human_size(info.get("size", 0))))
    log("\nRun 'lc finish' to compress, commit, and push.")
    return 0


def cmd_status(args) -> int:
    state = env.load_state()
    if not state:
        log("No active session.")
        return 0
    live = recorder.status(state)
    log("Problem : {}".format(state.get("slug", "?")))
    log("Folder  : {}".format(state.get("folder", "?")))
    if state.get("started_at"):
        started = datetime.fromisoformat(state["started_at"])
        elapsed = (datetime.now() - started).total_seconds()
        log("Started : {}  ({} ago)".format(
            started.strftime("%H:%M:%S"), postprocess.human_duration(elapsed)))
    log("Screen  : {}".format("recording" if live["screen"] else "stopped"))
    log("Camera  : {}".format("recording" if live["camera"] else "stopped"))
    return 0


def cmd_test(args) -> int:
    folder = _resolve_folder(args.problem)
    if not folder:
        return 1
    rule("Checks for " + folder.name)
    ok = runner.run_all(folder, log)
    log("\n" + ("All checks passed." if ok else "Some checks failed."))
    return 0 if ok else 1


def cmd_finish(args) -> int:
    cfg = env.load_config()
    state = env.load_state()
    if not state.get("folder"):
        log("No active problem. Run 'lc new <problem>' first.")
        return 1
    folder = Path(state["folder"])

    if any(recorder.status(state).values()):
        rule("Stopping recording")
        state["raw"] = recorder.stop(cfg, state)
        log("Stopped.")

    raw = state.get("raw") or {}
    media_dir = folder / "media"
    media_dir.mkdir(exist_ok=True)
    record = {"solved_on": date.today().isoformat(), "media": {}}

    if raw.get("screen") or raw.get("camera"):
        rule("Compressing")
    for kind in ("screen", "camera"):
        src = raw.get(kind)
        if not src or not Path(src).exists():
            continue
        src = Path(src)
        before = postprocess.probe(src)
        dest = media_dir / (kind + ".mp4")
        log("  {:<7} {} -> {}".format(
            kind, postprocess.human_size(before.get("size", 0)), dest.name))
        # The screen capture is silent by design; borrow the narration that
        # was recorded alongside the webcam.
        borrow = None
        if (kind == "screen" and raw.get("camera")
                and cfg["recorder"]["screen"].get("borrow_camera_audio", True)):
            borrow = Path(raw["camera"])
        if not postprocess.compress(src, dest, cfg["encode"][kind], log,
                                    audio_from=borrow):
            continue
        after = postprocess.probe(dest)
        entry = {
            "file": dest.name,
            "size": after.get("size", 0),
            "duration": after.get("duration", before.get("duration", 0)),
        }
        poster_path = media_dir / (kind + ".jpg")
        if postprocess.poster(dest, poster_path, min(3.0, entry["duration"] / 2 or 1)):
            entry["poster"] = poster_path.name
        record["media"][kind] = entry
        log("          {} ({})  saved {:.0f}%".format(
            postprocess.human_size(entry["size"]),
            postprocess.human_duration(entry["duration"]),
            100 * (1 - entry["size"] / before["size"]) if before.get("size") else 0))
        if entry["size"] / (1024 * 1024) > cfg["encode"]["max_mb_warn"]:
            log("          ! over {} MB - raise the CRF in config.json".format(
                cfg["encode"]["max_mb_warn"]))

    writeup.save_record(folder, record)

    rule("Writing docs")
    writeup.write_problem_readme(folder)
    log("  solutions/{}/README.md".format(folder.name))
    writeup.rebuild_index(cfg)
    log("  README.md")

    rule("Publishing")
    meta_path = folder / ".meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    if publish.commit_solve(folder, meta, args.message, log):
        if cfg["publish"]["auto_push"] and not args.no_push:
            publish.push(log)

    if not cfg["publish"]["keep_raw"] and state.get("session_dir"):
        import shutil
        shutil.rmtree(state["session_dir"], ignore_errors=True)
        log("Removed raw capture.")

    env.clear_state()
    log("\nDone.")
    return 0


def cmd_cancel(args) -> int:
    import shutil
    cfg = env.load_config()
    state = env.load_state()
    if not state:
        log("No active session.")
        return 0
    if any(recorder.status(state).values()):
        recorder.stop(cfg, state)
        log("Recording stopped.")
    session_dir = state.get("session_dir")
    if session_dir and Path(session_dir).exists():
        shutil.rmtree(session_dir, ignore_errors=True)
        log("Deleted the raw capture.")
    folder = Path(state["folder"]) if state.get("folder") else None
    if folder and folder.exists():
        if args.delete_folder:
            tracked = publish.git("ls-files", "--", str(folder), check=False).stdout.strip()
            if tracked:
                log("Kept solutions/{} - it already has committed files.".format(folder.name))
            else:
                shutil.rmtree(folder, ignore_errors=True)
                log("Deleted solutions/{}.".format(folder.name))
        else:
            log("Kept your code in solutions/{}.".format(folder.name))
    env.clear_state()
    log("Session discarded.")
    return 0


def cmd_shortcut(args) -> int:
    """Create the desktop and Start Menu shortcuts for the launcher."""
    pythonw = env.REPO / ".venv" / "Scripts" / "pythonw.exe"
    launcher = env.REPO / "launcher.pyw"
    icon = env.REPO / "assets" / "lc.ico"
    hotkey = "" if args.hotkey.lower() == "none" else args.hotkey
    # A shortcut's hotkey only fires from the Start Menu or Desktop, and two
    # shortcuts claiming the same one conflict, so only the Start Menu copy
    # carries it.
    script = r"""
$ws = New-Object -ComObject WScript.Shell
$places = @(
  @{ Dir = [Environment]::GetFolderPath('Desktop'); Hotkey = '' },
  @{ Dir = (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs'); Hotkey = '__HOTKEY__' }
)
foreach ($p in $places) {
  $lnk = $ws.CreateShortcut((Join-Path $p.Dir 'LeetCode Session.lnk'))
  $lnk.TargetPath = '__PYTHONW__'
  $lnk.Arguments = '"__LAUNCHER__"'
  $lnk.WorkingDirectory = '__REPO__'
  if (Test-Path '__ICON__') { $lnk.IconLocation = '__ICON__,0' }
  $lnk.Description = 'Record a LeetCode solve and publish it to GitHub'
  if ($p.Hotkey) { $lnk.Hotkey = $p.Hotkey }
  $lnk.Save()
  Write-Output ('  ' + $lnk.FullName)
}
"""
    for token, value in (("__PYTHONW__", pythonw), ("__LAUNCHER__", launcher),
                         ("__REPO__", env.REPO), ("__ICON__", icon),
                         ("__HOTKEY__", hotkey)):
        script = script.replace(token, str(value))
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        capture_output=True, text=True)
    if result.returncode != 0:
        log("Could not create shortcuts:\n" + (result.stderr or result.stdout).strip())
        return 1
    log("Created shortcuts:")
    log(result.stdout.rstrip())
    if hotkey:
        log("Hotkey: {} opens LeetCode Session from anywhere.".format(hotkey))
    return 0


def cmd_rebuild(args) -> int:
    cfg = env.load_config()
    count = 0
    for folder in sorted((env.REPO / "solutions").glob("*/")):
        if (folder / ".meta.json").exists():
            writeup.write_problem_readme(folder)
            count += 1
    writeup.rebuild_index(cfg)
    log("Rebuilt {} problem README(s) and the index.".format(count))
    return 0


def cmd_init_repo(args) -> int:
    cfg = env.load_config()
    if publish.has_remote():
        log("A remote is already configured: " + publish.git(
            "remote", "get-url", "origin", check=False).stdout.strip())
        return 0
    publish.ensure_lfs(log)
    writeup.rebuild_index(cfg)
    publish.git("add", "-A", check=False)
    if publish.git("diff", "--cached", "--quiet", check=False).returncode != 0:
        publish.git("commit", "-m", "Set up LeetCode journal")
    slug = publish.init_repo(cfg, args.name, not args.public, log)
    if slug:
        publish.push(log)
    return 0 if slug else 1


def cmd_devices(args) -> int:
    ffmpeg = env.require("ffmpeg")
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    rule("Capture devices")
    log("Copy the exact quoted name into config.json.\n")
    for line in (result.stderr or "").splitlines():
        if "(video)" in line or "(audio)" in line:
            log("  " + line.split("] ", 1)[-1])
    cfg = env.load_config()
    log("\nCurrently configured:")
    log("  camera : {}".format(cfg["recorder"]["camera"]["device"]))
    log("  mic    : {}".format(cfg["recorder"]["audio"]["mic_device"]))
    return 0


def cmd_doctor(args) -> int:
    cfg = env.load_config()
    rule("Toolchain")
    needed = {
        "ffmpeg": "recording and compression (winget install Gyan.FFmpeg)",
        "ffprobe": "media metadata (ships with ffmpeg)",
        "git": "version control",
        "g++": "C++ checks (winget install BrechtSanders.WinLibs.POSIX.UCRT)",
        "gh": "creating the GitHub repo (winget install GitHub.cli)",
    }
    missing = 0
    for name, why in needed.items():
        path = env.which(name)
        if path:
            log("  ok      {:<8} {}".format(name, path))
        else:
            missing += 1
            log("  MISSING {:<8} {}".format(name, why))

    rule("Git LFS")
    lfs = subprocess.run(["git", "lfs", "version"], capture_output=True, text=True)
    log("  " + ("ok      " + lfs.stdout.strip() if lfs.returncode == 0 else "MISSING git-lfs"))
    clean = publish.git("config", "--get", "filter.lfs.clean", check=False).stdout.strip()
    log("  {} LFS filter {}".format("ok     " if clean else "WARN   ",
                                    "active" if clean else "not installed - run 'git lfs install'"))
    attr = publish.git("check-attr", "filter", "--", "solutions/x/media/screen.mp4",
                       check=False).stdout
    log("  {} .mp4 routed to LFS".format("ok     " if "filter: lfs" in attr else "WARN   "))

    rule("Capture devices")
    ffmpeg = env.which("ffmpeg")
    if ffmpeg:
        out = subprocess.run(
            [ffmpeg, "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
            capture_output=True, text=True, encoding="utf-8", errors="replace").stderr or ""
        cam = cfg["recorder"]["camera"]["device"]
        mic = cfg["recorder"]["audio"]["mic_device"]
        log("  {} camera '{}'".format("ok     " if cam in out else "MISSING", cam))
        log("  {} mic    '{}'".format("ok     " if mic in out else "MISSING", mic))
        if cam not in out or mic not in out:
            log("         run 'lc devices' to list what is actually connected")

    rule("GitHub")
    remote = publish.git("remote", "get-url", "origin", check=False).stdout.strip()
    log("  " + ("ok      remote " + remote if remote
               else "WARN    no remote - run 'lc init-repo <name>'"))
    gh = env.which("gh")
    if gh:
        auth = subprocess.run([gh, "auth", "status"], capture_output=True, text=True)
        log("  " + ("ok      gh authenticated" if auth.returncode == 0
                    else "WARN    gh not signed in - run 'gh auth login'"))

    used = publish.lfs_usage_mb()
    log("\nLFS objects stored locally: {:.0f} MB (free tier is 1024 MB).".format(used))
    log("\n" + ("Everything looks good." if not missing
               else "{} tool(s) missing - see above.".format(missing)))
    return 0


# ---------------------------------------------------------------------------


def _resolve_folder(problem: str | None) -> Path | None:
    if problem:
        slug = leetcode.slugify(problem)
        matches = sorted((env.REPO / "solutions").glob("*-" + slug))
        if not matches:
            matches = sorted((env.REPO / "solutions").glob("*" + slug + "*"))
        if not matches:
            log("No solutions folder matching '{}'.".format(problem))
            return None
        return matches[-1]
    state = env.load_state()
    if state.get("folder"):
        return Path(state["folder"])
    log("No active problem. Pass one explicitly, e.g. 'lc test two-sum'.")
    return None


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="lc", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("new", help="scaffold a problem and start recording")
    s.add_argument("problem", help="slug, title, full LeetCode URL, or 'daily'")
    s.add_argument("--no-record", action="store_true", help="scaffold only")
    s.add_argument("--force", action="store_true", help="overwrite existing files")
    s.add_argument("--open", action="store_true",
                   help="open the problem page and the code editor")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("start", help="start recording the active problem")
    s.set_defaults(func=cmd_start)

    s = sub.add_parser("stop", help="stop recording without publishing")
    s.set_defaults(func=cmd_stop)

    s = sub.add_parser("status", help="show the active session")
    s.set_defaults(func=cmd_status)

    s = sub.add_parser("test", help="run local Python and C++ checks")
    s.add_argument("problem", nargs="?", help="defaults to the active problem")
    s.set_defaults(func=cmd_test)

    s = sub.add_parser("finish", help="stop, compress, commit, and push")
    s.add_argument("-m", "--message", help="custom commit message")
    s.add_argument("--no-push", action="store_true", help="commit but do not push")
    s.set_defaults(func=cmd_finish)

    s = sub.add_parser("cancel", help="stop recording and throw the session away")
    s.add_argument("--delete-folder", action="store_true",
                   help="also delete the scaffolded code folder if never committed")
    s.set_defaults(func=cmd_cancel)

    s = sub.add_parser("shortcut", help="create desktop and Start Menu shortcuts")
    s.add_argument("--hotkey", default="Ctrl+Alt+L",
                   help="global hotkey for the Start Menu shortcut, or 'none'")
    s.set_defaults(func=cmd_shortcut)

    s = sub.add_parser("rebuild", help="regenerate every README from stored metadata")
    s.set_defaults(func=cmd_rebuild)

    s = sub.add_parser("init-repo", help="create and link the GitHub repository")
    s.add_argument("name", help="repository name, e.g. leetcode-journal")
    s.add_argument("--public", action="store_true", help="make it public (default private)")
    s.set_defaults(func=cmd_init_repo)

    s = sub.add_parser("devices", help="list webcams and microphones")
    s.set_defaults(func=cmd_devices)

    s = sub.add_parser("doctor", help="check the toolchain and configuration")
    s.set_defaults(func=cmd_doctor)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except KeyboardInterrupt:
        log("\nInterrupted. If a recording is running, 'lc stop' will finalize it.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
