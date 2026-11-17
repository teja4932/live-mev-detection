
import os
import asyncio
import json
import websockets
from collections import deque
from dotenv import load_dotenv


# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()

WS_URL = os.getenv("ALCHEMY_WS_URL")

TRANSACTION_BUFFER_SIZE = 20

transaction_buffer = deque(
    maxlen=TRANSACTION_BUFFER_SIZE
)


# ============================================================
# VALUE CONVERSION FUNCTIONS
# ============================================================

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


# ============================================================
# TRANSACTION NORMALIZATION
# ============================================================

def normalize_transaction(tx):

    return {
        "hash": tx.get("hash"),

        "from_address": tx.get("from"),

        "to_address": tx.get("to"),

        "value_eth": wei_to_eth(
            tx.get("value")
        ),

        "gas_price_gwei": wei_to_gwei(
            tx.get("gasPrice")
        ),

        "gas_limit": hex_to_int(
            tx.get("gas")
        ),

        "nonce": hex_to_int(
            tx.get("nonce")
        ),

        "input": tx.get("input"),

        "max_fee_per_gas_gwei":
            wei_to_gwei(
                tx.get("maxFeePerGas")
            ),

        "max_priority_fee_per_gas_gwei":
            wei_to_gwei(
                tx.get("maxPriorityFeePerGas")
            )
    }


# ============================================================
# 1. GAS REORDERING DETECTION
# ============================================================

def detect_gas_reordering(transactions):

    gas_prices = [
        tx["gas_price_gwei"]
        for tx in transactions
        if tx.get("gas_price_gwei") is not None
        and tx.get("gas_price_gwei") > 0
    ]

    if len(gas_prices) < 3:
        return False, None

    min_gas = min(gas_prices)

    max_gas = max(gas_prices)

    threshold = min_gas * 3

    if max_gas > threshold:

        return True, {
            "min_gas_gwei": min_gas,
            "max_gas_gwei": max_gas,
            "threshold_gwei": threshold
        }

    return False, None


# ============================================================
# 2. FRONT-RUN DETECTION
# ============================================================

def detect_front_run(transactions):

    if len(transactions) < 2:
        return False, None

    attacker = transactions[-2]

    victim = transactions[-1]

    attacker_gas = attacker.get(
        "gas_price_gwei"
    )

    victim_gas = victim.get(
        "gas_price_gwei"
    )

    attacker_value = attacker.get(
        "value_eth"
    )

    victim_value = victim.get(
        "value_eth"
    )

    if (
        attacker_gas is None
        or victim_gas is None
        or attacker_value is None
        or victim_value is None
    ):
        return False, None

    if attacker_gas > victim_gas * 2:

        if victim_value > 0:

            if attacker_value < victim_value * 0.3:

                return True, {
                    "attacker_hash":
                        attacker.get("hash"),

                    "victim_hash":
                        victim.get("hash"),

                    "attacker_gas_gwei":
                        attacker_gas,

                    "victim_gas_gwei":
                        victim_gas,

                    "attacker_value_eth":
                        attacker_value,

                    "victim_value_eth":
                        victim_value
                }

    return False, None


# ============================================================
# 3. BACK-RUN DETECTION
# ============================================================

def detect_back_run(transactions):

    if len(transactions) < 2:
        return False, None

    victim = transactions[-2]

    attacker = transactions[-1]

    victim_gas = victim.get(
        "gas_price_gwei"
    )

    attacker_gas = attacker.get(
        "gas_price_gwei"
    )

    victim_value = victim.get(
        "value_eth"
    )

    attacker_value = attacker.get(
        "value_eth"
    )

    if (
        victim_gas is None
        or attacker_gas is None
        or victim_value is None
        or attacker_value is None
    ):
        return False, None

    if attacker_gas > victim_gas * 2:

        if victim_value > 0:

            if attacker_value < victim_value * 0.3:

                return True, {
                    "victim_hash":
                        victim.get("hash"),

                    "attacker_hash":
                        attacker.get("hash"),

                    "victim_gas_gwei":
                        victim_gas,

                    "attacker_gas_gwei":
                        attacker_gas,

                    "victim_value_eth":
                        victim_value,

                    "attacker_value_eth":
                        attacker_value
                }

    return False, None


# ============================================================
# 4. REPEATED TRANSACTION DETECTION
# ============================================================

