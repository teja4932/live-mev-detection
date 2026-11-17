import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

ws_url = os.getenv("ALCHEMY_WS_URL")
rpc_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")

w3 = Web3(Web3.HTTPProvider(rpc_url))

block = w3.eth.get_block(5776101, full_transactions=True)

for tx in block.transactions:
    index = tx["transactionIndex"]

    if index in [37, 38, 39]:
        receipt = w3.eth.get_transaction_receipt(tx["hash"])

        print("\n" + "=" * 65)
        print("INDEX:", index)
        print("HASH:", tx["hash"].hex())
        print("FROM:", tx["from"])
        print("TO:", tx["to"])
        print("INPUT:", tx["input"].hex())
        print("STATUS:", receipt["status"])

        for i, log in enumerate(receipt["logs"]):
            print("\nLog:", i + 1)
            print("Contract:", log["address"])
            print("Topics:", [t.hex() for t in log["topics"]])
            print("Data:", log["data"].hex())