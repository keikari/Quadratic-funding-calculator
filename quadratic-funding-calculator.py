import requests
import os
from math import sqrt, floor, ceil

server = "http://localhost:5279"
proposals = []
total_scaled = 0


# Set these values
last_accepted_height = 99999999
min_subs = 100
min_tip = 0
LBC_pool = 50000
claim_ids = [
    "76e3f9293ed5089c452232a2ad0511ecc77922fc",
    "c7cd5669b62bc5cd4386e08d1b0077c3c80568f8",
    "9f92f500378af5ef0cf1706141bffffed892f876",
    "99687395cc27ee453dc88dc9da53eb95cc0e9861",
    "ac47b46e35f37fe79d2b770af7e19c07bf3a4050",
    "f7a87b602def099215e5fb07dc13e62bdc531044",
    "270477be5195fb73e2f4e07900f94aba258225c5",
    "b5f8ddf844e6dd89ed1de52f66d43d12c84c9346",
]

def getAuthToken():
    auth_token_file = os.path.dirname(__file__) + "/auth_token"
    try: 
        with open(auth_token_file, "r") as file:
            auth_token = file.readline()
            response_error = requests.get("https://api.odysee.com/user/me?auth_token=%s" % auth_token).json()["error"]
            if response_error != None:
                # If auth_token expired or other error, just start from fresh
                raise FileNotFoundError
            print("Old auth_token found")

    except FileNotFoundError:
        with open(auth_token_file, "w") as file:
            auth_token = requests.post("https://api.odysee.com/user/new").json()["data"]["auth_token"]
            file.write(auth_token)
            print("New auth_token created")

    return auth_token



## Get auth token to check follows
auth_token = getAuthToken()

