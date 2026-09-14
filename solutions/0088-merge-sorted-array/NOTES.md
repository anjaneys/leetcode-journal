# Notes - 88. Merge Sorted Array

class Solution {
public:
    void merge(vector<int>& nums1, int m, vector<int>& nums2, int n) {
        nums1.resize(m);
        for(int i = 0; i < n; i++){
            nums1.push_back(nums2[i]);
        }
        for(int i = 0; i < (m + n) -1; i++){
            for(int j = 1; j < (m + n) - i; j++){
                if(nums1[j] < nums1[j - 1]){
                    int tmp = nums1[j];
                    nums1[j] = nums1[j - 1];
                    nums1[j - 1] = tmp;
                }
            }
        }
    }
};
