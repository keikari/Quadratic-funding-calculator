import requests
from math import sqrt, floor, ceil

# Qf json
# {
#     round_details: {
#         LBC_pool,
#         last_accepted_height,
#         min_subs,
#         min_tip,
#         max_contribution_amount,
#     },
#     proposals: [ 
#         {
#             claim,
#             contributors: [
#                 {
#                     channel_claim,
#                     accepted_amount,
#                     tip_amount,
#                     tips: [
#                         {
#                             amount,
#                             txid,
#                             vout
#                         }
#                     ]
#                 }, ... 
#             ],
#             invalid_supports: [
#                 {
#                     support_amount,
#                     txid,
#                     reason
#                 }, ...
#             ],
#             funded_amount,
#             accepted_amount,
#             matched_amount,
#             average_amount,
#         }, ...
#     ],
#     total_contributors,
# }



class Qf:
    def __init__(self, proposal_claim_ids, round_details, server = "http://localhost:5279", auth_token = None):
        self.proposals = []
        self.round_details = round_details
        self.total_supports_found = 0
        self.total_contributors = 0

        claims = requests.post(server, json={
            "method": "claim_search",
            "params": {
                "claim_ids": proposal_claim_ids,
                "no_totals": True,
                "page_size": len(proposal_claim_ids)
            }
        }).json()["result"]["items"]

        for claim in claims:
            print("Looking for contributions, proposal: %d/%d" % (len(self.proposals) + 1, len(proposal_claim_ids)), end='\r' if len(self.proposals) < len(proposal_claim_ids) - 1 else '\n')
            self.proposals.append(Proposal(claim, round_details, server, auth_token))
        self.calculateMatchedAmounts()
        self.calculateTotalSupports()
        self.calculateTotalContributors()

    def update(self):
        for proposal in self.proposals:
            proposal.update()
        self.calculateMatchedAmounts()
        self.calculateTotalSupports()
        self.calculateTotalContributors()

    def calculateMatchedAmounts(self):
        total_scaled = 0
        for proposal in self.proposals:
            total_scaled += proposal.scaled

        # After total_scaled is known, updated matched amounts for proposals
        for proposal in self.proposals:
            matched_amount = 0
            if total_scaled != 0:
                matched_amount = self.round_details["LBC_pool"] * (proposal.scaled/total_scaled)
            proposal.matched_amount = matched_amount

    def calculateTotalContributors(self):
        contributors = []
        for proposal in self.proposals:
            for contributor in proposal.contributors:
                if not contributor["channel_claim"]["claim_id"] in contributors:
                    contributors.append(contributor["channel_claim"]["claim_id"])

        self.total_contributors = len(contributors)


    def calculateTotalSupports(self):
        total_supports = 0
        for proposal in self.proposals:
            total_supports += proposal.support_count
        self.total_supports_found = total_supports

    def getJSON(self):
        result_json = {
            "round_details": self.round_details,
            "total_contributors": self.total_contributors,
            "proposals": []
        }

        # Sort here
        self.proposals.sort(reverse=True, key=lambda x: x.scaled)

        for proposal in self.proposals:
            result_json["proposals"].append(proposal.getJSON())

        return result_json
        