class Proposal:
    def __init__(self, claim):
        self.claim = claim
        self.contributors = []
        self.total_funded = 0
        self.scaled = 0
        self.median = 0
        self.average_contribution = 0
        
        self.invalid_supports = [] # To help confirming the result

        print("Looking for contributions, proposal: %d/%d" % (len(proposals) + 1, len(claim_ids)), end='\r')
        self.getContributions()
        if len(self.contributors) > 0:
            self.calculateScaled()
            self.calculateMedian()
            self.average_contribution = self.total_funded/len(self.contributors)
        

    def getContributions(self):
        # Get list of supports from chainquery
        supports = requests.get('https://chainquery.lbry.com/api/sql?query=SELECT * FROM support WHERE supported_claim_id = "%s"AND support_amount >= %f' % (self.claim["claim_id"], min_tip)).json()

        # Use lbrynet to get more details about transaction (Looking for support's signing channel)
        for support in supports["data"]: 
            vout = support["vout"]
            txid = support["transaction_hash_id"]
            transaction = requests.post(server, json={
                "method": "transaction_show",
                "params": {
                    "txid": txid }}).json()

            # Check that tip has been send before deadline, else skip
            if transaction["result"]["height"] > last_accepted_height:
                self.addInvalidSupport({"txid": txid, "support_amount": support["support_amount"], "reason": "Block height over %d" % last_accepted_height})
                continue

            support_ouput = transaction["result"]["outputs"][vout]

            support_amount = float(support_ouput["amount"])
            try:
                channel_id = support_ouput["signing_channel"]["channel_id"]

                # If channel is view-rewards channel, or creator's own channel, just skip it
                if channel_id == "7d0b0f83a195fd1278e1944ddda4cda8d9c01a56":
                    self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "View-reward"})
                    continue
                elif channel_id == self.claim["signing_channel"]["claim_id"]:
                    self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "Same channel than proposal"})
                    continue
                # Check sub count of channel
                subs = requests.post("https://api.odysee.com/subscription/sub_count", data={"auth_token": auth_token, "claim_id": [channel_id]} ).json()["data"][0] 
                if subs < min_subs:
                    self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "Not enough follows(%d): %s" % (subs, channel_id)})
                    continue

                # Do claim_serch to find more info about the signing channel(like name)
                channel = requests.post(server, json={
                    "method": "claim_search",
                    "params": {
                        "claim_ids": [channel_id]}}).json()
                try:
                    channel_url = channel["result"]["items"][0]["permanent_url"]
                    channel_address = channel["result"]["items"][0]["address"]
                except IndexError:
                    self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "Channel not returned by hub"})
                    continue

                # Check that the tip was sent to the proposal-claim's address, and that the tip's signing channel is in different address than addresses associated with the proposal
                if (self.claim["address"] != support_ouput["address"] or 
                        self.claim["address"] == channel_address or 
                        self.claim["signing_channel"]["address"] == channel_address):
                    self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "Not a tip"})
                    continue

                # Check addresses of all inputs in the transaction. If any of addresses matches to any of the following, consider tip as a support:
                # 1. output address
                # 2. address where proposal claim is
                # 3. address of the proposal's signing channel 
                is_tip = True; 
                tx_inputs = transaction["result"]["inputs"];
                for tx_input in tx_inputs: 
                    input_transaction = requests.post(server, json={
                        "method": "transaction_show",
                        "params": {
                            "txid": tx_input["txid"] }}).json()
                    tx_input_address = input_transaction["result"]["outputs"][tx_input["nout"]]["address"]
                    if (tx_input_address == support_ouput["address"] or 
                            tx_input_address == self.claim["address"] or 
                            tx_input_address == self.claim["signing_channel"]["address"]):
                        self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "Not a tip: input %s:%d " % (txid, tx_input["nout"])})
                        is_tip = False
                        break
                        

                if is_tip:
                    # Check that output hasn't been spent. Prevents looping of tips
                    unspent_support_outputs = requests.get('https://chainquery.lbry.com/api/sql?query=SELECT * FROM output WHERE transaction_hash = "%s" AND vout = "%d" AND is_spent = 0' % (txid, vout)).json()["data"];
                    if len(unspent_support_outputs) == 0:
                        # If tip is spent, check if it happened before voting deadline(should allow to re-check tips later)
                        spent_tx_id = requests.get('https://chainquery.lbry.com/api/sql?query=SELECT * FROM input WHERE prevout_hash = "%s" AND prevout_n = %d' % (txid, vout)).json()["data"][0]["transaction_hash"]
                        spent_height = requests.post(server, json={ 
                            "method": "transaction_show", 
                            "params": { 
                                "txid": spent_tx_id
                            }
                        }).json()["result"]["height"]
                        if spent_height <= last_accepted_height:
                            self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "Tip is spent too early"})
                            continue

                    # If this is reached, consider tip being valid
                    self.addContribution(channel_url, support_amount)

            except KeyError:
                self.addInvalidSupport({"txid": txid, "support_amount": support_amount, "reason": "Anonymous channel or other error"})
                pass

    def addContribution(self, channel_url, support_amount):
        for contributor in self.contributors:
            # If one channel has add multiple tips, count those as one tip
            if contributor["channel_url"] == channel_url:
                contributor["tip_amount"] += support_amount
                contributor["tips"].append(support_amount) # This is for error checking
                return
        self.contributors.append({"channel_url": channel_url, "tip_amount": support_amount, "tips":[support_amount]})

    def addInvalidSupport(self, invalid_support):
        self.invalid_supports.append(invalid_support)

    # Calculate scaled_value for proposal ( sum([sqrt(x),sqrt(x2),...]) ** 2 )
    def calculateScaled(self):
        sum_of_sqrts = 0
        for contributor in self.contributors:
            self.total_funded += contributor["tip_amount"] # This line is just to collect info
            sum_of_sqrts += sqrt(contributor["tip_amount"])
        self.scaled = (sum_of_sqrts ** 2)

    def calculateMedian(self):
        # Sorting this will also make printing use same order
        self.contributors.sort(reverse=True, key=lambda x: x["tip_amount"])
        # Use (len - 1) because indexes start from 0. [0, 1, 2, 3, 4] 
        middle_point = (len(self.contributors) - 1) / 2
        # This should work for even and odd numbered lists
        self.median = (self.contributors[floor(middle_point)]["tip_amount"] + self.contributors[ceil(middle_point)]["tip_amount"]) / 2

            

    def print(self):
        print("Proposal url: %s" % self.claim["canonical_url"])
        print("Proposal claim_id: %s" % self.claim["claim_id"])
        print("Proposal channel_id: %s" % self.claim["signing_channel"]["claim_id"])
        print("Claim's address: %s" % self.claim["address"])
        print("Contributors: %s" % len(self.contributors))
        print("Median contribution: %s" % self.median)
        print("Average contribution: %s" % self.average_contribution)
        print("Scaled: %.2f" % self.scaled)
        print("Funded amount: %.2f LBC" % self.total_funded)
        for contributor in self.contributors:
            print("%.2f LBC by %s" % (contributor["tip_amount"], contributor["channel_url"]))
            for tip in contributor["tips"]:
                print("- %f" % tip)
            print(60*'-')
        self.printInvalidSupports()
        print('\n')

    def printInvalidSupports(self, print_view_rewards = False):
        print("====INVALID SUPPORTS BELOW====")
        for support in self.invalid_supports:
            if print_view_rewards or support["reason"] != "View-reward":
                print("txid: %s" % support["txid"])
                print("amount: %s" % support["support_amount"])
                print("reason: %s" % support["reason"])
                print(60*'-')



# Starts from here
claims = requests.post(server, json={
    "method": "claim_search",
    "params": {
        "claim_ids": claim_ids
    }
}).json()["result"]["items"]
for claim in claims:
    proposals.append(Proposal(claim));

proposals.sort(reverse=True, key=lambda x: x.scaled)

all_contributors = []
total_funded = 0
for proposal in proposals:
    total_scaled += proposal.scaled
    total_funded += proposal.total_funded
    for contributor in proposal.contributors:
        if not any(collected_contributor["channel_url"] == contributor["channel_url"] for collected_contributor in all_contributors):
            all_contributors.append(contributor)
    proposal.print()

# Print results
print(10*"=", "RESULTS", 10*"=")
for proposal in proposals:
    matched_LBC = LBC_pool * (proposal.scaled/total_scaled)
    print("%s" % proposal.claim["canonical_url"])
    print("Contributors: %d" % len(proposal.contributors))
    print("Median contribution: %.2f LBC" % proposal.median)
    print("Average contribution: %.2f LBC" % proposal.average_contribution)
    print("Funded amount: %.2f LBC" % proposal.total_funded)
    print("Matched amount: %.2f LBC" % matched_LBC)
    print('\n')

print("Total contributors: %d" % len(all_contributors))
print("Total funded: %.2f LBC" % total_funded)
