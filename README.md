# LeetCode Journal

Every problem I solve, recorded start to finish: the screen, the camera, the code, and what I was actually thinking.

**1** solved &nbsp;&middot;&nbsp; 1 Easy &nbsp;&middot;&nbsp; 0 Medium &nbsp;&middot;&nbsp; 0 Hard

| # | Problem | Difficulty | Lang | Recording | Date |
|--:|---------|------------|------|-----------|------|
| 0088 | [Merge Sorted Array](solutions/0088-merge-sorted-array/) | Easy | C++ | [screen](solutions/0088-merge-sorted-array/media/screen.mp4) [cam](solutions/0088-merge-sorted-array/media/camera.mp4) | 2026-09-13 |

## How this repo is produced

Each solve starts from a one-click desktop launcher that opens the problem, starts recording, and publishes when I hit Finish. Underneath it is a small CLI:

```
lc new two-sum      pull the statement, open it on LeetCode, start recording
lc save             save the solution copied from LeetCode's editor
lc finish           stop recording, compress, commit, push
```

Recordings are compressed with ffmpeg and stored via Git LFS. Click any
thumbnail to play the video on GitHub.

Full setup notes are in [SETUP.md](SETUP.md).

<sub>github.com/anjaneys/leetcode-journal</sub>