class Proposal:
    def __init__(self, claim, round_details, server = "http://localhost:5279", auth_token = None):
        self.claim = claim
        self.server = server
        self.auth_token = auth_token;
        self.contributors = []
        self.support_count = 0
        self.funded_amount = 0
        self.accepted_amount = 0
        self.scaled = 0
        self.median = 0
        self.average_contribution = 0
        self.checked_txids = []
        self.invalid_supports = [] # To help confirming the result
        self.matched_amount = 0

        # Round details
        self.min_tip = round_details["min_tip"] if "min_tip" in round_details else 0;
        self.last_accepted_height = round_details["last_accepted_height"] if "last_accepted_height" in round_details else 1070908
        self.min_subs = round_details["min_subs"] if "min_subs" in round_details else 100
        self.max_contribution_amount = round_details["max_contribution_amount"] if "max_contribution_amount" in round_details else 0

        self.getContributions()
        self.calculateValues()

    def update(self):
        self.checkContributionsAreStillValid()
        self.getContributions()
        self.calculateValues()
        
    def calculateValues(self):
        # Order in these matters a bit
        self.calculateContributions()
        self.calculateFundedAmount()
        self.calculateAcceptedAmounts()
        self.calculateScaled()
        self.calculateMedian()
        try: 
            self.average_contribution = self.funded_amount/len(self.contributors)
        except ZeroDivisionError:
            self.average_contribution = 0.0

    def isContributionSpentTooEarly(self, txid, vout):
        # Check that output hasn't been spent. Prevents looping of tips
        contribution_is_spent_too_early = False
        unspent_support_outputs = requests.get('https://chainquery.lbry.com/api/sql?query=SELECT * FROM output WHERE transaction_hash = "%s" AND vout = "%d" AND is_spent = 0' % (txid, vout)).json()["data"];
        if len(unspent_support_outputs) == 0:
            # If tip is spent, check if it happened before voting deadline(should allow to re-check tips later)
            spent_tx_id = requests.get('https://chainquery.lbry.com/api/sql?query=SELECT * FROM input WHERE prevout_hash = "%s" AND prevout_n = %d' % (txid, vout)).json()["data"][0]["transaction_hash"]
            spent_height = requests.post(self.server, json={ 
                "method": "transaction_show", 
                "params": { 
                    "txid": spent_tx_id
                }
            }).json()["result"]["height"]
            if spent_height <= self.last_accepted_height:
                contribution_is_spent_too_early = True

        return contribution_is_spent_too_early
        
    def checkContributionsAreStillValid(self):
        for contributor in self.contributors:
            for tip in contributor["tips"]:
                txid = tip["txid"]
                vout = tip["vout"]
                amount = tip["amount"]
                if self.isContributionSpentTooEarly(txid, vout) == True:
                   self.addInvalidSupport({"txid": txid, "amount": amount, "reason": "Tip is spent too early"})
                   contributor["tips"].remove(tip)
                if len(contributor["tips"]) == 0:
                    self.contributors.remove(contributor)


    def getContributions(self):
        # Get list of supports from chainquery
        supports = requests.get('https://chainquery.lbry.com/api/sql?query=SELECT * FROM support WHERE supported_claim_id = "%s"AND support_amount >= %f' % (self.claim["claim_id"], self.min_tip)).json()

        # Use lbrynet to get more details about transaction (Looking for support's signing channel)
        for support in supports["data"]: 
            vout = support["vout"]
            txid = support["transaction_hash_id"]

            # No need to check txid again, also prevents adding same contirbution multiple times
            if txid in self.checked_txids:
                continue

            self.checked_txids.append(txid)
            self.support_count += 1
            transaction = requests.post(self.server, json={
                "method": "transaction_show",
                "params": {
                    "txid": txid }}).json()

            # Check that tip has been send before deadline, else skip
            if transaction["result"]["height"] > self.last_accepted_height:
                self.addInvalidSupport({"txid": txid, "amount": support["support_amount"], "reason": "Block height over %d" % self.last_accepted_height})
                continue

            support_ouput = transaction["result"]["outputs"][vout]

            support_amount = float(support_ouput["amount"])
            try:
                channel_id = support_ouput["signing_channel"]["channel_id"]

                # If channel is view-rewards channel, or creator's own channel, just skip it
                if channel_id == "7d0b0f83a195fd1278e1944ddda4cda8d9c01a56":
                    self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "View-reward"})
                    continue
                elif channel_id == self.claim["signing_channel"]["claim_id"]:
                    self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Same channel than proposal"})
                    continue
                # Check sub count of channel
                if self.auth_token != None:
                    subs = requests.post("https://api.odysee.com/subscription/sub_count", data={"auth_token": self.auth_token, "claim_id": [channel_id]} ).json()["data"][0]
                    if subs < self.min_subs:
                        self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Not enough follows(%d): %s" % (subs, channel_id)})
                        continue

                # Do claim_serch to find more info about the signing channel(like name)
                channel_response = requests.post(self.server, json={
                    "method": "claim_search",
                    "params": {
                        "claim_ids": [channel_id]}}).json()
                try:
                    channel_claim = channel_response["result"]["items"][0]
                    channel_url = channel_claim["permanent_url"]
                    channel_address = channel_claim["address"]
                except IndexError:
                    self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Channel not returned by hub"})
                    continue

                # Check that the tip was sent to the proposal-claim's address, and that the tip's signing channel is in different address than addresses associated with the proposal
                if (self.claim["address"] != support_ouput["address"] or 
                        self.claim["address"] == channel_address or 
                        self.claim["signing_channel"]["address"] == channel_address):
                    self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Not a tip"})
                    continue

                # Check addresses of all inputs in the transaction. If any of addresses matches to any of the following, consider tip as a support:
                # 1. output address
                # 2. address where proposal claim is
                # 3. address of the proposal's signing channel 
                is_tip = True; 
                tx_inputs = transaction["result"]["inputs"];
                for tx_input in tx_inputs: 
                    input_transaction = requests.post(self.server, json={
                        "method": "transaction_show",
                        "params": {
                            "txid": tx_input["txid"] }}).json()
                    tx_input_address = input_transaction["result"]["outputs"][tx_input["nout"]]["address"]
                    if (tx_input_address == support_ouput["address"] or 
                            tx_input_address == self.claim["address"] or 
                            tx_input_address == self.claim["signing_channel"]["address"]):
                        self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Not a tip: input %s:%d " % (txid, tx_input["nout"])})
                        is_tip = False
                        break
                        

                if is_tip:
                    if self.isContributionSpentTooEarly(txid, vout) == True:
                        self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Tip is spent too early"})
                        continue

                    # If this is reached, consider tip being valid
                    self.addContribution(channel_claim, support_amount, txid, vout)

            except KeyError:
                self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Anonymous channel or other error"})
                pass

    def addContribution(self, channel_claim, support_amount, txid, vout):
        for contributor in self.contributors:
            # If one channel has add multiple tips, count those as one tip
            if contributor["channel_claim"]["permanent_url"] == channel_claim["permanent_url"]:
                contributor["tips"].append({"amount": support_amount, "txid": txid, "vout": vout}) # This is for error checking
                return

        # Create new, if contributor doesn't exist
        self.contributors.append({"channel_claim": channel_claim, "tip_amount": support_amount, "tips":[{"amount":support_amount, "txid": txid, "vout": vout}]})

    def addInvalidSupport(self, invalid_support):
        self.invalid_supports.append(invalid_support)

    def calculateAcceptedAmounts(self):
        accepted_amount = 0
        for contributor in self.contributors:
            if self.max_contribution_amount > 0:
                contributor["accepted_amount"] = min(contributor["tip_amount"], self.max_contribution_amount)
            else:
                contributor["accepted_amount"] = contributor["tip_amount"]
            accepted_amount += contributor["accepted_amount"]

        self.accepted_amount = accepted_amount

    def calculateFundedAmount(self):
        funded_amount = 0
        for contributor in self.contributors:
            funded_amount += contributor["tip_amount"]

        self.funded_amount = funded_amount

    def calculateContributions(self):
        for contributor in self.contributors:
            contributor["tip_amount"] = 0
            for tip in contributor["tips"]:
                contributor["tip_amount"] += tip["amount"]

    # Calculate scaled_value for proposal ( sum([sqrt(x),sqrt(x2),...]) ** 2 )
    def calculateScaled(self):
        sum_of_sqrts = 0
        for contributor in self.contributors:
            sum_of_sqrts += sqrt(contributor["accepted_amount"])
        self.scaled = (sum_of_sqrts ** 2)

    def calculateMedian(self):
        if len(self.contributors) > 0:
            # Sorting this will also make printing use same order
            self.contributors.sort(reverse=True, key=lambda x: x["tip_amount"])
            # Use (len - 1) because indexes start from 0. [0, 1, 2, 3, 4] 
            middle_point = (len(self.contributors) - 1) / 2
            # This should work for even and odd numbered lists
            self.median = (self.contributors[floor(middle_point)]["tip_amount"] + self.contributors[ceil(middle_point)]["tip_amount"]) / 2
        else:
            self.median = 0.0

    def getJSON(self):
        result_json = {
            "claim": self.claim,
            "contributors": self.contributors,
            "invalid_supports": self.invalid_supports,
            "funded_amount": self.funded_amount,
            "accepted_amount": self.accepted_amount,
            "matched_amount": self.matched_amount,
            "average_amount": self.average_contribution
        }
        return result_json

