import os
import asyncio
import json
import websockets
from collections import deque
from dotenv import load_dotenv

load_dotenv()

WS_URL = os.getenv("ALCHEMY_WS_URL")

# Keep the most recent 20 pending transactions
TRANSACTION_BUFFER_SIZE = 20
transaction_buffer = deque(maxlen=TRANSACTION_BUFFER_SIZE)


def hex_to_int(value):
    if value is None:
        return None

    if isinstance(value, str) and value.startswith("0x"):
        return int(value, 16)

    return value


def wei_to_eth(value):
    if value is None:
        return None

    return int(value, 16) / 10**18


def wei_to_gwei(value):
    if value is None:
        return None

    return int(value, 16) / 10**9


def normalize_transaction(tx):

    return {
        "hash": tx.get("hash"),
        "from_address": tx.get("from"),
        "to_address": tx.get("to"),
        "value_eth": wei_to_eth(tx.get("value")),
        "gas_price_gwei": wei_to_gwei(tx.get("gasPrice")),
        "gas_limit": hex_to_int(tx.get("gas")),
        "nonce": hex_to_int(tx.get("nonce")),
        "input": tx.get("input"),
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
    print("      LIVE ETHEREUM TRANSACTION MONITOR - STEP 4")
    print("=" * 70)

    async with websockets.connect(WS_URL) as websocket:

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

            if data.get("method") != "eth_subscription":
                continue

            tx_hash = data["params"]["result"]

            transaction = await get_transaction(
                websocket,
                tx_hash,
                request_id
            )

            request_id += 1

            if transaction is None:
                print("⚠️ Transaction details not available yet.")
                continue

            normalized_tx = normalize_transaction(transaction)

            # Add transaction to rolling buffer
            transaction_buffer.append(normalized_tx)

            print("\n" + "=" * 70)
            print("NEW PENDING TRANSACTION")
            print("=" * 70)

            print("Hash:       ", normalized_tx["hash"])
            print("From:       ", normalized_tx["from_address"])
            print("To:         ", normalized_tx["to_address"])
            print("Value ETH:  ", normalized_tx["value_eth"])
            print("Gas Gwei:   ", normalized_tx["gas_price_gwei"])
            print("Gas Limit:  ", normalized_tx["gas_limit"])
            print("Nonce:      ", normalized_tx["nonce"])

            print("\nTransaction Buffer")
            print("-" * 70)
            print("Current transactions:", len(transaction_buffer))
            print("Maximum transactions:", TRANSACTION_BUFFER_SIZE)

            print("\nRecent transaction hashes:")

            for index, tx in enumerate(transaction_buffer, start=1):
                print(f"{index}. {tx['hash']}")

            print("-" * 70)


asyncio.run(monitor_pending_transactions())