def detect_repeated_transaction(transactions):

    sender_counts = {}

    for tx in transactions:

        sender = tx.get(
            "from_address"
        )

        if sender is None:
            continue

        sender_counts[sender] = (
            sender_counts.get(sender, 0) + 1
        )

    for sender, count in sender_counts.items():

        if count >= 3:

            return True, {
                "sender": sender,
                "count": count
            }

    return False, None


# ============================================================
# 5. DIRECTION REVERSAL DETECTION
# ============================================================

def detect_direction_reversal(transactions):

    if len(transactions) < 2:
        return False, None

    previous = transactions[-2]

    current = transactions[-1]

    previous_sender = previous.get(
        "from_address"
    )

    current_sender = current.get(
        "from_address"
    )

    previous_input = previous.get(
        "input"
    )

    current_input = current.get(
        "input"
    )

    if (
        previous_sender is None
        or current_sender is None
    ):
        return False, None

    if (
        previous_sender.lower()
        != current_sender.lower()
    ):
        return False, None

    if not previous_input or not current_input:
        return False, None

    if (
        previous_input == "0x"
        or current_input == "0x"
    ):
        return False, None

    # Preliminary live signal:
    # same sender + changed calldata

    if previous_input != current_input:

        return True, {
            "sender": current_sender,

            "previous_hash":
                previous.get("hash"),

            "current_hash":
                current.get("hash"),

            "previous_input":
                previous_input,

            "current_input":
                current_input
        }

    return False, None


# ============================================================
# 6. SUDDEN INSERTION DETECTION
# ============================================================

def detect_sudden_insertion(transactions):

    gas_prices = [
        tx["gas_price_gwei"]
        for tx in transactions
        if tx.get("gas_price_gwei") is not None
        and tx.get("gas_price_gwei") > 0
    ]

    if len(gas_prices) < 3:
        return False, None

    average_gas = (
        sum(gas_prices)
        / len(gas_prices)
    )

    threshold = average_gas * 3

    current_tx = transactions[-1]

    current_gas = current_tx.get(
        "gas_price_gwei"
    )

    if current_gas is None:
        return False, None

    if current_gas > threshold:

        return True, {
            "transaction_hash":
                current_tx.get("hash"),

            "sender":
                current_tx.get("from_address"),

            "gas_price_gwei":
                current_gas,

            "average_gas_gwei":
                average_gas,

            "threshold_gwei":
                threshold
        }

    return False, None


# ============================================================
# 7. LIQUIDITY IMPACT DETECTION
# ============================================================

def detect_liquidity_impact(transactions):

    values = [
        tx["value_eth"]
        for tx in transactions
        if tx.get("value_eth") is not None
        and tx.get("value_eth") > 0
    ]

    if not values:
        return False, None

    total_value = sum(values)

    for tx in transactions:

        value = tx.get(
            "value_eth"
        )

        if value is None or value <= 0:
            continue

        if value * 2 > total_value:

            return True, {
                "transaction_hash":
                    tx.get("hash"),

                "sender":
                    tx.get("from_address"),

                "transaction_value_eth":
                    value,

                "total_value_eth":
                    total_value,

                "impact_ratio":
                    value / total_value
            }

    return False, None


# ============================================================
# 8. SANDWICH ATTACK DETECTION
# ============================================================

def detect_sandwich(transactions):

    if len(transactions) < 3:
        return False, None

    for i in range(
        len(transactions) - 2
    ):

        for j in range(
            i + 1,
            len(transactions) - 1
        ):

            for k in range(
                j + 1,
                len(transactions)
            ):

                first = transactions[i]

                middle = transactions[j]

                last = transactions[k]

                first_sender = first.get(
                    "from_address"
                )

                middle_sender = middle.get(
                    "from_address"
                )

                last_sender = last.get(
                    "from_address"
                )

                if (
                    first_sender is None
                    or middle_sender is None
                    or last_sender is None
                ):
                    continue

                # First and third transactions
                # must have the same sender.

                if (
                    first_sender.lower()
                    != last_sender.lower()
                ):
                    continue

                # Attacker and victim must
                # be different addresses.

                if (
                    first_sender.lower()
                    == middle_sender.lower()
                ):
                    continue

                first_input = first.get(
                    "input"
                )

                last_input = last.get(
                    "input"
                )

                if not first_input or not last_input:
                    continue

                if (
                    first_input == "0x"
                    or last_input == "0x"
                ):
                    continue

                # Preliminary same-direction
                # condition using calldata.

                if first_input != last_input:
                    continue

                return True, {
                    "attacker_address":
                        first_sender,

                    "victim_address":
                        middle_sender,

                    "front_run_hash":
                        first.get("hash"),

                    "victim_hash":
                        middle.get("hash"),

                    "back_run_hash":
                        last.get("hash")
                }

    return False, None


