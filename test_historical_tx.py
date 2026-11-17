
import os
from dotenv import load_dotenv
from web3 import Web3

load_dotenv()

ws_url = os.getenv("ALCHEMY_WS_URL")

if not ws_url:
    raise ValueError("ALCHEMY_WS_URL not found in .env")

# Convert Alchemy WebSocket URL to HTTP URL
rpc_url = ws_url.replace("wss://", "https://").replace("ws://", "http://")

w3 = Web3(Web3.HTTPProvider(rpc_url))

print("Connected:", w3.is_connected())

tx_hash = "0x2df451562f86aee08ad62d3ed5fcb4bc64dd13b8a7ecfacca6cf0114f7f105e5"

tx = w3.eth.get_transaction(tx_hash)

print("\nTransaction details:")
print("Hash:", tx["hash"].hex())
print("Block:", tx["blockNumber"])
print("Transaction index:", tx["transactionIndex"])
print("From:", tx["from"])
print("To:", tx["to"])
print("Gas:", tx["gas"])
print("Gas price (Gwei):", tx["gasPrice"] / 10**9)
print("Nonce:", tx["nonce"])
print("Input length:", len(tx["input"]))
receipt = w3.eth.get_transaction_receipt(tx_hash)

print("\nTransaction receipt:")
print("Status:", receipt["status"])
print("Gas used:", receipt["gasUsed"])
print("Block:", receipt["blockNumber"])
print("Transaction index:", receipt["transactionIndex"])
print("Number of logs:", len(receipt["logs"]))

for i, log in enumerate(receipt["logs"][:5]):
    print(f"\nLog {i + 1}")
    print("Address:", log["address"])
    print("Topics:", [topic.hex() for topic in log["topics"]])
    print("Data length:", len(log["data"]))

from web3 import Web3

event_topic = receipt["logs"][1]["topics"][0]

print("\nSecond event signature:")
print(event_topic.hex())

print("\nEvent topic count:", len(receipt["logs"][1]["topics"]))
print("Contract address:", receipt["logs"][1]["address"])

# Decode Uniswap V1 TokenPurchase event

# Search all logs for Uniswap V1 TokenPurchase event

token_purchase_topic = (
    "cd60aa75dea3072fbc07ae6d7d856b5dc5f4eee88854f5b4abf7b680ef8bc50f"
)

found = False

for log in receipt["logs"]:
    topics = log["topics"]

    if topics and topics[0].hex().lower() == token_purchase_topic:
        buyer = Web3.to_checksum_address("0x" + topics[1].hex()[-40:])
        eth_sold = int(topics[2].hex(), 16)
        tokens_bought = int(topics[3].hex(), 16)

        print("\nUniswap V1 TokenPurchase:")
        print("Buyer:", buyer)
        print("ETH sold:", Web3.from_wei(eth_sold, "ether"))
        print("Tokens bought (raw):", tokens_bought)

        found = True

if not found:
    print("\nNo Uniswap V1 TokenPurchase event found.")
    print("All event signatures:")

    for log in receipt["logs"]:
        print(
            "Contract:", log["address"],
            "| Topic:", log["topics"][0].hex() if log["topics"] else "None"
        )