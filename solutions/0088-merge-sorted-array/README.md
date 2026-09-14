# 0088. Merge Sorted Array

![Easy](https://img.shields.io/badge/Easy-brightgreen?style=flat-square) &nbsp;&middot;&nbsp; [Open on LeetCode](https://leetcode.com/problems/merge-sorted-array/) &nbsp;&middot;&nbsp; Solved **2026-09-13**

`Array`  `Two Pointers`  `Sorting`

## Walkthrough

_No recording attached to this solve._

## Notes

class Solution {
public:
    void merge(vector<int>& nums1, int m, vector<int>& nums2, int n) {
        for(int i = 0; i < m + n; i++){
                if (i < nums1[i-1]){
                    nums1[i-1] = nums1[i];
                    nums1[i] = nums1[i-1];
                }

                for(int j = 0; j < n; j++){
                    if(nums2[j] < nums1[j-1]){
                        nums1[j-1] = nums2[j];
                        nums1[j] = nums1[j-1];
                    }
             }
        }
        for(int k = 0; k < m + n; k++){
            cout << nums1[k];
        }
    }
};

## Solution

### C++ <sub>[solution.cpp](solution.cpp)</sub>

```cpp
class Solution {
public:
    void merge(vector<int>& nums1, int m, vector<int>& nums2, int n) {
        for(int i = 0; i < m + n; i++){
                if (i < nums1[i-1]){
                    nums1[i-1] = nums1[i];
                    nums1[i] = nums1[i-1];
                }

                for(int j = 0; j < n; j++){
                    if(nums2[j] < nums1[j-1]){
                        nums1[j-1] = nums2[j];
                        nums1[j] = nums1[j-1];
                    }
             }
        }
        for(int k = 0; k < m + n; k++){
            cout << nums1[k];
        }
    }
};
```

## Problem

You are given two integer arrays `nums1` and `nums2`, sorted in **non-decreasing order**, and two integers `m` and `n`, representing the number of elements in `nums1` and `nums2` respectively.

**Merge** `nums1` and `nums2` into a single array sorted in **non-decreasing order**.

The final sorted array should not be returned by the function, but instead be _stored inside the array _`nums1`. To accommodate this, `nums1` has a length of `m + n`, where the first `m` elements denote the elements that should be merged, and the last `n` elements are set to `0` and should be ignored. `nums2` has a length of `n`.

Example 1:**

```

**Input:** nums1 = [1,2,3,0,0,0], m = 3, nums2 = [2,5,6], n = 3
**Output:** [1,2,2,3,5,6]
**Explanation:** The arrays we are merging are [1,2,3] and [2,5,6].
The result of the merge is [1,2,2,3,5,6] with the underlined elements coming from nums1.

```

Example 2:**

```

**Input:** nums1 = [1], m = 1, nums2 = [], n = 0
**Output:** [1]
**Explanation:** The arrays we are merging are [1] and [].
The result of the merge is [1].

```

Example 3:**

```

**Input:** nums1 = [0], m = 0, nums2 = [1], n = 1
**Output:** [1]
**Explanation:** The arrays we are merging are [] and [1].
The result of the merge is [1].
Note that because m = 0, there are no elements in nums1. The 0 is only there to ensure the merge result can fit in nums1.

```

**Constraints:**

- `nums1.length == m + n`

- `nums2.length == n`

- `0 <= m, n <= 200`

- `1 <= m + n <= 200`

- `-10^9 <= nums1[i], nums2[j] <= 10^9`

**Follow up: **Can you come up with an algorithm that runs in `O(m + n)` time?

---

<sub>Recorded and published with the [leetcode-journal](../../README.md) setup.</sub>