# ============================================================
# GAS ANOMALY CALCULATION
# ============================================================

def calculate_gas_anomaly(transactions):

    if len(transactions) < 2:
        return False, None

    gas_prices = [
        tx.get("gas_price_gwei")
        for tx in transactions
        if tx.get("gas_price_gwei") is not None
        and tx.get("gas_price_gwei") > 0
    ]

    if len(gas_prices) < 2:
        return False, None

    current_tx = transactions[-1]

    current_gas = current_tx.get(
        "gas_price_gwei"
    )

    if current_gas is None:
        return False, None

    average_gas = (
        sum(gas_prices)
        / len(gas_prices)
    )

    threshold = average_gas * 2

    if current_gas > threshold:

        return True, {
            "current_gas_gwei":
                current_gas,

            "average_gas_gwei":
                average_gas,

            "threshold_gwei":
                threshold
        }

    return False, None


# ============================================================
# RISK SCORE CALCULATION
# ============================================================

def calculate_risk_score(
    gas_attack,
    front_run,
    back_run,
    repeated_attack,
    direction_attack,
    sudden_attack,
    liquidity_attack,
    sandwich_attack,
    gas_anomaly
):

    detected_signals = []

    # --------------------------------------------------------
    # Collect detected signals
    # --------------------------------------------------------

    if gas_attack:
        detected_signals.append(
            "Gas Reordering"
        )

    if front_run:
        detected_signals.append(
            "Front-Run"
        )

    if back_run:
        detected_signals.append(
            "Back-Run"
        )

    if repeated_attack:
        detected_signals.append(
            "Repeated Transaction"
        )

    if direction_attack:
        detected_signals.append(
            "Direction Reversal"
        )

    if sudden_attack:
        detected_signals.append(
            "Sudden Insertion"
        )

    if liquidity_attack:
        detected_signals.append(
            "Liquidity Impact"
        )

    if sandwich_attack:
        detected_signals.append(
            "Sandwich Attack"
        )

    signal_count = len(
        detected_signals
    )

    # --------------------------------------------------------
    # Flag Weight
    # --------------------------------------------------------

    if signal_count <= 1:

        flag_weight = 10

    elif signal_count <= 3:

        flag_weight = 20

    else:

        flag_weight = 30

    # --------------------------------------------------------
    # Scenario Severity
    # --------------------------------------------------------

    scenario = "Normal"

    scenario_severity = 0

    if sandwich_attack:

        scenario = "Sandwich Attack"

        scenario_severity = 40

    elif front_run:

        scenario = "Front-Run"

        scenario_severity = 25

    elif sudden_attack:

        scenario = "Sudden Insertion"

        scenario_severity = 20

    elif gas_attack:

        scenario = "Gas Reordering"

        scenario_severity = 15

    elif back_run:

        scenario = "Back-Run"

        scenario_severity = 15

    elif repeated_attack:

        scenario = "Repeated Transaction"

        scenario_severity = 10

    elif direction_attack:

        scenario = "Direction Reversal"

        scenario_severity = 10

    elif liquidity_attack:

        scenario = "Liquidity Impact"

        scenario_severity = 10

    # --------------------------------------------------------
    # Gas Anomaly Score
    # --------------------------------------------------------

    gas_anomaly_score = 0

    if gas_anomaly:

        gas_anomaly_score = 10

    # --------------------------------------------------------
    # Final Risk Score
    # --------------------------------------------------------

    risk_score = (
        flag_weight
        + scenario_severity
        + gas_anomaly_score
    )

    # Maximum score = 100

    risk_score = min(
        risk_score,
        100
    )

    # --------------------------------------------------------
    # Risk Level
    # --------------------------------------------------------

    if risk_score <= 34:

        risk_level = "LOW"

    elif risk_score <= 69:

        risk_level = "MEDIUM"

    else:

        risk_level = "HIGH"

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    if risk_level == "HIGH":

        recommendation = (
            "[BLOCK] Attack detected! "
            "Block this transaction."
        )

    elif risk_level == "MEDIUM":

        recommendation = (
            "[MONITOR] Additional validation required."
        )

    else:

        recommendation = (
            "[ALLOW] No restrictions needed."
        )

    return {
        "detected_signals":
            detected_signals,

        "signal_count":
            signal_count,

        "flag_weight":
            flag_weight,

        "scenario":
            scenario,

        "scenario_severity":
            scenario_severity,

        "gas_anomaly_score":
            gas_anomaly_score,

        "risk_score":
            risk_score,

        "risk_level":
            risk_level,

        "recommendation":
            recommendation
    }


