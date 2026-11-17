import os
import csv
import json
import time
import asyncio
import statistics

from datetime import datetime, timezone
from collections import deque

import psutil
import matplotlib.pyplot as plt
import websockets

import live_monitor as detector


# ============================================================
# EXPERIMENT CONFIGURATION
# ============================================================

TRANSACTION_LIMITS = [100, 300, 500, 1000]
WINDOW_SIZE = 20
RESULTS_DIRECTORY = "results_live"
WS_URL = detector.WS_URL

process = psutil.Process(os.getpid())

DETECTOR_NAMES = [
    "Gas Reordering",
    "Front-Run",
    "Back-Run",
    "Repeated Transaction",
    "Direction Reversal",
    "Sudden Insertion",
    "Liquidity Impact",
    "Sandwich Attack",
    "Gas Anomaly",
    "Risk Scoring",
]


# ============================================================
# DIRECTORY CREATION
# ============================================================

def create_experiment_directory(transaction_limit):

    folder = os.path.join(
        RESULTS_DIRECTORY,
        f"transactions_{transaction_limit}"
    )

    graph_folder = os.path.join(
        folder,
        "performance_graphs"
    )

    os.makedirs(graph_folder, exist_ok=True)

    return folder, graph_folder


# ============================================================
# RUN DETECTION AND MEASURE INDIVIDUAL EXECUTION TIMES
# ============================================================

def run_detection(transactions):

    detector_functions = {
        "Gas Reordering": detector.detect_gas_reordering,
        "Front-Run": detector.detect_front_run,
        "Back-Run": detector.detect_back_run,
        "Repeated Transaction": detector.detect_repeated_transaction,
        "Direction Reversal": detector.detect_direction_reversal,
        "Sudden Insertion": detector.detect_sudden_insertion,
        "Liquidity Impact": detector.detect_liquidity_impact,
        "Sandwich Attack": detector.detect_sandwich,
    }

    timings = {}
    signals = {}
    results = {}

    # Measure the eight detection rules individually.

    for name, function in detector_functions.items():

        start = time.perf_counter()

        detected, details = function(transactions)

        end = time.perf_counter()

        timings[name] = (end - start) * 1000

        signals[name] = detected

        results[name] = detected

    # Measure gas anomaly detection.

    start = time.perf_counter()

    gas_anomaly, gas_details = detector.calculate_gas_anomaly(
        transactions
    )

    end = time.perf_counter()

    timings["Gas Anomaly"] = (end - start) * 1000

    signals["Gas Anomaly"] = gas_anomaly

    # Measure risk scoring.

    start = time.perf_counter()

    risk = detector.calculate_risk_score(
        results["Gas Reordering"],
        results["Front-Run"],
        results["Back-Run"],
        results["Repeated Transaction"],
        results["Direction Reversal"],
        results["Sudden Insertion"],
        results["Liquidity Impact"],
        results["Sandwich Attack"],
        gas_anomaly
    )

    end = time.perf_counter()

    timings["Risk Scoring"] = (end - start) * 1000

    return risk, timings, signals


# ============================================================
# SAVE CSV RESULTS
# ============================================================

