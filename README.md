# LeetCode Journal

Every problem I solve, recorded start to finish: the screen, the camera, the code, and what I was actually thinking.

**0** solved &nbsp;&middot;&nbsp; 0 Easy &nbsp;&middot;&nbsp; 0 Medium &nbsp;&middot;&nbsp; 0 Hard

_Nothing solved yet. Run `lc new <problem>` to start._

## How this repo is produced

Each solve starts from a one-click desktop launcher that opens the problem, starts recording, and publishes when I hit Finish. Underneath it is a small CLI:

```
lc new two-sum      scaffold the folder, pull the statement, start recording
lc test             compile and run the local checks
lc finish           stop recording, compress, commit, push
```

Recordings are compressed with ffmpeg and stored via Git LFS. Click any
thumbnail to play the video on GitHub.

Full setup notes are in [SETUP.md](SETUP.md).
