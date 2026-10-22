# 0380. Insert Delete GetRandom O(1)

![Medium](https://img.shields.io/badge/Medium-orange?style=flat-square) &nbsp;&middot;&nbsp; [Open on LeetCode](https://leetcode.com/problems/insert-delete-getrandom-o1/) &nbsp;&middot;&nbsp; Solved **2026-10-21**

`Array`  `Hash Table`  `Math`  `Design`  `Randomized`

## Walkthrough

| Screen recording | Camera |
|:--:|:--:|
| [<img src="media/screen.jpg" width="380">](media/screen.mp4)<br><sub>20m 59s &middot; 21 MB</sub> | [<img src="media/camera.jpg" width="380">](media/camera.mp4)<br><sub>20m 54s &middot; 16 MB</sub> |

## Solution

### C++ <sub>[solution.cpp](solution.cpp)</sub>

```cpp
class RandomizedSet {
    vector<int>nums;
    unordered_map<int, int> pos;

public:
    RandomizedSet() {

    }

    bool insert(int val) {
        if(pos.count(val)){
            return false;
        }
        pos[val] = nums.size();
        nums.push_back(val);
        return true;
    }

    bool remove(int val) {
        auto it = pos.find(val);
        if(it == pos.end()){
            return false;
        }
        nums[it->second] = nums.back();
        pos[nums.back()] = it->second;
        nums.pop_back();
        pos.erase(val);
        return true;
    }

    int getRandom() {
        random_device rd;
        mt19937 gen(rd());
        uniform_int_distribution<> distr(0, nums.size() - 1);
        int random_index = distr(gen);
        int random_value = nums[random_index];
        return random_value;
    }
};

/**
 * Your RandomizedSet object will be instantiated and called as such:
 * RandomizedSet* obj = new RandomizedSet();
 * bool param_1 = obj->insert(val);
 * bool param_2 = obj->remove(val);
 * int param_3 = obj->getRandom();
 */
```

## Problem

Implement the `RandomizedSet` class:

- `RandomizedSet()` Initializes the `RandomizedSet` object.

- `bool insert(int val)` Inserts an item `val` into the set if not present. Returns `true` if the item was not present, `false` otherwise.

- `bool remove(int val)` Removes an item `val` from the set if present. Returns `true` if the item was present, `false` otherwise.

- `int getRandom()` Returns a random element from the current set of elements (it's guaranteed that at least one element exists when this method is called). Each element must have the **same probability** of being returned.

You must implement the functions of the class such that each function works in **average** `O(1)` time complexity.

Example 1:**

```

**Input**
["RandomizedSet", "insert", "remove", "insert", "getRandom", "remove", "insert", "getRandom"]
[[], [1], [2], [2], [], [1], [2], []]
**Output**
[null, true, false, true, 2, true, false, 2]

**Explanation**
RandomizedSet randomizedSet = new RandomizedSet();
randomizedSet.insert(1); // Inserts 1 to the set. Returns true as 1 was inserted successfully.
randomizedSet.remove(2); // Returns false as 2 does not exist in the set.
randomizedSet.insert(2); // Inserts 2 to the set, returns true. Set now contains [1,2].
randomizedSet.getRandom(); // getRandom() should return either 1 or 2 randomly.
randomizedSet.remove(1); // Removes 1 from the set, returns true. Set now contains [2].
randomizedSet.insert(2); // 2 was already in the set, so return false.
randomizedSet.getRandom(); // Since 2 is the only number in the set, getRandom() will always return 2.

```

**Constraints:**

- `-2^31 <= val <= 2^31 - 1`

- At most `2 * ``10^5` calls will be made to `insert`, `remove`, and `getRandom`.

- There will be **at least one** element in the data structure when `getRandom` is called.

---

<sub>Recorded and published with the [leetcode-journal](../../README.md) setup.</sub>
