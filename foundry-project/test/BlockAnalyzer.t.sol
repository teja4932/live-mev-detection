// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "forge-std/Test.sol";
import "../src/BlockAnalyzer.sol";

contract BlockAnalyzerTest is Test {

    BlockAnalyzer analyzer;

    address user1 = address(0x1);
    address user2 = address(0x2);
    address user3 = address(0x3);

    function setUp() public {
        analyzer = new BlockAnalyzer();
    }

    // ============================================================
    // HELPER
    // ============================================================

    function createTx(
        address from,
        uint256 value,
        uint256 gasPrice,
        uint256 nonce,
        bytes memory data
    )
        internal
        pure
        returns (BlockAnalyzer.Transaction memory)
    {
        return BlockAnalyzer.Transaction({
            from: from,
            to: address(0x100),
            value: value,
            gasPrice: gasPrice,
            gasLimit: 21000,
            nonce: nonce,
            data: data
        });
    }

    // ============================================================
    // 1. GAS REORDERING
    // ============================================================

    function test_GasReordering() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](3);

        txs[0] = createTx(
            user1,
            1 ether,
            10 gwei,
            1,
            hex"01"
        );

        txs[1] = createTx(
            user2,
            1 ether,
            12 gwei,
            1,
            hex"02"
        );

        txs[2] = createTx(
            user3,
            1 ether,
            40 gwei,
            1,
            hex"03"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
        assertEq(result.scenario, "Gas Reordering");
    }

    // ============================================================
    // 2. FRONT-RUN
    // ============================================================

    function test_FrontRun() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](2);

        // Attacker
        txs[0] = createTx(
            user1,
            0.1 ether,
            100 gwei,
            1,
            hex"aaaa"
        );

        // Victim
        txs[1] = createTx(
            user2,
            1 ether,
            30 gwei,
            1,
            hex"bbbb"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
    }

    // ============================================================
    // 3. BACK-RUN
    // ============================================================

    function test_BackRun() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](2);

        // Victim
        txs[0] = createTx(
            user1,
            1 ether,
            30 gwei,
            1,
            hex"aaaa"
        );

        // Attacker
        txs[1] = createTx(
            user2,
            0.1 ether,
            100 gwei,
            1,
            hex"bbbb"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
    }

    // ============================================================
    // 4. REPEATED TRANSACTION
    // ============================================================

    function test_RepeatedTransaction() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](3);

        txs[0] = createTx(
            user1,
            0.1 ether,
            20 gwei,
            1,
            hex"01"
        );

        txs[1] = createTx(
            user1,
            0.1 ether,
            20 gwei,
            2,
            hex"02"
        );

        txs[2] = createTx(
            user1,
            0.1 ether,
            20 gwei,
            3,
            hex"03"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
    }

    // ============================================================
    // 5. DIRECTION REVERSAL
    // ============================================================

    function test_DirectionReversal() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](2);

        txs[0] = createTx(
            user1,
            1 ether,
            20 gwei,
            1,
            hex"aaaaaaaa"
        );

        txs[1] = createTx(
            user1,
            1 ether,
            20 gwei,
            2,
            hex"bbbbbbbb"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
    }

    // ============================================================
    // 6. SUDDEN INSERTION
    // ============================================================

    function test_SuddenInsertion() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](3);

        txs[0] = createTx(
            user1,
            1 ether,
            10 gwei,
            1,
            hex"01"
        );

        txs[1] = createTx(
            user2,
            1 ether,
            10 gwei,
            1,
            hex"02"
        );

        // Current transaction has a large gas spike.
        txs[2] = createTx(
            user3,
            1 ether,
            100 gwei,
            1,
            hex"03"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
    }

    // ============================================================
    // 7. LIQUIDITY IMPACT
    // ============================================================

    function test_LiquidityImpact() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](3);

        // This transaction represents more than 50%
        // of the total ETH value.

        txs[0] = createTx(
            user1,
            10 ether,
            20 gwei,
            1,
            hex"01"
        );

        txs[1] = createTx(
            user2,
            1 ether,
            20 gwei,
            1,
            hex"02"
        );

        txs[2] = createTx(
            user3,
            1 ether,
            20 gwei,
            1,
            hex"03"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
    }

    // ============================================================
    // 8. SANDWICH ATTACK
    // ============================================================

    function test_SandwichAttack() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](3);

        // Attacker front-run
        txs[0] = createTx(
            user1,
            0.1 ether,
            100 gwei,
            1,
            hex"aaaaaaaa"
        );

        // Victim
        txs[1] = createTx(
            user2,
            1 ether,
            30 gwei,
            1,
            hex"bbbbbbbb"
        );

        // Same attacker after victim
        txs[2] = createTx(
            user1,
            0.1 ether,
            100 gwei,
            2,
            hex"aaaaaaaa"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertTrue(result.isSuspicious);
    }

    // ============================================================
    // NORMAL BLOCK
    // ============================================================

    function test_NormalBlock() public {

        BlockAnalyzer.Transaction[] memory txs =
            new BlockAnalyzer.Transaction[](3);

        txs[0] = createTx(
            user1,
            0.1 ether,
            20 gwei,
            1,
            hex"01"
        );

        txs[1] = createTx(
            user2,
            0.1 ether,
            22 gwei,
            1,
            hex"02"
        );

        txs[2] = createTx(
            user3,
            0.1 ether,
            21 gwei,
            1,
            hex"03"
        );

        BlockAnalyzer.ScenarioResult memory result =
            analyzer.analyzeBlock(txs);

        assertFalse(result.isSuspicious);
        assertEq(result.riskScore, 0);
        assertEq(result.riskLevel, "LOW");
    }
}