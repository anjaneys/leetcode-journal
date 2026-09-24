# Notes - 121. Best Time to Buy and Sell Stock

class Solution {
public:
    int maxProfit(vector<int>& prices) {
        int minPrice = INT_MAX;
        int val = 0;
        for(int i = 0; i < prices.size(); i++){
            if(prices[i] < minPrice){
                minPrice = prices[i];
            }

            int diff = prices[i] - minPrice;

            if(diff > val){
                val = diff;
            }
        }
        return val;
    }
};
