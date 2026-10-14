// 0274. H-Index  [Medium]
// https://leetcode.com/problems/h-index/

#include <bits/stdc++.h>
using namespace std;

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
