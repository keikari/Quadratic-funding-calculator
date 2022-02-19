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
    "last_accepted_height": 10709080,
    "first_accepted_height": 11135490,
    "min_subs": 100,
    "min_tip": 0,
    "max_contribution_amount": 0 # set 0 if not used
}

claim_ids = [
    "4b4012c5db509554b3fc3eb9145ecd5d75e70c67",
    "fc4f7e318aa8a72abcaaa9ef7e68939ff810da95",
    "2abd078151d4d7802be626497f8d38ca6b002d1c",
    "49f1f0d64ba28180336c4014d138ff6e9785f49c",
    "33a885a17a14399c4076bb2d97e8c52ee05fe77e",
    "20b6a9decb74288178bc74bc58f1d1b5602d9213",
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

