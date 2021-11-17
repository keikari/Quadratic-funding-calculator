import requests
from math import sqrt

server = "http://localhost:5279"
proposals = []
total_scaled = 0


# Set these values
last_accepted_height = 99999999999999999999
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


class Proposal:
    def __init__(self, claim):
        self.claim = claim
        self.contributors = []
        self.total_funded = 0
        self.scaled = 0

        self.getContributions()
        self.calculateScaled()

    def getContributions(self):
        # Get list of supports from chainquery
        supports = requests.get('https://chainquery.lbry.com/api/sql?query=SELECT * FROM support WHERE supported_claim_id = "%s"' % self.claim["claim_id"]).json();

        # Use lbrynet to get more details about transaction (Looking for support's signing channel)
        for support in supports["data"]: 
            vout = support["vout"]
            transaction = requests.post(server, json={
                "method": "transaction_show",
                "params": {
                    "txid": support["transaction_hash_id"] }}).json()

            # Check that tip has been send before deadline, else skip
            if transaction["result"]["height"] > last_accepted_height:
                continue

            try:
                output = transaction["result"]["outputs"][vout]
                channel_id = output["signing_channel"]["channel_id"]

                # If channel is view-rewards channel, or creator's own channel, just skip it
                if channel_id == "7d0b0f83a195fd1278e1944ddda4cda8d9c01a56" or channel_id == self.claim["signing_channel"]["claim_id"]:
                    continue

                # Do claim_serch to find more info about the signing channel(like name)
                channel = requests.post(server, json={
                    "method": "claim_search",
                    "params": {
                        "claim_ids": [channel_id]}}).json()
                try:
                    channel_url = channel["result"]["items"][0]["permanent_url"]
                except IndexError:
                    channel_name = "NOT_RETURNED_BY_HUB"
                support_amount = float(output["amount"])

                # Only include the support if it was a tip
                if self.claim["address"] == output["address"]:
                    self.addContribution(channel_url, support_amount)
            except KeyError:
                pass

    def addContribution(self, channel_url, support_amount):
        for contributor in self.contributors:
            # If one channel has add multiple tips, count those as one tip
            if contributor["channel_url"] == channel_url:
                contributor["tip_amount"] += support_amount
                contributor["tips"].append(support_amount)
                return
        self.contributors.append({"channel_url": channel_url, "tip_amount": support_amount, "tips":[support_amount]})

    # Calculate scaled_value for proposal ( sum([sqrt(x),sqrt(x2),...]) ** 2 )
    def calculateScaled(self):
        sum_of_sqrts = 0
        for contributor in self.contributors:
            self.total_funded += contributor["tip_amount"]
            sum_of_sqrts += sqrt(contributor["tip_amount"])
        self.scaled = (sum_of_sqrts ** 2)

    def print(self):
        print("Proposal url: %s" % self.claim["canonical_url"])
        print("Claim's address: %s" % self.claim["address"])
        print("Scaled: %.2f" % self.scaled)
        print("Funded amount: %.2f LBC" % self.total_funded)
        for contributor in self.contributors:
            print("%.2f LBC by %s" % (contributor["tip_amount"], contributor["channel_url"]))
            for tip in contributor["tips"]:
                print("- %f" % tip)
        print('\n')



# Starts from here
for claim_id in claim_ids:
    claim = requests.post(server, json={
        "method": "claim_search",
        "params": {
            "claim_ids": [claim_id] }}).json()["result"]["items"][0]
    proposals.append(Proposal(claim));


for proposal in proposals:
    total_scaled += proposal.scaled
    proposal.print()

# Print results
print(10*"=", "RESULTS", 10*"=")
for proposal in proposals:
    matched_LBC = LBC_pool * (proposal.scaled/total_scaled)
    print("%s" % proposal.claim["canonical_url"])
    print("Funded amount: %.2f LBC" % proposal.total_funded)
    print("Matched amount: %.2f LBC" % matched_LBC)
    print('\n')

