import os
import asyncio
import json
import websockets
from dotenv import load_dotenv

load_dotenv()

WS_URL = os.getenv("ALCHEMY_WS_URL")


async def monitor_pending_transactions():

    if not WS_URL:
        print("❌ ALCHEMY_WS_URL not found in .env")
        return

    print("=" * 70)
    print("      LIVE ETHEREUM PENDING TRANSACTION MONITOR")
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

        while True:

            message = await websocket.recv()
            data = json.loads(message)

            if data.get("method") == "eth_subscription":

                tx_hash = data["params"]["result"]

                print("Pending transaction:")
                print(tx_hash)
                print("-" * 70)


asyncio.run(monitor_pending_transactions())