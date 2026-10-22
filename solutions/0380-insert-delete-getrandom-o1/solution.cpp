// 0380. Insert Delete GetRandom O(1)  [Medium]
// https://leetcode.com/problems/insert-delete-getrandom-o1/

#include <bits/stdc++.h>
using namespace std;

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
