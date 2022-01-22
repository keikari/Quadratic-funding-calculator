import requests
import os
import time
import json as JSON
from Qf import Qf

server = "http://localhost:5279"
proposals = []
total_scaled = 0
support_count = 0

# Set these values
round_details = {
    "LBC_pool": 50000,
    "last_accepted_height": 1070908,
    "min_subs": 100,
    "min_tip": 0,
    "max_contribution_amount": 0 # set 0 if not used
}

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

def getCurrentHeight():
    return requests.post(server, json={"method": "status"}).json()["result"]["wallet"]["blocks"]

def createJSONfile(file_name, json):
    json = JSON.dumps(json)
    with open(file_name, 'w') as file:
        file.write(f"""var qf_results = {json}
    """)

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



qf = Qf(claim_ids, round_details, server, auth_token)
createJSONfile("qf-result-json.js", qf.getJSON())

# Loop to update values
height = getCurrentHeight()
last_height = height
print("Block: %d" % height)
print("Supports found(includes view-rewards): %d" % qf.total_supports_found)
while height <= round_details["last_accepted_height"] or True:
    if (last_height < height):
        qf.update()
        createJSONfile("qf-result-json.js", qf.getJSON())
        print("Block: %d" % height)
        print("Supports found(includes view-rewards): %d" % qf.total_supports_found)
    time.sleep(15)
    last_height = height
    height = getCurrentHeight()

