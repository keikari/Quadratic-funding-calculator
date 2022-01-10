# Quadratic-funding-calculator

quadratic-funding-calculator.py is used to enter/get needed values for Qtf.py. And to keep actively looking for new contributions.

Qtf.py contains logic for looking for tips and checking which ones are valid. 
update() looks for new tips and checks that old ones aren't spent too early. (Follows aren't currenlty being updated actively, don't think this being issue for now, but to be sure to have up to date numbers, script needs to be restarted)


Qtf.py spits out json like this. 
Results of test round can be found in this format from qtf-result-json.js

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
