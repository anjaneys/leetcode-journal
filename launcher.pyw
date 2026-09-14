"""LeetCode Session - the one-click front end for the lc pipeline.

Open the shortcut (or press Ctrl+Alt+L), pick a problem, and it opens the
problem on leetcode.com and starts recording. You solve in LeetCode's own
editor while a small timer window stays up. When you're done, copy your code
(Ctrl+A, Ctrl+C in LeetCode's editor) and click Finish & upload: it picks the
code up from the clipboard, then compresses, commits, and pushes.

Every action shells out to lc.py rather than calling into it, so the GUI and
the CLI share one code path and cannot drift apart.
"""
from __future__ import annotations

import ctypes
import json
import os
import queue
import subprocess
import sys
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

REPO = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO))

from tools import clipboard, codeimport, env, publish, writeup  # noqa: E402

# lc.py runs under the console interpreter even though this window runs under
# pythonw: pythonw has no usable stdout, and lc's output is what the log shows.
PYTHON = Path(sys.executable).with_name("python.exe")
if not PYTHON.exists():
    PYTHON = Path(sys.executable)
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Where the session window was last dragged to. Per machine, so gitignored.
PREFS = REPO / ".launcher.json"

ORANGE = "#ffa116"
RED = "#d93025"
GREEN = "#1e8e3e"
MUTED = "#6b6b6b"
DIFFICULTY_COLOR = {"Easy": "#00a88f", "Medium": "#d98200", "Hard": "#e0224f"}