# ============================================================
# MAIN LIVE MONITOR
# ============================================================

async def monitor_pending_transactions():

    if not WS_URL:

        print(
            "❌ ALCHEMY_WS_URL not found in .env"
        )

        return

    print(
        "=" * 70
    )

    print(
        "      LIVE ETHEREUM TRANSACTION MONITOR"
    )

    print(
        "      STEP 6 - RISK SCORING"
    )

    print(
        "=" * 70
    )

    print(
        "\nDetection enabled:"
    )

    print(
        "  • Gas Reordering"
    )

    print(
        "  • Front-Run"
    )

    print(
        "  • Back-Run"
    )

    print(
        "  • Repeated Transaction"
    )

    print(
        "  • Direction Reversal"
    )

    print(
        "  • Sudden Insertion"
    )

    print(
        "  • Liquidity Impact"
    )

    print(
        "  • Sandwich Attack"
    )

    print(
        "\nRisk Scoring:"
    )

    print(
        "  • LOW    : 0 - 34"
    )

    print(
        "  • MEDIUM : 35 - 69"
    )

    print(
        "  • HIGH   : 70 - 100"
    )

    print(
        "\nBuffer size:",
        TRANSACTION_BUFFER_SIZE
    )

    # --------------------------------------------------------
    # CONNECT TO ALCHEMY
    # --------------------------------------------------------

    async with websockets.connect(
        WS_URL
    ) as websocket:

        # ----------------------------------------------------
        # SUBSCRIBE TO PENDING TRANSACTIONS
        # ----------------------------------------------------

        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "eth_subscribe",
            "params": [
                "alchemy_pendingTransactions",
                {
                    "hashesOnly": False
                }
            ]
        }

        await websocket.send(
            json.dumps(request)
        )

        response = await websocket.recv()

        print(
            "\n✅ Subscription response:"
        )

        print(
            response
        )

        print(
            "\n🟢 Listening for pending transactions...\n"
        )

        # ====================================================
        # CONTINUOUS MONITORING LOOP
        # ====================================================

        while True:

            message = await websocket.recv()

            data = json.loads(message)

            if (
                data.get("method")
                != "eth_subscription"
            ):
                continue

            transaction = (
                data.get("params", {}).get("result")
            )

            if not isinstance(transaction, dict):

                continue

            # ------------------------------------------------
            # NORMALIZE TRANSACTION
            # ------------------------------------------------

            normalized_tx = (
                normalize_transaction(
                    transaction
                )
            )

            # ------------------------------------------------
            # ADD TO ROLLING BUFFER
            # ------------------------------------------------

            transaction_buffer.append(
                normalized_tx
            )

            current_transactions = list(
                transaction_buffer
            )

            # =================================================
            # RUN ALL 8 DETECTORS
            # =================================================

            gas_attack, gas_details = (
                detect_gas_reordering(
                    current_transactions
                )
            )

            front_run, front_details = (
                detect_front_run(
                    current_transactions
                )
            )

            back_run, back_details = (
                detect_back_run(
                    current_transactions
                )
            )

            repeated_attack, repeated_details = (
                detect_repeated_transaction(
                    current_transactions
                )
            )

            direction_attack, direction_details = (
                detect_direction_reversal(
                    current_transactions
                )
            )

            sudden_attack, sudden_details = (
                detect_sudden_insertion(
                    current_transactions
                )
            )

            liquidity_attack, liquidity_details = (
                detect_liquidity_impact(
                    current_transactions
                )
            )

            sandwich_attack, sandwich_details = (
                detect_sandwich(
                    current_transactions
                )
            )

            # ------------------------------------------------
            # GAS ANOMALY
            # ------------------------------------------------

            gas_anomaly, gas_anomaly_details = (
                calculate_gas_anomaly(
                    current_transactions
                )
            )

            # =================================================
            # TRANSACTION INFORMATION
            # =================================================

            print(
                "\n" + "=" * 70
            )

            print(
                "NEW PENDING TRANSACTION"
            )

            print(
                "=" * 70
            )

            print(
                "Hash:       ",
                normalized_tx["hash"]
            )

            print(
                "From:       ",
                normalized_tx["from_address"]
            )

            print(
                "To:         ",
                normalized_tx["to_address"]
            )

            print(
                "Value ETH:  ",
                normalized_tx["value_eth"]
            )

            print(
                "Gas Gwei:   ",
                normalized_tx["gas_price_gwei"]
            )

            print(
                "Gas Limit:  ",
                normalized_tx["gas_limit"]
            )

            print(
                "Nonce:      ",
                normalized_tx["nonce"]
            )

            # =================================================
            # TRANSACTION BUFFER
            # =================================================

            print(
                "\nTransaction Buffer"
            )

            print(
                "-" * 70
            )

            print(
                "Current transactions:",
                len(transaction_buffer)
            )

            print(
                "Maximum transactions:",
                TRANSACTION_BUFFER_SIZE
            )

            print(
                "\nRecent transaction hashes:"
            )

            for index, tx in enumerate(
                transaction_buffer,
                start=1
            ):

                print(
                    f"{index}. {tx['hash']}"
                )

            # =================================================
            # MEV DETECTION
            # =================================================

            print(
                "\nMEV Detection"
            )

            print(
                "-" * 70
            )

            # -------------------------------------------------
            # GAS REORDERING
            # -------------------------------------------------

            if gas_attack:

                print(
                    "⚠️ GAS REORDERING SIGNAL DETECTED"
                )

                print(
                    "Minimum Gas (Gwei):",
                    gas_details["min_gas_gwei"]
                )

                print(
                    "Maximum Gas (Gwei):",
                    gas_details["max_gas_gwei"]
                )

                print(
                    "Threshold (Gwei):",
                    gas_details["threshold_gwei"]
                )

            else:

                print(
                    "✅ No gas reordering signal"
                )

            # -------------------------------------------------
            # FRONT-RUN
            # -------------------------------------------------

            if front_run:

                print(
                    "\n⚠️ FRONT-RUN SIGNAL DETECTED"
                )

                print(
                    "Possible attacker:",
                    front_details["attacker_hash"]
                )

                print(
                    "Possible victim:",
                    front_details["victim_hash"]
                )

                print(
                    "Attacker Gas (Gwei):",
                    front_details["attacker_gas_gwei"]
                )

                print(
                    "Victim Gas (Gwei):",
                    front_details["victim_gas_gwei"]
                )

            else:

                print(
                    "No front-run signal"
                )

            # -------------------------------------------------
            # BACK-RUN
            # -------------------------------------------------

            if back_run:

                print(
                    "\n⚠️ BACK-RUN SIGNAL DETECTED"
                )

                print(
                    "Possible victim:",
                    back_details["victim_hash"]
                )

                print(
                    "Possible attacker:",
                    back_details["attacker_hash"]
                )

                print(
                    "Victim Gas (Gwei):",
                    back_details["victim_gas_gwei"]
                )

                print(
                    "Attacker Gas (Gwei):",
                    back_details["attacker_gas_gwei"]
                )

            else:

                print(
                    "No back-run signal"
                )

            # -------------------------------------------------
            # REPEATED TRANSACTION
            # -------------------------------------------------

            if repeated_attack:

                print(
                    "\n⚠️ REPEATED TRANSACTION SIGNAL DETECTED"
                )

                print(
                    "Sender:",
                    repeated_details["sender"]
                )

                print(
                    "Transaction count:",
                    repeated_details["count"]
                )

            else:

                print(
                    "No repeated transaction signal"
                )

            # -------------------------------------------------
            # DIRECTION REVERSAL
            # -------------------------------------------------

            if direction_attack:

                print(
                    "\n⚠️ DIRECTION REVERSAL SIGNAL DETECTED"
                )

                print(
                    "Sender:",
                    direction_details["sender"]
                )

                print(
                    "Previous transaction:",
                    direction_details["previous_hash"]
                )

                print(
                    "Current transaction:",
                    direction_details["current_hash"]
                )

            else:

                print(
                    "No direction reversal signal"
                )

            # -------------------------------------------------
            # SUDDEN INSERTION
            # -------------------------------------------------

            if sudden_attack:

                print(
                    "\n⚠️ SUDDEN INSERTION SIGNAL DETECTED"
                )

                print(
                    "Transaction:",
                    sudden_details["transaction_hash"]
                )

                print(
                    "Gas Price (Gwei):",
                    sudden_details["gas_price_gwei"]
                )

                print(
                    "Average Gas (Gwei):",
                    sudden_details["average_gas_gwei"]
                )

                print(
                    "Threshold (Gwei):",
                    sudden_details["threshold_gwei"]
                )

            else:

                print(
                    "No sudden insertion signal"
                )

            # -------------------------------------------------
            # LIQUIDITY IMPACT
            # -------------------------------------------------

            if liquidity_attack:

                print(
                    "\n⚠️ LIQUIDITY IMPACT SIGNAL DETECTED"
                )

                print(
                    "Transaction:",
                    liquidity_details["transaction_hash"]
                )

                print(
                    "Transaction Value (ETH):",
                    liquidity_details["transaction_value_eth"]
                )

                print(
                    "Total Buffer Value (ETH):",
                    liquidity_details["total_value_eth"]
                )

                print(
                    "Impact Ratio:",
                    round(
                        liquidity_details["impact_ratio"],
                        4
                    )
                )

            else:

                print(
                    "No liquidity impact signal"
                )

            # -------------------------------------------------
            # SANDWICH
            # -------------------------------------------------

            if sandwich_attack:

                print(
                    "\n⚠️ SANDWICH ATTACK SIGNAL DETECTED"
                )

                print(
                    "Possible attacker:",
                    sandwich_details["attacker_address"]
                )

                print(
                    "Possible victim:",
                    sandwich_details["victim_address"]
                )

                print(
                    "Front-run transaction:",
                    sandwich_details["front_run_hash"]
                )

                print(
                    "Victim transaction:",
                    sandwich_details["victim_hash"]
                )

                print(
                    "Back-run transaction:",
                    sandwich_details["back_run_hash"]
                )

            else:

                print(
                    "No sandwich attack signal"
                )

            print(
                "-" * 70
            )

            print(
                "⚠️ Detection results are "
                "suspicious signals, not proof "
                "of an MEV attack."
            )

            # =================================================
            # RISK SCORE
            # =================================================

            risk = calculate_risk_score(

                gas_attack,

                front_run,

                back_run,

                repeated_attack,

                direction_attack,

                sudden_attack,

                liquidity_attack,

                sandwich_attack,

                gas_anomaly
            )

            # =================================================
            # RISK ASSESSMENT
            # IMPORTANT: THIS IS INSIDE THE LOOP
            # =================================================

            print(
                "\n" + "=" * 70
            )

            print(
                "RISK ASSESSMENT"
            )

            print(
                "=" * 70
            )

            print(
                "Detected Signals:",
                risk["signal_count"]
            )

            if risk["detected_signals"]:

                print(
                    "Signals:",
                    ", ".join(
                        risk["detected_signals"]
                    )
                )

            else:

                print(
                    "Signals: None"
                )

            print(
                "Flag Weight:",
                risk["flag_weight"]
            )

            print(
                "Scenario:",
                risk["scenario"]
            )

            print(
                "Scenario Severity:",
                risk["scenario_severity"]
            )

            if gas_anomaly:

                print(
                    "Gas Anomaly: YES"
                )

                print(
                    "Current Gas (Gwei):",
                    gas_anomaly_details["current_gas_gwei"]
                )

                print(
                    "Average Gas (Gwei):",
                    gas_anomaly_details["average_gas_gwei"]
                )

                print(
                    "Gas Threshold (Gwei):",
                    gas_anomaly_details["threshold_gwei"]
                )

            else:

                print(
                    "Gas Anomaly: NO"
                )

            print(
                "Gas Anomaly Score:",
                risk["gas_anomaly_score"]
            )

            print(
                "-" * 70
            )

            print(
                "RISK SCORE:",
                risk["risk_score"],
                "/ 100"
            )

            print(
                "RISK LEVEL:",
                risk["risk_level"]
            )

            print(
                "RECOMMENDATION:",
                risk["recommendation"]
            )

            print(
                "=" * 70
            )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            monitor_pending_transactions()
        )

    except KeyboardInterrupt:

        print(
            "\n\n🛑 Live monitor stopped by user."
        )
