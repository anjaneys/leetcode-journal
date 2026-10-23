// 0238. Product of Array Except Self  [Medium]
// https://leetcode.com/problems/product-of-array-except-self/

#include <bits/stdc++.h>
using namespace std;

class Solution {
public:
    vector<int> productExceptSelf(vector<int>& nums) {
        vector<int> answer (nums.size(), 1);
        for(int i = 1; i < nums.size(); i++){
            answer[i] = nums[i-1] * answer[i-1];
        }
        int temp = 1;
        for(int i = nums.size() - 1; i >= 0; i--){
            answer[i] *= temp;
            temp *= nums[i];
        }

        return answer;
    }
};
