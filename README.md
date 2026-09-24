# LeetCode Journal

Every problem I solve, recorded start to finish: the screen, the camera, the code, and what I was actually thinking.

**7** solved &nbsp;&middot;&nbsp; 5 Easy &nbsp;&middot;&nbsp; 2 Medium &nbsp;&middot;&nbsp; 0 Hard

| # | Problem | Difficulty | Lang | Recording | Date |
|--:|---------|------------|------|-----------|------|
| 0026 | [Remove Duplicates from Sorted Array](solutions/0026-remove-duplicates-from-sorted-array/) | Easy | C++ | [screen](solutions/0026-remove-duplicates-from-sorted-array/media/screen.mp4) [cam](solutions/0026-remove-duplicates-from-sorted-array/media/camera.mp4) | 2026-09-15 |
| 0027 | [Remove Element](solutions/0027-remove-element/) | Easy | C++ | [screen](solutions/0027-remove-element/media/screen.mp4) [cam](solutions/0027-remove-element/media/camera.mp4) | 2026-09-14 |
| 0080 | [Remove Duplicates from Sorted Array II](solutions/0080-remove-duplicates-from-sorted-array-ii/) | Medium | C++ | [screen](solutions/0080-remove-duplicates-from-sorted-array-ii/media/screen.mp4) [cam](solutions/0080-remove-duplicates-from-sorted-array-ii/media/camera.mp4) | 2026-09-20 |
| 0088 | [Merge Sorted Array](solutions/0088-merge-sorted-array/) | Easy | C++ | [screen](solutions/0088-merge-sorted-array/media/screen.mp4) [cam](solutions/0088-merge-sorted-array/media/camera.mp4) | 2026-09-13 |
| 0121 | [Best Time to Buy and Sell Stock](solutions/0121-best-time-to-buy-and-sell-stock/) | Easy | C++ | [screen](solutions/0121-best-time-to-buy-and-sell-stock/media/screen.mp4) [cam](solutions/0121-best-time-to-buy-and-sell-stock/media/camera.mp4) | 2026-09-23 |
| 0169 | [Majority Element](solutions/0169-majority-element/) | Easy | C++ | [screen](solutions/0169-majority-element/media/screen.mp4) [cam](solutions/0169-majority-element/media/camera.mp4) | 2026-09-21 |
| 0189 | [Rotate Array](solutions/0189-rotate-array/) | Medium | C++ | [screen](solutions/0189-rotate-array/media/screen.mp4) [cam](solutions/0189-rotate-array/media/camera.mp4) | 2026-09-22 |

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
