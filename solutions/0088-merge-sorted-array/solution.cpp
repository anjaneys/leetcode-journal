// 0088. Merge Sorted Array  [Easy]
// https://leetcode.com/problems/merge-sorted-array/

#include <bits/stdc++.h>
using namespace std;

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
