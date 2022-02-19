# Quadratic-funding-calculator  

Round details need to be set in quadratic-funding-calculator.py  or in quadratic-funding-calculator-run-once-script.py.  
  
quadratic-funding-calculator-run-once-script.py will only run once and print results in terminal.   
    
To have something that updates actively, just run quadratic-funding-calculator.py. It will keep looking for new supports until it's killed. It will write current results to qf-result-json.js  

Qf.py contains logic for looking for tips and checking which ones are valid.  
Qf.update() looks for new tips and checks that old ones aren't spent too early. (Follows aren't currenlty being updated actively, don't think this being issue for now, but to be sure to have latest numbers, script needs to be restarted)  
   
Qf.py result are printed as following json  
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
                    amount,
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
