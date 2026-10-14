# 0274. H-Index

![Medium](https://img.shields.io/badge/Medium-orange?style=flat-square) &nbsp;&middot;&nbsp; [Open on LeetCode](https://leetcode.com/problems/h-index/) &nbsp;&middot;&nbsp; Solved **2026-10-13**

`Array`  `Sorting`  `Counting Sort`

## Walkthrough

| Screen recording | Camera |
|:--:|:--:|
| [<img src="media/screen.jpg" width="380">](media/screen.mp4)<br><sub>5m 18s &middot; 4 MB</sub> | [<img src="media/camera.jpg" width="380">](media/camera.mp4)<br><sub>5m 14s &middot; 4 MB</sub> |

## Solution

### C++ <sub>[solution.cpp](solution.cpp)</sub>

```cpp
class Solution {
public:
    int hIndex(vector<int>& citations) {
        int h = 0;
        sort(citations.rbegin(), citations.rend());
        for(int i = 0; i < citations.size(); i++){
            if(citations[i] > h){
                h++;
            }
        }
        return h;
    }
};
```

## Problem

Given an array of integers `citations` where `citations[i]` is the number of citations a researcher received for their `i^th` paper, return _the researcher's h-index_.

According to the definition of h-index on Wikipedia: The h-index is defined as the maximum value of `h` such that the given researcher has published at least `h` papers that have each been cited at least `h` times.

Example 1:**

```

**Input:** citations = [3,0,6,1,5]
**Output:** 3
**Explanation:** [3,0,6,1,5] means the researcher has 5 papers in total and each of them had received 3, 0, 6, 1, 5 citations respectively.
Since the researcher has 3 papers with at least 3 citations each and the remaining two with no more than 3 citations each, their h-index is 3.

```

Example 2:**

```

**Input:** citations = [1,3,1]
**Output:** 1

```

**Constraints:**

- `n == citations.length`

- `1 <= n <= 5000`

- `0 <= citations[i] <= 1000`

---

<sub>Recorded and published with the [leetcode-journal](../../README.md) setup.</sub>
