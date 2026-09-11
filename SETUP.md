# Setup and operating notes

How this repository records, compresses, and publishes a LeetCode solve.

## One click: LeetCode Session

Open **LeetCode Session** from the desktop, the Start Menu, or with
**Ctrl+Alt+L** from anywhere.

1. Paste a problem URL (it pre-fills if one is already on your clipboard),
   type a slug or title, or press **Today's daily**.
2. **Start** opens the problem on leetcode.com and starts recording.
3. Solve it in LeetCode's own editor as usual. A small timer window starts in
   the bottom-right corner; drag it wherever it is out of the way and it
   remembers the spot.
4. When you're done, click into LeetCode's editor, press **Ctrl+A** then
   **Ctrl+C**, and click **Finish & upload**. It notices the code on your
   clipboard and saves it as `solution.py` or `solution.cpp` (the language is
   detected). Then it stops recording, compresses, commits, and pushes.

**Save code** does just the clipboard step, for saving partway through;
saving again overwrites. Finishing with nothing saved warns you rather than
publishing a solve with no code.

The **Notes** box is optional: approach, complexity, what tripped you up. It
autosaves to `NOTES.md` and appears on the problem's GitHub page. Leave it
empty and no notes file is created.

The timer window shows up in the screen recording, which is why it is small.
Untick **Keep on top** to let it sit behind the browser, or minimise it.

If you close the window mid-solve, the recording keeps running. Reopening
LeetCode Session picks the session back up. Closing is blocked while it is
compressing or pushing, because interrupting that step could leave a
half-written video.

The launcher is a thin front end: every button runs the matching `lc`
command, so everything below works the same way from a terminal. Re-run
`lc shortcut` if you move the repo folder, or `lc shortcut --hotkey none` to
drop the hotkey.

## The loop

```bash
lc new two-sum --open   # fetch the statement, open it on leetcode.com, start recording
lc save                 # save the solution on your clipboard (copied from LeetCode)
lc finish               # stop recording, compress, write the README, commit, push
```

`lc save` detects Python vs C++ itself; `--lang` overrides that, and `--file`
reads from a file instead of the clipboard. `lc finish` refuses to publish
with no saved code unless you pass `--no-code`.

Prefer writing code locally? `lc new two-sum --stubs` writes LeetCode's
starter code plus tests generated from the problem's examples, and `lc test`
runs them.

`lc new` accepts a slug, a title, or a full URL — `lc new "https://leetcode.com/problems/two-sum/"`
and `lc new "Two Sum"` both work.

Other commands:

| Command | What it does |
|---|---|
| `lc status` | Is anything recording, and for how long |
| `lc start` / `lc stop` | Control recording without scaffolding or publishing |
| `lc rebuild` | Regenerate every README from stored metadata |
| `lc devices` | List webcams and microphones with their exact names |
| `lc doctor` | Check the toolchain, LFS wiring, and devices |
| `lc cancel` | Stop recording and delete the raw video; `--delete-folder` also removes uncommitted code |
| `lc shortcut` | (Re)create the desktop and Start Menu shortcuts |
| `lc new daily` | Start today's daily challenge |
| `lc init-repo <name>` | Create the GitHub repo and push |

`lc finish --no-push` commits locally without pushing.

## What gets produced

```
solutions/0001-two-sum/
├── README.md          generated: statement, videos, your code and notes
├── NOTES.md           from the Notes box (only if you wrote any)
├── solution.py        your code, pasted from LeetCode
├── solution.cpp       ...whichever language(s) you saved
├── media/
│   ├── screen.mp4     compressed, narration muxed in   (Git LFS)
│   ├── camera.mp4     compressed webcam + mic          (Git LFS)
│   └── *.jpg          poster frames for the README
└── .meta.json         cached problem metadata
```

## Where the files live

Raw captures go to **`D:/LeetCodeJournal/raw/`**, set by `storage.raw_root` in
`config.json`. They are deliberately off the repo and off `C:`: combined
capture runs several MB/s, so a long session is multiple GB, and `C:` has far
less headroom than `D:`.

