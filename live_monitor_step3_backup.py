import os
import asyncio
import json
import websockets
from dotenv import load_dotenv

load_dotenv()

WS_URL = os.getenv("ALCHEMY_WS_URL")


def hex_to_int(value):
    """Convert Ethereum hexadecimal value to integer."""
    if value is None:
        return None

    if isinstance(value, str) and value.startswith("0x"):
        return int(value, 16)

    return value


def wei_to_eth(value):
    """Convert Wei to ETH."""
    if value is None:
        return None

    return int(value, 16) / 10**18


def wei_to_gwei(value):
    """Convert Wei to Gwei."""
    if value is None:
        return None

    return int(value, 16) / 10**9


def normalize_transaction(tx):
    """Convert raw Ethereum transaction into a clean Python dictionary."""

    return {
        "hash": tx.get("hash"),
        "from_address": tx.get("from"),
        "to_address": tx.get("to"),

        # Wei → ETH
        "value_eth": wei_to_eth(tx.get("value")),

        # Wei → Gwei
        "gas_price_gwei": wei_to_gwei(tx.get("gasPrice")),

        # Hex → integer
        "gas_limit": hex_to_int(tx.get("gas")),
        "nonce": hex_to_int(tx.get("nonce")),

        # Transaction input/data
        "input": tx.get("input"),

        # EIP-1559 fields
        "max_fee_per_gas_gwei":
            wei_to_gwei(tx.get("maxFeePerGas")),

        "max_priority_fee_per_gas_gwei":
            wei_to_gwei(tx.get("maxPriorityFeePerGas"))
    }


async def get_transaction(websocket, tx_hash, request_id):

    request = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "eth_getTransactionByHash",
        "params": [tx_hash]
    }

    await websocket.send(json.dumps(request))

    while True:

        message = await websocket.recv()
        data = json.loads(message)

        if data.get("id") != request_id:
            continue

        return data.get("result")


async def monitor_pending_transactions():

    if not WS_URL:
        print("❌ ALCHEMY_WS_URL not found in .env")
        return

    print("=" * 70)
    print("      LIVE ETHEREUM TRANSACTION MONITOR - STEP 3")
    print("=" * 70)

    async with websockets.connect(WS_URL) as websocket:

        # Subscribe to pending transactions
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_subscribe",
            "params": [
                "newPendingTransactions"
            ]
        }

        await websocket.send(json.dumps(request))

        response = await websocket.recv()

        print("\n✅ Subscription response:")
        print(response)

        print("\n🟢 Listening for pending transactions...\n")

        request_id = 2

        while True:

            message = await websocket.recv()
            data = json.loads(message)

            if data.get("method") == "eth_subscription":

                tx_hash = data["params"]["result"]

                print("\n" + "=" * 70)
                print("PENDING TRANSACTION")
                print("=" * 70)

                transaction = await get_transaction(
                    websocket,
                    tx_hash,
                    request_id
                )

                request_id += 1

                if transaction is None:

                    print("⚠️ Transaction details not available yet.")
                    continue

                # Normalize transaction
                normalized_tx = normalize_transaction(transaction)

                print("\nNormalized Transaction:")
                print("-" * 70)

                print("Hash:                    ",
                      normalized_tx["hash"])

                print("From:                    ",
                      normalized_tx["from_address"])

                print("To:                      ",
                      normalized_tx["to_address"])

                print("Value (ETH):             ",
                      normalized_tx["value_eth"])

                print("Gas Price (Gwei):        ",
                      normalized_tx["gas_price_gwei"])

                print("Gas Limit:               ",
                      normalized_tx["gas_limit"])

                print("Nonce:                   ",
                      normalized_tx["nonce"])

                print("Input/Data:              ",
                      normalized_tx["input"])

                print("Max Fee (Gwei):          ",
                      normalized_tx["max_fee_per_gas_gwei"])

                print("Max Priority Fee (Gwei): ",
                      normalized_tx["max_priority_fee_per_gas_gwei"])

                print("-" * 70)


asyncio.run(monitor_pending_transactions())