def save_csv(path, records, fieldnames):

    with open(
        path,
        "w",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        writer.writerows(records)


# ============================================================
# PERCENTILE CALCULATION
# ============================================================

def calculate_percentile(values, percentile):

    if not values:
        return 0

    sorted_values = sorted(values)

    if len(sorted_values) == 1:
        return sorted_values[0]

    position = (
        percentile / 100
    ) * (len(sorted_values) - 1)

    lower = int(position)

    upper = min(
        lower + 1,
        len(sorted_values) - 1
    )

    fraction = position - lower

    return (
        sorted_values[lower] * (1 - fraction)
        + sorted_values[upper] * fraction
    )


# ============================================================
# DETECTION EFFICIENCY BAR CHART
# ============================================================

def save_efficiency_bar_chart(
    summary,
    value_key,
    title,
    x_label,
    output_path,
    exclude_sandwich=False
):

    """
    Full charts include all ten components.

    Zoomed charts exclude Sandwich Attack visually
    to make smaller execution times easier to compare.

    CSV results always retain all components.
    """

    plot_rows = [
        row for row in summary
        if not (
            exclude_sandwich
            and row["detection_component"] == "Sandwich Attack"
        )
    ]

    # Sort from highest latency to lowest latency.

    plot_rows = sorted(
        plot_rows,
        key=lambda row: row[value_key],
        reverse=True
    )

    if not plot_rows:
        return

    names = [
        row["detection_component"]
        for row in plot_rows
    ]

    values = [
        row[value_key]
        for row in plot_rows
    ]

    figure_height = max(
        5.5,
        0.55 * len(names) + 1.5
    )

    fig, ax = plt.subplots(
        figsize=(11, figure_height)
    )

    bars = ax.barh(
        names,
        values,
        height=0.62
    )

    # Highest latency appears at the top.

    ax.invert_yaxis()

    ax.set_xlabel(x_label)

    ax.set_ylabel("Detection Component")

    ax.set_title(
        title,
        pad=14
    )

    ax.grid(
        axis="x",
        linestyle="--",
        alpha=0.45
    )

    ax.set_axisbelow(True)

    max_value = max(values) if values else 0

    right_padding = (
        max_value * 0.20
        if max_value > 0
        else 0.01
    )

    ax.set_xlim(
        left=0,
        right=max_value + right_padding
    )

    # Display exact numerical values beside bars.

    for bar, value in zip(bars, values):

        ax.annotate(
            f"{value:.5f} ms",

            xy=(
                bar.get_width(),
                bar.get_y() + bar.get_height() / 2
            ),

            xytext=(5, 0),

            textcoords="offset points",

            va="center",

            ha="left",

            fontsize=8
        )

    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close(fig)


# ============================================================
# SAVE DETECTION EFFICIENCY RESULTS
# ============================================================

def save_detection_efficiency(
    detector_timings,
    detector_signal_counts,
    folder,
    graph_folder
):

    summary = []

    for name in DETECTOR_NAMES:

        values = detector_timings[name]

        if not values:
            continue

        summary.append({

            "detection_component": name,

            "average_latency_ms":
                statistics.mean(values),

            "minimum_latency_ms":
                min(values),

            "maximum_latency_ms":
                max(values),

            "p95_latency_ms":
                calculate_percentile(values, 95),

            "standard_deviation_ms":
                statistics.stdev(values)
                if len(values) > 1 else 0,

            "signal_count":
                detector_signal_counts[name],

            "execution_count":
                len(values)

        })

    if not summary:

        print(
            "No detector timing data available."
        )

        return

    # --------------------------------------------------------
    # SAVE CSV
    # --------------------------------------------------------

    efficiency_path = os.path.join(
        folder,
        "detection_efficiency.csv"
    )

    save_csv(
        efficiency_path,
        summary,
        list(summary[0].keys())
    )

    # --------------------------------------------------------
    # 1. FULL AVERAGE LATENCY
    # ALL TEN COMPONENTS
    # --------------------------------------------------------

    save_efficiency_bar_chart(

        summary,

        "average_latency_ms",

        "Detection Efficiency - Average Execution Latency",

        "Average Execution Time (ms)",

        os.path.join(
            graph_folder,
            "detection_efficiency.png"
        ),

        exclude_sandwich=False

    )

    # --------------------------------------------------------
    # 2. FULL P95 LATENCY
    # ALL TEN COMPONENTS
    # --------------------------------------------------------

    save_efficiency_bar_chart(

        summary,

        "p95_latency_ms",

        "Detection Efficiency - P95 Execution Latency",

        "P95 Execution Time (ms)",

        os.path.join(
            graph_folder,
            "detection_efficiency_p95.png"
        ),

        exclude_sandwich=False

    )

    # --------------------------------------------------------
    # 3. ZOOMED AVERAGE LATENCY
    # WITHOUT SANDWICH ATTACK
    # --------------------------------------------------------

    save_efficiency_bar_chart(

        summary,

        "average_latency_ms",

        "Detection Efficiency - Average Latency (Zoomed View)",

        "Average Execution Time (ms)",

        os.path.join(
            graph_folder,
            "detection_efficiency_zoomed.png"
        ),

        exclude_sandwich=True

    )

    # --------------------------------------------------------
    # 4. ZOOMED P95 LATENCY
    # WITHOUT SANDWICH ATTACK
    # --------------------------------------------------------

    save_efficiency_bar_chart(

        summary,

        "p95_latency_ms",

        "Detection Efficiency - P95 Latency (Zoomed View)",

        "P95 Execution Time (ms)",

        os.path.join(
            graph_folder,
            "detection_efficiency_p95_zoomed.png"
        ),

        exclude_sandwich=True

    )

    print(
        "\nDetection efficiency CSV and four graphs saved."
    )


# ============================================================
# GENERATE GENERAL PERFORMANCE GRAPHS
# ============================================================

def generate_graphs(
    records,
    graph_folder,
    transaction_limit
):

    if not records:

        print(
            "No transaction data available for graphs."
        )

        return

    transaction_numbers = [
        row["transaction_number"]
        for row in records
    ]

    detection_latencies = [
        row["detection_latency_ms"]
        for row in records
    ]

    end_to_end_latencies = [
        row["end_to_end_latency_ms"]
        for row in records
    ]

    # --------------------------------------------------------
    # 1. DETECTION LATENCY
    # --------------------------------------------------------

    plt.figure(figsize=(9, 5))

    plt.plot(
        transaction_numbers,
        detection_latencies,
        marker=".",
        markersize=3,
        linewidth=1
    )

    plt.xlabel("Transaction Number")

    plt.ylabel("Detection Latency (ms)")

    plt.title(
        f"Detection Latency - {transaction_limit} Transactions"
    )

    plt.grid(True, alpha=0.4)

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            graph_folder,
            "detection_latency.png"
        ),
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    # --------------------------------------------------------
    # 2. END-TO-END LATENCY
    # --------------------------------------------------------

    plt.figure(figsize=(9, 5))

    plt.plot(
        transaction_numbers,
        end_to_end_latencies,
        marker=".",
        markersize=3,
        linewidth=1
    )

    plt.xlabel("Transaction Number")

    plt.ylabel("End-to-End Latency (ms)")

    plt.title(
        f"End-to-End Latency - {transaction_limit} Transactions"
    )

    plt.grid(True, alpha=0.4)

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            graph_folder,
            "end_to_end_latency.png"
        ),
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    # --------------------------------------------------------
    # 3. MEMORY USAGE
    # --------------------------------------------------------

    plt.figure(figsize=(9, 5))

    plt.plot(
        transaction_numbers,
        [
            row["memory_usage_mb"]
            for row in records
        ],
        label="Memory (MB)"
    )

    plt.xlabel("Transaction Number")

    plt.ylabel("Memory Usage (MB)")

    plt.title(
        f"Memory Usage - {transaction_limit} Transactions"
    )

    plt.grid(True, alpha=0.4)

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            graph_folder,
            "memory_usage.png"
        ),
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()

    # --------------------------------------------------------
    # 4. CPU USAGE
    # --------------------------------------------------------

    plt.figure(figsize=(9, 5))

    plt.plot(
        transaction_numbers,
        [
            row["cpu_usage_percent"]
            for row in records
        ],
        label="CPU Usage"
    )

    plt.xlabel("Transaction Number")

    plt.ylabel("CPU Usage (%)")

    plt.title(
        f"CPU Usage - {transaction_limit} Transactions"
    )

    plt.grid(True, alpha=0.4)

    plt.legend()

    plt.tight_layout()

    plt.savefig(
        os.path.join(
            graph_folder,
            "cpu_usage.png"
        ),
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()


# ============================================================
# RUN ONE LIVE EXPERIMENT
# ============================================================

async def run_experiment(transaction_limit):

    print("\n" + "=" * 65)

    print(
        f"LIVE EXPERIMENT: {transaction_limit} TRANSACTIONS"
    )

    print("=" * 65)

    folder, graph_folder = create_experiment_directory(
        transaction_limit
    )

    # --------------------------------------------------------
    # RESET BUFFER
    # --------------------------------------------------------

    detector.TRANSACTION_BUFFER_SIZE = WINDOW_SIZE

    detector.transaction_buffer = deque(
        maxlen=WINDOW_SIZE
    )

    records = []

    processed_hashes = set()

    duplicate_count = 0

    cpu_samples = []

    memory_samples = []

    # --------------------------------------------------------
    # INITIALIZE DETECTOR MEASUREMENTS
    # --------------------------------------------------------

    detector_timings = {
        name: [] for name in DETECTOR_NAMES
    }

    detector_signal_counts = {
        name: 0 for name in DETECTOR_NAMES
    }

    process.cpu_percent()

    # --------------------------------------------------------
    # CONNECT TO ALCHEMY
    # --------------------------------------------------------

    async with websockets.connect(WS_URL) as websocket:

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

        response = json.loads(
            await websocket.recv()
        )

        if response.get("error"):

            raise RuntimeError(
                f"Alchemy subscription failed: {response['error']}"
            )

        print("\nSubscription successful.")

        print(
            "Subscription ID:",
            response.get("result")
        )

        print(
            "\nWaiting for live Ethereum transactions..."
        )

        experiment_start = time.perf_counter()

        # ====================================================
        # LIVE TRANSACTION LOOP
        # ====================================================

        while len(records) < transaction_limit:

            message = await websocket.recv()

            receive_time = time.perf_counter()

            data = json.loads(message)

            if data.get("method") != "eth_subscription":
                continue

            transaction = (
                data.get("params", {}).get("result")
            )

            if not isinstance(transaction, dict):
                continue

            tx_hash = transaction.get("hash")

            if not tx_hash:
                continue

            # ------------------------------------------------
            # AVOID DUPLICATE TRANSACTIONS
            # ------------------------------------------------

            if tx_hash in processed_hashes:

                duplicate_count += 1

                continue

            # ------------------------------------------------
            # NORMALIZATION
            # ------------------------------------------------

            try:

                normalized_tx = (
                    detector.normalize_transaction(
                        transaction
                    )
                )

            except (ValueError, TypeError) as error:

                print(
                    "\nTransaction normalization failed:",
                    error
                )

                continue

            processed_hashes.add(tx_hash)

            # ------------------------------------------------
            # ADD TO ROLLING BUFFER
            # ------------------------------------------------

            detector.transaction_buffer.append(
                normalized_tx
            )

            current_transactions = list(
                detector.transaction_buffer
            )

            # ------------------------------------------------
            # RUN DETECTION AND RISK SCORING
            # ------------------------------------------------

            detection_start = time.perf_counter()

            risk, per_rule_timings, per_rule_signals = (
                run_detection(current_transactions)
            )

            detection_end = time.perf_counter()

            detection_latency_ms = (
                detection_end - detection_start
            ) * 1000

            end_to_end_latency_ms = (
                detection_end - receive_time
            ) * 1000

            # ------------------------------------------------
            # COLLECT INDIVIDUAL DETECTOR RESULTS
            # ------------------------------------------------

            for name, latency in per_rule_timings.items():

                detector_timings[name].append(
                    latency
                )

            for name, detected in per_rule_signals.items():

                if detected:

                    detector_signal_counts[name] += 1

            # ------------------------------------------------
            # RESOURCE MONITORING
            # ------------------------------------------------

            cpu_usage = process.cpu_percent()

            memory_usage = (
                process.memory_info().rss
                / (1024 * 1024)
            )

            cpu_samples.append(cpu_usage)

            memory_samples.append(memory_usage)

            # ------------------------------------------------
            # RECORD TRANSACTION DATA
            # ------------------------------------------------

            transaction_number = len(records) + 1

            records.append({

                "transaction_number":
                    transaction_number,

                "transaction_hash":
                    tx_hash,

                "timestamp_utc":
                    datetime.now(timezone.utc).isoformat(),

                "from_address":
                    normalized_tx["from_address"],

                "to_address":
                    normalized_tx["to_address"],

                "value_eth":
                    normalized_tx["value_eth"],

                "gas_price_gwei":
                    normalized_tx["gas_price_gwei"],

                "gas_limit":
                    normalized_tx["gas_limit"],

                "nonce":
                    normalized_tx["nonce"],

                "detection_latency_ms":
                    detection_latency_ms,

                "end_to_end_latency_ms":
                    end_to_end_latency_ms,

                "risk_score":
                    risk["risk_score"],

                "risk_level":
                    risk["risk_level"],

                "detected_signals":
                    ", ".join(risk["detected_signals"]),

                "cpu_usage_percent":
                    cpu_usage,

                "memory_usage_mb":
                    memory_usage

            })

            print(
                f"\rProcessed: {transaction_number}/{transaction_limit}"
                f" | Risk: {risk['risk_score']}"
                f" | Detection: {detection_latency_ms:.4f} ms",
                end="",
                flush=True
            )

    experiment_end = time.perf_counter()

    # ========================================================
    # CALCULATE PERFORMANCE METRICS
    # ========================================================

    elapsed_time = (
        experiment_end - experiment_start
    )

    detection_values = [
        row["detection_latency_ms"]
        for row in records
    ]

    end_to_end_values = [
        row["end_to_end_latency_ms"]
        for row in records
    ]

    throughput = (
        len(records) / elapsed_time
        if elapsed_time > 0
        else 0
    )

    metrics = {

        "transaction_limit":
            transaction_limit,

        "processed_transactions":
            len(records),

        "duplicate_notifications":
            duplicate_count,

        "window_size":
            WINDOW_SIZE,

        "experiment_duration_seconds":
            elapsed_time,

        "average_detection_latency_ms":
            statistics.mean(detection_values),

        "minimum_detection_latency_ms":
            min(detection_values),

        "maximum_detection_latency_ms":
            max(detection_values),

        "p95_detection_latency_ms":
            calculate_percentile(
                detection_values,
                95
            ),

        "average_end_to_end_latency_ms":
            statistics.mean(end_to_end_values),

        "p95_end_to_end_latency_ms":
            calculate_percentile(
                end_to_end_values,
                95
            ),

        "throughput_transactions_per_second":
            throughput,

        "average_cpu_usage_percent":
            statistics.mean(cpu_samples),

        "peak_cpu_usage_percent":
            max(cpu_samples),

        "average_memory_usage_mb":
            statistics.mean(memory_samples),

        "peak_memory_usage_mb":
            max(memory_samples),

        "experiment_timestamp":
            datetime.now(timezone.utc).isoformat()

    }

    # ========================================================
    # SAVE TRANSACTION RESULTS
    # ========================================================

    save_csv(
        os.path.join(
            folder,
            "transaction_data.csv"
        ),
        records,
        list(records[0].keys())
    )

    # ========================================================
    # SAVE GENERAL PERFORMANCE METRICS
    # ========================================================

    save_csv(
        os.path.join(
            folder,
            "metrics.csv"
        ),
        [metrics],
        list(metrics.keys())
    )

    # ========================================================
    # SAVE DETECTION EFFICIENCY
    # ========================================================

    save_detection_efficiency(
        detector_timings,
        detector_signal_counts,
        folder,
        graph_folder
    )

    # ========================================================
    # GENERATE GENERAL PERFORMANCE GRAPHS
    # ========================================================

    generate_graphs(
        records,
        graph_folder,
        transaction_limit
    )

    # ========================================================
    # DISPLAY SUMMARY
    # ========================================================

    print("\n\n" + "-" * 65)

    print(
        f"EXPERIMENT COMPLETED: {transaction_limit} TRANSACTIONS"
    )

    print("-" * 65)

    for key, value in metrics.items():

        print(f"{key}: {value}")

    print("-" * 65)

    print(
        "Results saved in:",
        folder
    )


# ============================================================
# MAIN PROGRAM
# ============================================================

async def main():

    if not WS_URL:

        print(
            "ALCHEMY_WS_URL not found in .env"
        )

        return

    os.makedirs(
        RESULTS_DIRECTORY,
        exist_ok=True
    )

    print("=" * 65)

    print(
        "LIVE MEV DETECTOR - PERFORMANCE EVALUATION"
    )

    print("=" * 65)

    print(
        "Transaction source: Alchemy Ethereum WebSocket"
    )

    print(
        "Window size:",
        WINDOW_SIZE
    )

    print(
        "Transaction limits:",
        TRANSACTION_LIMITS
    )

    print(
        "Results directory:",
        RESULTS_DIRECTORY
    )

    for limit in TRANSACTION_LIMITS:

        await run_experiment(limit)

    print(
        "\nAll scalability experiments completed."
    )


# ============================================================
# PROGRAM START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "\nExperiment interrupted by user."
        )