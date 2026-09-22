# Notes - 169. Majority Element

class Solution {
public:
    int majorityElement(vector<int>& nums) {
        int n = nums.size();
        unordered_map<int, int> map;
        for(int i = 0; i < n; i++){
            map[nums[i]]++;
        }
        for(int j = 0; j < n; j++){
            if(map[nums[j]] > n / 2){
                return nums[j];
            }
        }
        return 0;
    }
};
