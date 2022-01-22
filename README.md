# Quadratic-funding-calculator  

Round details need to be set in quadratic-funding-calculator.py  
Then just run quadratic-funding-calculator.py, it will keep looking for new supports until it's killed. It will write current results to qf-result-json.js  

quadratic-funding-calculator.py is used to enter/get needed values for Qtf.py. And to keep actively looking for new contributions.  

Qf.py contains logic for looking for tips and checking which ones are valid.  
Qf.update() looks for new tips and checks that old ones aren't spent too early. (Follows aren't currenlty being updated actively, don't think this being issue for now, but to be sure to have latest numbers, script needs to be restarted)  
  
  
Qf.py spits out json like this.  

```
{
    round_details: {
        LBC_pool,
        last_accepted_height,
        min_subs,
        min_tip,
        max_contribution_amount,
    },
    proposals: [ 
        {
            claim,
            contributors: [
                {
                    channel_claim,
                    accepted_amount,
                    tip_amount,
                    tips: [
                        {
                            amount,
                            txid,
                            vout
                        }
                    ]
                }, ... 
            ],
            invalid_supports: [
                {
                    support_amount,
                    txid,
                    reason
                }, ...
            ],
            funded_amount,
            accepted_amount,
            matched_amount,
            average_amount,
        }, ...
    ],
    total_contributors
}
```
  
Other stuff is just for a most basic website that shows the results.
