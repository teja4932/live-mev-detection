// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

contract BlockAnalyzer {

    // ============================================================
    // TRANSACTION STRUCTURE
    // ============================================================

    struct Transaction {
        address from;
        address to;
        uint256 value;
        uint256 gasPrice;
        uint256 gasLimit;
        uint256 nonce;
        bytes data;
    }

    // ============================================================
    // ANALYSIS RESULT
    // ============================================================

    struct ScenarioResult {
        bool isSuspicious;
        uint256 riskScore;
        string riskLevel;
        string scenario;
        string recommendation;
        uint256 detectedSignals;
    }

    // ============================================================
    // 1. GAS REORDERING
    // ============================================================

    function checkReordering(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 3) {
            return false;
        }

        uint256 minGas = txs[0].gasPrice;
        uint256 maxGas = txs[0].gasPrice;

        for (uint256 i = 1; i < txs.length; i++) {
            if (txs[i].gasPrice < minGas) {
                minGas = txs[i].gasPrice;
            }

            if (txs[i].gasPrice > maxGas) {
                maxGas = txs[i].gasPrice;
            }
        }

        if (minGas == 0) {
            return false;
        }

        return maxGas > minGas * 3;
    }

    // ============================================================
    // 2. FRONT-RUN DETECTION
    // ============================================================

    function checkFrontRun(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 2) {
            return false;
        }

        Transaction memory attacker = txs[txs.length - 2];
        Transaction memory victim = txs[txs.length - 1];

        if (victim.value == 0) {
            return false;
        }

        if (victim.gasPrice == 0) {
            return false;
        }

        // Attacker pays significantly higher gas.
        if (attacker.gasPrice <= victim.gasPrice * 2) {
            return false;
        }

        // Attacker transaction has relatively small value.
        if (attacker.value >= victim.value * 30 / 100) {
            return false;
        }

        return true;
    }

    // ============================================================
    // 3. BACK-RUN DETECTION
    // ============================================================

    function checkBackRun(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 2) {
            return false;
        }

        Transaction memory victim = txs[txs.length - 2];
        Transaction memory attacker = txs[txs.length - 1];

        if (victim.value == 0) {
            return false;
        }

        if (victim.gasPrice == 0) {
            return false;
        }

        // Attacker follows victim with significantly higher gas.
        if (attacker.gasPrice <= victim.gasPrice * 2) {
            return false;
        }

        if (attacker.value >= victim.value * 30 / 100) {
            return false;
        }

        return true;
    }

    // ============================================================
    // 4. REPEATED TRANSACTION DETECTION
    // ============================================================

    function checkRepeatedTransactions(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 3) {
            return false;
        }

        for (uint256 i = 0; i < txs.length; i++) {

            uint256 count = 0;

            for (uint256 j = 0; j < txs.length; j++) {
                if (txs[i].from == txs[j].from) {
                    count++;
                }
            }

            if (count >= 3) {
                return true;
            }
        }

        return false;
    }

    // ============================================================
    // 5. DIRECTION REVERSAL
    // ============================================================

    function checkDirectionReversal(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 2) {
            return false;
        }

        Transaction memory previous = txs[txs.length - 2];
        Transaction memory current = txs[txs.length - 1];

        // Same sender is required.
        if (previous.from != current.from) {
            return false;
        }

        // Empty calldata cannot tell us transaction direction.
        if (previous.data.length == 0 || current.data.length == 0) {
            return false;
        }

        // Different calldata is used as a preliminary
        // direction-change signal.
        if (
            keccak256(previous.data) !=
            keccak256(current.data)
        ) {
            return true;
        }

        return false;
    }

    // ============================================================
    // 6. SUDDEN INSERTION
    // ============================================================

    function checkSuddenInsertion(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 3) {
            return false;
        }

        uint256 totalGas = 0;

        for (uint256 i = 0; i < txs.length; i++) {
            totalGas += txs[i].gasPrice;
        }

        uint256 averageGas = totalGas / txs.length;

        if (averageGas == 0) {
            return false;
        }

        Transaction memory current = txs[txs.length - 1];

        // Current transaction has a large gas spike.
        if (current.gasPrice > averageGas * 3) {
            return true;
        }

        return false;
    }

    // ============================================================
    // 7. LIQUIDITY IMPACT
    // ============================================================

    function checkLiquidityImpact(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length == 0) {
            return false;
        }

        uint256 totalValue = 0;

        for (uint256 i = 0; i < txs.length; i++) {
            totalValue += txs[i].value;
        }

        if (totalValue == 0) {
            return false;
        }

        for (uint256 i = 0; i < txs.length; i++) {

            if (txs[i].value == 0) {
                continue;
            }

            // One transaction represents more than 50%
            // of the total native ETH value.
            if (txs[i].value * 2 > totalValue) {
                return true;
            }
        }

        return false;
    }

    // ============================================================
    // 8. SANDWICH ATTACK
    // ============================================================

    function checkSandwich(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 3) {
            return false;
        }

        for (uint256 i = 0; i < txs.length - 2; i++) {

            for (uint256 j = i + 1; j < txs.length - 1; j++) {

                for (uint256 k = j + 1; k < txs.length; k++) {

                    Transaction memory first = txs[i];
                    Transaction memory middle = txs[j];
                    Transaction memory last = txs[k];

                    // First and last transactions
                    // must come from the same sender.
                    if (first.from != last.from) {
                        continue;
                    }

                    // Middle transaction must belong
                    // to a different sender.
                    if (first.from == middle.from) {
                        continue;
                    }

                    // Empty calldata is not useful for
                    // this preliminary sandwich signal.
                    if (
                        first.data.length == 0 ||
                        last.data.length == 0
                    ) {
                        continue;
                    }

                    // Same calldata is used as a preliminary
                    // same-direction indicator.
                    if (
                        keccak256(first.data) ==
                        keccak256(last.data)
                    ) {
                        return true;
                    }
                }
            }
        }

        return false;
    }

    // ============================================================
    // GAS ANOMALY
    // ============================================================

    function calculateGasAnomaly(
        Transaction[] memory txs
    )
        internal
        pure
        returns (bool)
    {
        if (txs.length < 2) {
            return false;
        }

        uint256 totalGas = 0;

        for (uint256 i = 0; i < txs.length; i++) {
            totalGas += txs[i].gasPrice;
        }

        uint256 averageGas = totalGas / txs.length;

        if (averageGas == 0) {
            return false;
        }

        Transaction memory current = txs[txs.length - 1];

        // Current gas > 2x average gas.
        if (current.gasPrice > averageGas * 2) {
            return true;
        }

        return false;
    }

    // ============================================================
    // FLAG WEIGHT
    // ============================================================

    function calculateFlagWeight(
        uint256 signalCount
    )
        internal
        pure
        returns (uint256)
    {
        if (signalCount <= 1) {
            return 10;
        }

        if (signalCount <= 3) {
            return 20;
        }

        return 30;
    }

    // ============================================================
    // SCENARIO SEVERITY
    // ============================================================

    function calculateScenarioSeverity(
        bool sandwich,
        bool frontRun,
        bool backRun,
        bool suddenInsertion,
        bool gasReordering,
        bool repeatedTransaction,
        bool directionReversal,
        bool liquidityImpact
    )
        internal
        pure
        returns (
            uint256 severity,
            string memory scenario
        )
    {
        // Highest severity takes priority.

        if (sandwich) {
            return (40, "Sandwich Attack");
        }

        if (frontRun) {
            return (25, "Front-Run");
        }

        if (suddenInsertion) {
            return (20, "Sudden Insertion");
        }

        if (gasReordering) {
            return (15, "Gas Reordering");
        }

        if (backRun) {
            return (15, "Back-Run");
        }

        if (repeatedTransaction) {
            return (10, "Repeated Transaction");
        }

        if (directionReversal) {
            return (10, "Direction Reversal");
        }

        if (liquidityImpact) {
            return (10, "Liquidity Impact");
        }

        return (0, "Normal");
    }

    // ============================================================
    // RISK LEVEL
    // ============================================================

    function getRiskLevel(
        uint256 riskScore
    )
        internal
        pure
        returns (string memory)
    {
        if (riskScore <= 34) {
            return "LOW";
        }

        if (riskScore <= 69) {
            return "MEDIUM";
        }

        return "HIGH";
    }

    // ============================================================
    // RECOMMENDATION
    // ============================================================

    function getRecommendation(
        uint256 riskScore
    )
        internal
        pure
        returns (string memory)
    {
        if (riskScore <= 34) {
            return "[ALLOW] No restrictions needed.";
        }

        if (riskScore <= 69) {
            return "[MONITOR] Additional validation required.";
        }

        return "[BLOCK] Attack risk detected. Block or reject.";
    }

    // ============================================================
    // MAIN BLOCK ANALYSIS
    // ============================================================

    function analyzeBlock(
        Transaction[] memory txs
    )
        external
        pure
        returns (ScenarioResult memory)
    {
        if (txs.length == 0) {
            return ScenarioResult({
                isSuspicious: false,
                riskScore: 0,
                riskLevel: "LOW",
                scenario: "Empty Block",
                recommendation: "[ALLOW] No transactions to analyze.",
                detectedSignals: 0
            });
        }

        // --------------------------------------------------------
        // Run all 8 detection rules
        // --------------------------------------------------------

        bool gasReordering =
            checkReordering(txs);

        bool frontRun =
            checkFrontRun(txs);

        bool backRun =
            checkBackRun(txs);

        bool repeatedTransaction =
            checkRepeatedTransactions(txs);

        bool directionReversal =
            checkDirectionReversal(txs);

        bool suddenInsertion =
            checkSuddenInsertion(txs);

        bool liquidityImpact =
            checkLiquidityImpact(txs);

        bool sandwich =
            checkSandwich(txs);

        // --------------------------------------------------------
        // Count detected signals
        // --------------------------------------------------------

        uint256 signalCount = 0;

        if (gasReordering) {
            signalCount++;
        }

        if (frontRun) {
            signalCount++;
        }

        if (backRun) {
            signalCount++;
        }

        if (repeatedTransaction) {
            signalCount++;
        }

        if (directionReversal) {
            signalCount++;
        }

        if (suddenInsertion) {
            signalCount++;
        }

        if (liquidityImpact) {
            signalCount++;
        }

        if (sandwich) {
            signalCount++;
        }

        // --------------------------------------------------------
        // Gas anomaly
        // --------------------------------------------------------

        bool gasAnomaly =
            calculateGasAnomaly(txs);

        // --------------------------------------------------------
        // Risk score calculation
        // --------------------------------------------------------

        uint256 flagWeight = 0;

        if (signalCount > 0) {
            flagWeight =
                calculateFlagWeight(signalCount);
        }

        (
            uint256 scenarioSeverity,
            string memory scenario
        ) = calculateScenarioSeverity(
            sandwich,
            frontRun,
            backRun,
            suddenInsertion,
            gasReordering,
            repeatedTransaction,
            directionReversal,
            liquidityImpact
        );

        uint256 gasAnomalyScore = 0;

        if (gasAnomaly) {
            gasAnomalyScore = 10;
        }

        uint256 riskScore =
            flagWeight +
            scenarioSeverity +
            gasAnomalyScore;

        // Maximum score = 100.
        if (riskScore > 100) {
            riskScore = 100;
        }

        // --------------------------------------------------------
        // Risk level
        // --------------------------------------------------------

        string memory riskLevel =
            getRiskLevel(riskScore);

        string memory recommendation =
            getRecommendation(riskScore);

        bool suspicious =
            signalCount > 0;

        // --------------------------------------------------------
        // Return result
        // --------------------------------------------------------

        return ScenarioResult({
            isSuspicious: suspicious,
            riskScore: riskScore,
            riskLevel: riskLevel,
            scenario: scenario,
            recommendation: recommendation,
            detectedSignals: signalCount
        });
    }
}