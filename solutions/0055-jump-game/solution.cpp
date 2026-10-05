// 0055. Jump Game  [Medium]
// https://leetcode.com/problems/jump-game/

#include <bits/stdc++.h>
using namespace std;

class Solution {
public:
    bool canJump(vector<int>& nums) {
        int range = 0;
        for(int i = 0; i < nums.size(); i++){
            if(i > range){
                return false;
            }
            range = max(range ,nums[i] + i);
            if(range >= nums.size()){
                return true;
            }
        }
        return true;
    }
};
