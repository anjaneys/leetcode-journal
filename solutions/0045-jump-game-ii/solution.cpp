// 0045. Jump Game II  [Medium]
// https://leetcode.com/problems/jump-game-ii/

#include <bits/stdc++.h>
using namespace std;

class Solution {
public:
    int jump(vector<int>& nums) {
        int jumps = 0;
        int range = 0;
        int j = 0;
        for(int i = 0; i < nums.size() - 1; i++){
            range = max(range, i + nums[i]);
            if(i == j){
                jumps++;
                j = range;
            }
        }
        return jumps;
    }
};
