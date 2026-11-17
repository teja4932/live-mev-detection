import os
import asyncio
import json
import websockets
from dotenv import load_dotenv

load_dotenv()

WS_URL = os.getenv("ALCHEMY_WS_URL")


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

        # Ignore pending subscription messages
        if data.get("id") != request_id:
            continue

        return data.get("result")


async def monitor_pending_transactions():

    if not WS_URL:
        print("❌ ALCHEMY_WS_URL not found in .env")
        return

    print("=" * 70)
    print("      LIVE ETHEREUM TRANSACTION MONITOR - STEP 2")
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
                print("Hash:", tx_hash)

                transaction = await get_transaction(
                    websocket,
                    tx_hash,
                    request_id
                )

                request_id += 1

                if transaction is None:
                    print("⚠️ Transaction details not available yet.")
                    continue

                print("\nTransaction Details:")
                print("-" * 70)

                print("Hash:              ", transaction.get("hash"))
                print("From:              ", transaction.get("from"))
                print("To:                ", transaction.get("to"))
                print("Value:             ", transaction.get("value"))
                print("Gas Price:         ", transaction.get("gasPrice"))
                print("Gas Limit:         ", transaction.get("gas"))
                print("Nonce:             ", transaction.get("nonce"))
                print("Input/Data:        ", transaction.get("input"))

                print("Max Fee Per Gas:   ",
                      transaction.get("maxFeePerGas"))

                print("Max Priority Fee:  ",
                      transaction.get("maxPriorityFeePerGas"))

                print("-" * 70)


asyncio.run(monitor_pending_transactions())