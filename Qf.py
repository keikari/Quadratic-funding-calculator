import requests
from math import sqrt, floor, ceil

# These are for checking if signatures are valid
from binascii import unhexlify
from hashlib import sha256
from coincurve import PublicKey as cPublicKey
from coincurve.ecdsa import deserialize_compact, cdata_to_der
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import Prehashed
from cryptography.exceptions import InvalidSignature


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
#                     amount,
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
        self.total_funded_amount = 0
        self.total_accepted_amount = 0
        self.current_block = 0
        self.server = server

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
        self.calculatedTotalAmounts()
        self.calculateTotalSupportCounts()
        self.calculateTotalContributors()
        self.updateCurrentBlock()

    def update(self):
        for proposal in self.proposals:
            proposal.update()
        self.calculateMatchedAmounts()
        self.calculatedTotalAmounts()
        self.calculateTotalSupportCounts()
        self.calculateTotalContributors()
        self.updateCurrentBlock()

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


    def calculateTotalSupportCounts(self):
        total_supports = 0
        for proposal in self.proposals:
            total_supports += proposal.support_count
        self.total_supports_found = total_supports

    def calculatedTotalAmounts(self):
        total_accepted_amount = 0
        total_funded_amount = 0
        for proposal in self.proposals:
            total_accepted_amount += proposal.accepted_amount
            total_funded_amount += proposal.funded_amount
        self.total_funded_amount = total_funded_amount
        self.total_accepted_amount = total_accepted_amount

    def updateCurrentBlock(self):
        self.current_block = requests.post(self.server, json={"method": "status"}).json()["result"]["wallet"]["blocks"]


    def getJSON(self):
        result_json = {
            "round_details": self.round_details,
            "total_contributors": self.total_contributors,
            "current_block": "~%d" % self.current_block,
            "proposals": []
        }

        # Sort here
        self.proposals.sort(reverse=True, key=lambda x: x.scaled)

        for proposal in self.proposals:
            result_json["proposals"].append(proposal.getJSON())

        return result_json

    def print(self):
        # Sort here
        self.proposals.sort(reverse=True, key=lambda x: x.scaled)

        # Print details
        for proposal in self.proposals:
            proposal.print()

        # Print results
        print(10*"=", "RESULTS", 10*"=")
        for proposal in self.proposals:
            print("%s" % proposal.claim["canonical_url"])
            print("Contributors: %d" % len(proposal.contributors))
            print("Funded amount:        %.2f LBC" % proposal.funded_amount)
            print("Accepted amount:      %.2f LBC" % proposal.accepted_amount)
            print("Matched amount:       %.2f LBC" % proposal.matched_amount)
            print('\n')

        print("Total contributors: %d" % self.total_contributors)
        print("Total funded: %.2f LBC" % self.total_funded_amount)
        print("Total accepted: %.2f LBC" % self.total_accepted_amount)


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
        self.first_accepted_height = round_details["first_accepted_height"] if "first_accepted_height" in round_details else 0
        self.last_accepted_height = round_details["last_accepted_height"] if "last_accepted_height" in round_details else 999999999
        self.min_subs = round_details["min_subs"] if "min_subs" in round_details else 0
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
            if spent_height <= self.last_accepted_height and spent_height > 0:
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


            support_ouput = transaction["result"]["outputs"][vout]

            support_amount = float(support_ouput["amount"])

            if "signing_channel" not in support_ouput:
                self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "No signing channel"})
                continue


            channel_id = support_ouput["signing_channel"]["channel_id"]

            # If channel is view-rewards channel, or creator's own channel, just skip it
            if channel_id == "7d0b0f83a195fd1278e1944ddda4cda8d9c01a56":
                self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "View-reward"})
                continue
            elif channel_id == self.claim["signing_channel"]["claim_id"]:
                self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Same channel than proposal(Support)"})
                continue

            # Check that tip has been send during accepted tipping times, else skip
            support_height = transaction["result"]["height"]
            if support_height > self.last_accepted_height:
                self.addInvalidSupport({"txid": txid, "amount": support["support_amount"], "reason": "Block height over %d (%d)" % (self.last_accepted_height, support_height)})
                continue
            elif support_height <= 0:
                # Ignore the transaction if it is found before it's confirmed. These will get re-checked on next block
                self.checked_txids.remove(txid)
                self.support_count -= 1
                continue
            elif support_height < self.first_accepted_height:
                self.addInvalidSupport({"txid": txid, "amount": support["support_amount"], "reason": "Block height under %d (%d)" % (self.first_accepted_height, support_height)})
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
                # Check sub count of channel
                if self.auth_token != None:
                    subs = requests.post("https://api.odysee.com/subscription/sub_count", data={"auth_token": self.auth_token, "claim_id": [channel_id]} ).json()["data"][0]
                    if subs < self.min_subs:
                        self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Not enough follows(%d): %s" % (subs, channel_id)})
                        continue
                if self.isContributionSpentTooEarly(txid, vout) == True:
                    self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Tip is spent too early"})
                    continue

                if not self.is_signature_valid(transaction, channel_claim):
                    self.addInvalidSupport({"txid": txid, "amount": support_amount, "reason": "Invalid channel signature"})
                    continue

                # If this is reached, consider tip being valid
                self.addContribution(channel_claim, support_amount, txid, vout)


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

    def is_signature_valid(self, tx, channel_claim):
        tx = tx["result"]

        # Get channel's public key as bytes
        pub_key_bytes = unhexlify(channel_claim["value"]["public_key"])

        # Extract signature
        # TODO: Figure out why/if this works
        end_of_signature = "6d6d76a914"
        signature_length = 128
        signature_bytes = unhexlify(tx["hex"].split(end_of_signature)[0][::-1][:signature_length][::-1])

        # Get digest value(needs three things)
        # 1. first txi:nout as bytes
        txi0_id_bytes = unhexlify(tx["inputs"][0]["txid"])[::-1]
        txi0_nout_bytes = unhexlify(format(tx["inputs"][0]["nout"], '08b'))[::-1] # Withs some padding
        txi0_bytes = b''.join([txi0_id_bytes, txi0_nout_bytes])

        # 2. channel_id as bytes
        channel_bytes = unhexlify(channel_claim["claim_id"])[::-1]

        # 3. message (for supports this is empty)
        message_bytes = b''

        digest = sha256(b''.join([txi0_bytes, channel_bytes, message_bytes])).digest()

        # Check signature (Basically copied some old code from lbry-sdk, I have no idea what happpens here, but seems to work)
        signature = cdata_to_der(deserialize_compact(signature_bytes))
        public_key = cPublicKey(pub_key_bytes)
        is_valid = public_key.verify(signature, digest, None)

        if not is_valid:
            # Above may not always detect valid signatures
            try:
                pk = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256K1(), pub_key_bytes)
                pk.verify(signature, digest, ec.ECDSA(Prehashed(hashes.SHA256())))
                is_valid = True
            except (ValueError, InvalidSignature):
                pass

        return is_valid


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

    def print(self):
        print("Proposal url: %s" % self.claim["canonical_url"])
        print("Proposal claim_id: %s" % self.claim["claim_id"])
        print("Proposal channel_id: %s" % self.claim["signing_channel"]["claim_id"])
        print("Claim's address: %s" % self.claim["address"])
        print("Contributors: %s" % len(self.contributors))
        print("Median contribution: %s" % self.median)
        print("Average contribution: %s" % self.average_contribution)
        print("Scaled: %.2f" % self.scaled)
        print("Funded amount: %.2f LBC" % self.funded_amount)
        print("Accepted amount: %.2f LBC" % self.accepted_amount)
        for contributor in self.contributors:
            print("%.2f (%.2f) LBC by %s" % (contributor["accepted_amount"], contributor["tip_amount"], contributor["channel_claim"]["name"]))
            for tip in contributor["tips"]:
                print("- %f" % tip["amount"])
                print(60*'-')
        self.printInvalidSupports()
        print('\n')

    def printInvalidSupports(self, print_view_rewards = False):
        print("====INVALID SUPPORTS BELOW====")
        for support in self.invalid_supports:
            if print_view_rewards or support["reason"] != "View-reward":
                print("txid: %s" % support["txid"])
                print("amount: %s" % support["amount"])
                print("reason: %s" % support["reason"])
                print(60*'-')