def fmt_elapsed(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return "{}:{:02d}:{:02d}".format(h, m, s) if h else "{:02d}:{:02d}".format(m, s)


def load_prefs() -> dict:
    try:
        return json.loads(PREFS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_prefs(prefs: dict) -> None:
    try:
        PREFS.write_text(json.dumps(prefs), encoding="utf-8")
    except OSError:
        pass


def virtual_screen():
    """Bounds of the whole desktop across every monitor: x, y, width, height."""
    metric = ctypes.windll.user32.GetSystemMetrics
    return metric(76), metric(77), metric(78), metric(79)


def parse_position(geometry: str):
    """'470x336+2075+1056' -> (2075, 1056). Tk writes negatives as '+-12'."""
    try:
        _size, x, y = geometry.replace("+", " ").split()
        return int(x), int(y)
    except ValueError:
        return None


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.events = queue.Queue()
        self.busy = False
        self.view = None
        self.gen = 0          # bumps per view so stale timers stop themselves
        self.buttons = []
        self.logbox = None
        self._pending_log = None
        self._notes_job = None
        self._pos_job = None
        self.notes = None
        self._notes_baseline = ""
        self.live = None
        self.state = {}
        self.folder = None

        root.title("LeetCode Session")
        root.resizable(False, False)
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.bind("<Configure>", self._on_configure)
        self._style()
        icon = REPO / "assets" / "lc.png"
        if icon.exists():
            self._icon = tk.PhotoImage(file=str(icon))
            root.iconphoto(True, self._icon)

        root.after(100, self._drain)
        if env.load_state().get("folder"):
            self.show_session()  # pick up a session left running earlier
        else:
            self.show_start()
        root.after(50, self._bring_to_front)

    # ------------------------------------------------------------------ look

    def _style(self):
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("H.TLabel", font=("Segoe UI Semibold", 13))
        style.configure("Muted.TLabel", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Timer.TLabel", font=("Segoe UI Light", 30))
        style.configure("Rec.TLabel", foreground=RED, font=("Segoe UI Semibold", 10))
        style.configure("Idle.TLabel", foreground=MUTED, font=("Segoe UI Semibold", 10))
        style.configure("Warn.TLabel", foreground="#b06000", font=("Segoe UI", 9))
        style.configure("Pass.TLabel", foreground=GREEN, font=("Segoe UI Semibold", 9))
        style.configure("Fail.TLabel", foreground=RED, font=("Segoe UI Semibold", 9))
        style.configure("Link.TLabel", foreground="#1a73e8", font=("Segoe UI", 9, "underline"))
        style.configure("Primary.TButton", font=("Segoe UI Semibold", 10))
        for name, color in DIFFICULTY_COLOR.items():
            style.configure(name + ".TLabel", foreground=color,
                            font=("Segoe UI Semibold", 10))

    def _clear(self):
        self._flush_notes()
        for child in self.root.winfo_children():
            child.destroy()
        self.buttons = []
        self.logbox = None
        self._pending_log = None
        self.notes = None
        self.gen += 1

    def _make_log(self, parent, height: int, lazy: bool = False):
        """lazy=True keeps the box hidden until the first line arrives, so an
        idle window is not dominated by an empty grey panel."""
        box = tk.Text(parent, height=height, width=60, font=("Consolas", 9),
                      relief="flat", background="#f4f4f4", foreground="#333333",
                      wrap="word", state="disabled", borderwidth=0, padx=8, pady=6)
        if lazy:
            self._pending_log = box
        else:
            box.pack(fill="both", expand=True, pady=(12, 0))
        return box

    def _link(self, parent, text, command):
        label = ttk.Label(parent, text=text, style="Link.TLabel", cursor="hand2")
        label.bind("<Button-1>", lambda _e: command())
        label.pack(side="left", padx=(0, 12))

    def _center(self):
        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 3
        self.root.geometry("+{}+{}".format(x, y))

    def _dock(self):
        """Place the session window where it was last dragged to, or the
        bottom-right corner the first time. It sits over LeetCode's page and
        shows in the recording, so where it lives is the user's call."""
        self.root.update_idletasks()
        w, h = self.root.winfo_reqwidth(), self.root.winfo_reqheight()
        vx, vy, vw, vh = virtual_screen()
        saved = load_prefs().get("session_pos")
        if (isinstance(saved, list) and len(saved) == 2
                and vx <= saved[0] <= vx + vw - 100 and vy <= saved[1] <= vy + vh - 100):
            x, y = saved
            y = max(vy, min(y, vy + vh - h - 60))  # keep the bottom on screen
        else:
            x = self.root.winfo_screenwidth() - w - 24
            y = self.root.winfo_screenheight() - h - 80
        self.root.geometry("+{}+{}".format(x, y))

    def _on_configure(self, event):
        # Toplevel bindings also fire for every child widget; only the window
        # itself moving matters here.
        if event.widget is not self.root or self.view != "session":
            return
        if self._pos_job:
            self.root.after_cancel(self._pos_job)
        self._pos_job = self.root.after(500, self._save_position)

    def _save_position(self):
        self._pos_job = None
        if self.view != "session":
            return
        position = parse_position(self.root.geometry())
        if position:
            prefs = load_prefs()
            prefs["session_pos"] = list(position)
            save_prefs(prefs)

    def _bring_to_front(self):
        """Land on top with keyboard focus when launched.

        Windows' focus-stealing rules can otherwise open the window *behind*
        whatever is in front - pressing the hotkey would appear to do nothing.
        Briefly going topmost, then restoring, is the reliable way through.
        """
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.after(400, self._restore_topmost)

    def _restore_topmost(self):
        pin = getattr(self, "pin", None)
        pinned = self.view == "session" and bool(pin is not None and pin.get())
        self.root.attributes("-topmost", pinned)

    # ---------------------------------------------------------- plumbing

    def run_lc(self, args, done=None):
        """Run `lc <args>` in the background, streaming output into the log."""
        self.busy = True
        self._enable(False)
        self.log("> lc " + " ".join(args))

        def work():
            lines = []
            try:
                proc = subprocess.Popen(
                    [str(PYTHON), str(REPO / "lc.py")] + list(args),
                    cwd=str(REPO),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True, encoding="utf-8", errors="replace",
                    env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                    creationflags=NO_WINDOW,
                )
                for line in proc.stdout:
                    line = line.rstrip()
                    lines.append(line)
                    self.events.put(("line", line))
                code = proc.wait()
            except OSError as exc:
                self.events.put(("line", "error: {}".format(exc)))
                code = 1
            self.events.put(("done", (code, "\n".join(lines), done)))

        threading.Thread(target=work, daemon=True).start()

    def _drain(self):
        # Tk is single-threaded: workers post events, this loop applies them.
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "line":
                    self.log(payload)
                elif kind == "done":
                    code, output, callback = payload
                    self.busy = False
                    self._enable(True)
                    if callback:
                        callback(code, output)
        except queue.Empty:
            pass
        self.root.after(100, self._drain)

    def _enable(self, on: bool):
        for button in self.buttons:
            try:
                button.state(["!disabled"] if on else ["disabled"])
            except tk.TclError:
                pass

    def log(self, text: str):
        if not self.logbox:
            return
        if self._pending_log is self.logbox:
            self.logbox.pack(fill="both", expand=True, pady=(12, 0))
            self._pending_log = None
            if self.view == "session":
                self._dock()  # it just grew; keep the bottom on screen
        self.logbox.configure(state="normal")
        self.logbox.insert("end", text + "\n")
        self.logbox.see("end")
        self.logbox.configure(state="disabled")

    # ------------------------------------------------------------- start

    def show_start(self, carry: str | None = None):
        self._clear()
        self.view = "start"
        self.root.attributes("-topmost", False)

        f = ttk.Frame(self.root, padding=(18, 16))
        f.pack(fill="both", expand=True)
        ttk.Label(f, text="Start a LeetCode session", style="H.TLabel").pack(anchor="w")
        ttk.Label(f, text="Paste a problem URL, a slug like two-sum, or a title.",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 10))

        self.entry = ttk.Entry(f, width=52, font=("Segoe UI", 10))
        self.entry.pack(fill="x")
        self.entry.bind("<Return>", lambda _e: self.start())
        clip = clipboard.read_text().strip()
        if "leetcode.com/problems/" in clip and len(clip) < 300:
            self.entry.insert(0, clip)
        self.entry.focus_set()

        opts = ttk.Frame(f)
        opts.pack(fill="x", pady=(10, 0))
        self.record_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(opts, text="Record screen + camera",
                        variable=self.record_var).pack(side="left")

        start = ttk.Button(opts, text="Start", style="Primary.TButton", command=self.start)
        daily = ttk.Button(opts, text="Today's daily", command=lambda: self.start("daily"))
        start.pack(side="right")
        daily.pack(side="right", padx=6)
        self.buttons = [start, daily]

        if not publish.has_remote():
            warn = ttk.Frame(f)
            warn.pack(fill="x", pady=(12, 0))
            ttk.Label(warn, text="No GitHub repo linked yet - solves stay on this PC.",
                      style="Warn.TLabel").pack(side="left")
            link = ttk.Button(warn, text="Link repo...", command=self.link_repo)
            link.pack(side="right")
            self.buttons.append(link)

        self.logbox = self._make_log(f, height=7, lazy=True)
        if carry:
            self.log(carry)
        self._center()

    def start(self, problem: str | None = None):
        if self.busy:
            return
        problem = problem or self.entry.get().strip()
        if not problem:
            messagebox.showinfo("LeetCode Session", "Enter a problem first.", parent=self.root)
            return
        args = ["new", problem, "--open"]
        if not self.record_var.get():
            args.append("--no-record")
        self.run_lc(args, done=self._started)

    def _started(self, code, output):
        if code == 0 and env.load_state().get("folder"):
            self.show_session()
        else:
            self.log("Could not start - see the messages above.")

    def link_repo(self):
        name = simpledialog.askstring("Link GitHub repo", "Repository name:",
                                      initialvalue="leetcode-journal", parent=self.root)
        if not name:
            return
        public = messagebox.askyesno(
            "Repository visibility",
            "Make the repository public?\n\nChoose No for private. The videos "
            "include your camera, so private is the safer default until you "
            "decide.", parent=self.root)
        args = ["init-repo", name.strip()] + (["--public"] if public else [])
        self.run_lc(args, done=lambda _c, output: self.show_start(carry=output))

    # ----------------------------------------------------------- session

    def _meta(self) -> dict:
        try:
            return json.loads((self.folder / ".meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def show_session(self, state: dict | None = None):
        self._clear()
        self.view = "session"
        self.state = state or env.load_state()
        self.folder = Path(self.state["folder"])
        self.live = None
        meta = self._meta()
        recording = bool(self.state.get("recording"))

        f = ttk.Frame(self.root, padding=(16, 12))
        f.pack(fill="both", expand=True)

        top = ttk.Frame(f)
        top.pack(fill="x")
        number = (meta.get("id") or "").lstrip("0")
        title = meta.get("title") or self.folder.name
        ttk.Label(top, text="{}. {}".format(number, title) if number else title,
                  style="H.TLabel").pack(side="left")
        difficulty = meta.get("difficulty")
        if difficulty in DIFFICULTY_COLOR:
            ttk.Label(top, text=difficulty, style=difficulty + ".TLabel").pack(
                side="left", padx=8, pady=(3, 0))

        mid = ttk.Frame(f)
        mid.pack(fill="x")
        self.timer = ttk.Label(mid, text="00:00", style="Timer.TLabel")
        self.timer.pack(side="left")
        self.rec = ttk.Label(mid, text="", style="Rec.TLabel")
        self.rec.pack(side="left", padx=12, pady=(12, 0))

        row = ttk.Frame(f)
        row.pack(fill="x", pady=(4, 0))
        save = ttk.Button(row, text="Save code", command=self.save_code)
        finish = ttk.Button(row, text="Finish & upload", style="Primary.TButton",
                            command=self.finish)
        discard = ttk.Button(row, text="Discard", command=self.discard)
        save.pack(side="left")
        finish.pack(side="left", padx=6)
        discard.pack(side="right")
        self.buttons = [save, finish, discard]
        if not recording:
            record = ttk.Button(row, text="Start recording", command=self.start_recording)
            record.pack(side="left")
            self.buttons.append(record)

        self.code_status = ttk.Label(f, text="", style="Muted.TLabel",
                                     wraplength=430, justify="left")
        self.code_status.pack(anchor="w", pady=(8, 0))

        links = ttk.Frame(f)
        links.pack(fill="x", pady=(8, 0))
        self._link(links, "Problem", lambda: webbrowser.open(meta.get("url") or ""))
        self._link(links, "Folder", lambda: os.startfile(str(self.folder)))
        self.pin = tk.BooleanVar(value=True)
        ttk.Checkbutton(links, text="Keep on top", variable=self.pin,
                        command=self._apply_pin).pack(side="right")

        ttk.Label(f, text="Notes (optional): your approach, complexity, what tripped you up",
                  style="Muted.TLabel").pack(anchor="w", pady=(10, 3))
        self.notes = tk.Text(f, height=4, width=56, font=("Segoe UI", 9), wrap="word",
                             relief="solid", borderwidth=1, padx=6, pady=4)
        self.notes.pack(fill="x")
        existing = writeup.notes_body(self.folder)
        self._notes_baseline = existing
        if existing:
            self.notes.insert("1.0", existing)
        self.notes.edit_modified(False)
        self.notes.bind("<<Modified>>", self._notes_changed)

        self.logbox = self._make_log(f, height=5, lazy=True)
        self._apply_pin()
        self._paint_rec()
        self._paint_code_status()
        self._dock()
        self._tick(self.gen)

    def _apply_pin(self):
        self.root.attributes("-topmost", bool(self.pin.get()))

    def _tick(self, gen: int):
        if gen != self.gen:
            return
        started = self.state.get("started_at")
        if self.state.get("recording") and started:
            try:
                elapsed = (datetime.now() - datetime.fromisoformat(started)).total_seconds()
            except ValueError:
                elapsed = 0
            self.timer.configure(text=fmt_elapsed(elapsed))
        else:
            self.timer.configure(text="--:--")
        self.root.after(1000, lambda: self._tick(gen))

    def _paint_rec(self):
        if self.view != "session":
            return
        if self.state.get("recording"):
            self.rec.configure(text="● REC", style="Rec.TLabel")
        else:
            self.rec.configure(text="not recording", style="Idle.TLabel")

    def _paint_code_status(self):
        if self.view != "session":
            return
        langs = codeimport.saved_languages(self.folder)
        if langs:
            names = " + ".join(codeimport.LANGS[lang]["label"] for lang in langs)
            self.code_status.configure(text="{} code saved ✓".format(names),
                                       style="Pass.TLabel")
        else:
            self.code_status.configure(
                text="Code not saved yet. When you're done, press Ctrl+A then "
                     "Ctrl+C in LeetCode's editor.", style="Muted.TLabel")

    # ------------------------------------------------------------- notes

    def _notes_changed(self, _event=None):
        if self.notes is None or not self.notes.edit_modified():
            return
        self.notes.edit_modified(False)
        if self._notes_job:
            self.root.after_cancel(self._notes_job)
        self._notes_job = self.root.after(800, self._save_notes)

    def _flush_notes(self):
        if self._notes_job:
            self.root.after_cancel(self._notes_job)
        self._save_notes()

    def _save_notes(self):
        """Autosave the notes box to NOTES.md; an empty box means no file."""
        self._notes_job = None
        if self.notes is None or not self.folder or not self.folder.exists():
            return
        try:
            text = self.notes.get("1.0", "end").strip()
        except tk.TclError:
            return
        if text == self._notes_baseline:
            return  # untouched since loaded - never clobber an edit made elsewhere
        self._notes_baseline = text
        path = self.folder / "NOTES.md"
        if text:
            meta = self._meta()
            heading = "# Notes - {}. {}".format(
                (meta.get("id") or "").lstrip("0") or "?", meta.get("title") or self.folder.name)
            content = heading + "\n\n" + text + "\n"
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                path.write_text(content, encoding="utf-8")
        elif path.exists():
            path.unlink()

    # ----------------------------------------------------------- actions

    def start_recording(self):
        self.run_lc(["start"], done=lambda _c, output: self.show_session())

    def save_code(self, then=None):
        self.run_lc(["save"], done=lambda code, output: self._code_saved(code, output, then))

    def _code_saved(self, code, output, then):
        self._paint_code_status()
        if code != 0:
            reason = output.strip().splitlines()[-1] if output.strip() else codeimport.NOT_CODE
            messagebox.showinfo("Nothing saved", reason, parent=self.root)
            return
        if then:
            then()

    def finish(self):
        self._flush_notes()
        where = ("push everything to GitHub" if publish.has_remote()
                 else "commit it on this PC (no GitHub repo linked yet)")
        clip = clipboard.read_text()
        lang, _reason = codeimport.detect(clip)
        unsaved = bool(lang) and not codeimport.is_saved(self.folder, lang, clip)
        have_code = bool(codeimport.saved_languages(self.folder))

        if unsaved:
            answer = messagebox.askyesnocancel(
                "Finish & upload",
                "Your clipboard has {} code that hasn't been saved yet.\n\n"
                "Yes - save it, then stop recording and {}\n"
                "No - finish without it\n"
                "Cancel - keep working".format(codeimport.LANGS[lang]["label"], where),
                parent=self.root)
            if answer is None:
                return
            if answer:
                self.save_code(then=self._finish_now)
                return
            if not have_code and not self._confirm_no_code():
                return
            self._finish_now(no_code=not have_code)
            return

        if not have_code:
            if self._confirm_no_code():
                self._finish_now(no_code=True)
            return

        if messagebox.askyesno("Finish & upload",
                               "Stop recording, compress the videos, and {}?".format(where),
                               parent=self.root):
            self._finish_now()

    def _confirm_no_code(self) -> bool:
        return messagebox.askyesno(
            "No code saved",
            "You haven't saved your solution.\n\n"
            "In LeetCode's editor press Ctrl+A then Ctrl+C, and click Finish "
            "again - it will pick the code up.\n\n"
            "Publish the recording without any code?",
            icon="warning", parent=self.root)

    def _finish_now(self, no_code: bool = False):
        self.finished_folder = self.folder.name
        self.code_status.configure(
            text="Compressing and publishing - this can take a minute for a long solve.",
            style="Muted.TLabel")
        self.run_lc(["finish"] + (["--no-code"] if no_code else []), done=self._finished)

    def _finished(self, code, output):
        if code != 0:
            tail = "\n".join(output.strip().splitlines()[-4:])
            messagebox.showerror(
                "Finish failed",
                tail + "\n\nThe raw recording on D: is untouched.", parent=self.root)
            self._paint_code_status()
            return
        cfg = env.load_config()
        repo = (cfg.get("github") or {}).get("repo")
        branch = (cfg.get("github") or {}).get("branch") or "main"
        if "Pushed." in output and repo:
            if messagebox.askyesno("Published", "Uploaded to GitHub. Open it?",
                                   parent=self.root):
                webbrowser.open("https://github.com/{}/tree/{}/solutions/{}".format(
                    repo, branch, self.finished_folder))
        elif "Push failed" in output:
            messagebox.showwarning(
                "Saved, not uploaded",
                "Committed on this PC, but the push to GitHub failed - see the "
                "log. It will go up with your next successful push.",
                parent=self.root)
        else:
            messagebox.showinfo("Saved", "Committed on this PC.", parent=self.root)
        self.show_start(carry=output)

    def discard(self):
        if not messagebox.askyesno(
                "Discard session",
                "Stop recording and delete the raw video?\n\n"
                "Anything saved in solutions/{} is kept.".format(self.folder.name),
                parent=self.root):
            return
        self.run_lc(["cancel"], done=lambda _c, output: self.show_start(carry=output))

    # ------------------------------------------------------------- close

    def on_close(self):
        if self.busy:
            messagebox.showinfo(
                "Still working",
                "Wait for the current step to finish before closing - "
                "interrupting it could leave a half-written video.", parent=self.root)
            return
        if self.view == "session" and self.state.get("recording"):
            if not messagebox.askokcancel(
                    "Recording is still running",
                    "Closing this window leaves the recording running in the "
                    "background.\n\nOpen LeetCode Session again to finish or "
                    "discard it.", parent=self.root):
                return
        self._flush_notes()
        self.root.destroy()


def _smoke_test() -> None:
    """Build both views off-screen and exit; used to verify the UI constructs."""
    root = tk.Tk()
    app = App(root)
    app.show_start()
    fake = {"folder": str(REPO / "solutions" / "_smoke"), "slug": "smoke",
            "recording": True, "started_at": datetime.now().isoformat(timespec="seconds")}
    app.show_session(fake)
    root.after(1500, root.destroy)
    root.mainloop()
    print("smoke ok")


def main() -> None:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # crisp text on high-DPI
    except (AttributeError, OSError):
        pass

    if "--smoke" in sys.argv:
        _smoke_test()
        return

    # One window at a time - two launchers would fight over the same session.
    global _MUTEX
    _MUTEX = ctypes.windll.kernel32.CreateMutexW(None, False, "LeetCodeJournal.Session")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        # Pressing the hotkey again should surface the open window, not nag.
        hwnd = ctypes.windll.user32.FindWindowW(None, "LeetCode Session")
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("LeetCode Session", "LeetCode Session is already open.")
        return

    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # pythonw has no console, so an unhandled error would vanish silently.
        detail = traceback.format_exc()
        (REPO / "launcher-error.log").write_text(detail, encoding="utf-8")
        try:
            messagebox.showerror("LeetCode Session crashed", detail[-1500:])
        except tk.TclError:
            pass