Only the compressed `.mp4`s enter the repo. Raw sessions are kept by default —
set `publish.keep_raw` to `false` to delete each one after a successful
`lc finish`, or clear out `D:/LeetCodeJournal/raw/` periodically by hand.

## How recording works

Two separate ffmpeg processes run per session:

- **screen** — `gdigrab` over the whole desktop, **video only**
- **camera** — `dshow` webcam, carrying the **microphone** as its audio track

The mic is opened exactly once. Two processes opening the same DirectShow
audio pin corrupts the clock, and the resulting files report durations several
times longer than the real recording. Post-processing muxes the narration from
the camera track onto the screen video, so both files stand alone.

Because the webcam takes a couple of seconds to initialise, the camera track
is shorter than the screen track even though they stop together. The muxing
step aligns their **end** points, not their starts — otherwise the narration
would run seconds ahead of the picture.

### Stopping cleanly

`lc start` and `lc finish` are separate processes, so `finish` has no handle on
the running ffmpeg. Each capture is therefore launched under a small
supervisor (`tools/_supervise.py`) that holds ffmpeg's stdin. Stopping writes a
sentinel file; the supervisor sends ffmpeg `q`, which is its documented
graceful shutdown.

This matters more than it sounds. ffmpeg is launched without a console, so
console control events (`CTRL_BREAK`) are never delivered to it — the earlier
approach only ever force-killed the capture, which left the container without
a finalised duration and made every reported length wrong.

Captures are written as `.mkv`, not `.mp4`. If a recording dies unexpectedly a
Matroska file is still playable; a truncated MP4 has no `moov` atom and is
unrecoverable.

## Compression

Set per-stream under `encode` in `config.json`:

| Knob | Screen | Camera | Effect |
|---|--:|--:|---|
| `scale_width` | 2560 | 640 | Biggest lever. 2560 keeps code readable on a 4480px ultrawide |
| `fps` | 12 | 24 | Nobody needs 60fps of a text editor |
| `crf` | 30 | 32 | Higher is smaller; cheap on low-motion content |

Typical result is a 94–99% reduction. Raise `crf` or lower `scale_width` if a
file lands over `encode.max_mb_warn`, which `lc finish` warns about.

## Storage budget

GitHub hard-rejects any file over **100 MB**, so videos go through **Git LFS**
(`.gitattributes` routes `*.mp4`). The free LFS tier is **1 GB of storage and
1 GB/month of bandwidth**.

A 40-minute solve lands roughly in the **50–150 MB** range for both videos
depending on how much the screen actually changes. That is very roughly
**7–15 solves** on the free tier. When you approach it, the options are a paid
LFS data pack, or moving to unlisted YouTube links and keeping only code in
the repo.

`lc doctor` prints the current local LFS total.

## Playback on GitHub

GitHub will not play a `<video>` tag pointing at a repo path — its content
proxy blocks it. What works is a poster image linked to the `.mp4`, because
GitHub's blob view renders a real player for video files, LFS-backed included.
That is why each README shows a clickable thumbnail rather than an inline
player.

## Changing devices

Run `lc devices` and copy the exact quoted name into `config.json` under
`recorder.camera.device` or `recorder.audio.mic_device`. `lc doctor` verifies
the configured names against what is actually connected.

Current setup:

- Camera — `EMEET SmartCam C960`
- Mic — `Microphone (HyperX Cloud Stinger Core (Wireless) – PS)`

## Using OBS instead of gdigrab

Set `recorder.backend` to `"obs"` in `config.json`. OBS then records the screen
(better capture on multi-monitor and fullscreen apps) while ffmpeg keeps the
webcam — the webcam must be opened by exactly one process, so do **not** add it
as an OBS source.

Requires OBS running with its WebSocket server enabled
(Tools → WebSocket Server Settings). Port and password go in the `obs` block of
`config.json`.

## Recovering an interrupted session

Raw `.mkv` files survive in `D:/LeetCodeJournal/raw/<timestamp>_<slug>/`. To
publish one after a crash, point `.lc_state.json` at it and re-run `lc finish`,
or compress by hand and drop the results into the problem's `media/` folder
before running `lc rebuild`.
