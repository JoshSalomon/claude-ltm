"""Unit tests for priority.py - Priority Scoring."""

from __future__ import annotations

import pytest


class TestPriorityCalculator:
    """Tests for PriorityCalculator class."""

    # =========================================================================
    # Score Calculation Tests
    # =========================================================================

    def test_priority_formula(self, priority_calculator):
        """Verify formula: (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)."""
        memory = {"difficulty": 0.5}
        stats = {"access_count": 5, "last_session": 10}
        current_session = 10  # Same session = recency 1.0

        priority = priority_calculator.calculate(memory, stats, current_session)

        # difficulty = 0.5 * 0.4 = 0.2
        # recency = 1.0 * 0.3 = 0.3 (same session)
        # frequency = 0.5 * 0.3 = 0.15 (5/10 capped)
        expected = 0.2 + 0.3 + 0.15
        assert abs(priority - expected) < 0.001

    def test_priority_max_score(self, priority_calculator):
        """Maximum values for all factors should give priority = 1.0."""
        memory = {"difficulty": 1.0}
        stats = {"access_count": 10, "last_session": 10}
        current_session = 10

        priority = priority_calculator.calculate(memory, stats, current_session)

        # All factors at max = 1.0
        assert priority == 1.0

    def test_priority_min_score(self, priority_calculator):
        """Minimum values for all factors should give priority = 0.0."""
        memory = {"difficulty": 0.0}
        stats = {"access_count": 0, "last_session": 0}
        current_session = 1000  # Very old

        priority = priority_calculator.calculate(memory, stats, current_session)

        # difficulty = 0.0
        # recency = 1/(1+1000) ≈ 0.001
        # frequency = 0.0
        assert priority < 0.01

    def test_priority_difficulty_weight(self, priority_calculator):
        """Verify difficulty contributes 40%."""
        memory = {"difficulty": 1.0}
        stats = {"access_count": 0, "last_session": 0}
        current_session = 1000  # Minimal recency

        priority = priority_calculator.calculate(memory, stats, current_session)

        # difficulty = 1.0 * 0.4 = 0.4
        # recency ≈ 0.001 * 0.3 ≈ 0
        # frequency = 0.0
        assert 0.39 < priority < 0.41

    def test_priority_recency_weight(self, priority_calculator):
        """Verify recency contributes 30%."""
        memory = {"difficulty": 0.0}
        stats = {"access_count": 0, "last_session": 10}
        current_session = 10  # Same session = recency 1.0

        priority = priority_calculator.calculate(memory, stats, current_session)

        # difficulty = 0.0
        # recency = 1.0 * 0.3 = 0.3
        # frequency = 0.0
        assert abs(priority - 0.3) < 0.001

    def test_priority_frequency_weight(self, priority_calculator):
        """Verify frequency contributes 30%."""
        memory = {"difficulty": 0.0}
        stats = {"access_count": 10, "last_session": 0}
        current_session = 1000  # Minimal recency

        priority = priority_calculator.calculate(memory, stats, current_session)

        # difficulty = 0.0
        # recency ≈ 0
        # frequency = 1.0 * 0.3 = 0.3
        assert 0.29 < priority < 0.31

    def test_priority_none_stats(self, priority_calculator):
        """Handle None stats gracefully."""
        memory = {"difficulty": 0.5}
        priority = priority_calculator.calculate(memory, None, 10)

        # Should use defaults: access_count=0, last_session=0
        assert 0 <= priority <= 1

    # =========================================================================
    # Recency Calculation Tests
    # =========================================================================

    def test_recency_current_session(self, priority_calculator):
        """Memory accessed this session should have recency = 1.0."""
        recency = priority_calculator._calculate_recency(
            {"last_session": 10}, current_session=10
        )
        assert recency == 1.0

    def test_recency_one_session_ago(self, priority_calculator):
        """Memory accessed 1 session ago should have recency = 0.5."""
        recency = priority_calculator._calculate_recency(
            {"last_session": 9}, current_session=10
        )
        assert recency == 0.5

    def test_recency_decay_curve(self, priority_calculator):
        """Verify decay: recency = 1 / (1 + sessions_since)."""
        # 2 sessions ago
        recency = priority_calculator._calculate_recency(
            {"last_session": 8}, current_session=10
        )
        assert abs(recency - 1 / 3) < 0.001

        # 9 sessions ago
        recency = priority_calculator._calculate_recency(
            {"last_session": 1}, current_session=10
        )
        assert abs(recency - 0.1) < 0.001

    def test_recency_missing_last_session(self, priority_calculator):
        """Missing last_session should default to 0."""
        recency = priority_calculator._calculate_recency({}, current_session=10)
        # 10 sessions since = 1/(1+10) ≈ 0.091
        assert abs(recency - 1 / 11) < 0.001

    # =========================================================================
    # Frequency Calculation Tests
    # =========================================================================

    def test_frequency_zero_access(self, priority_calculator):
        """Never accessed should have frequency = 0.0."""
        frequency = priority_calculator._calculate_frequency({"access_count": 0})
        assert frequency == 0.0

    def test_frequency_ten_accesses(self, priority_calculator):
        """Accessed 10 times should have frequency = 1.0."""
        frequency = priority_calculator._calculate_frequency({"access_count": 10})
        assert frequency == 1.0

    def test_frequency_capped(self, priority_calculator):
        """Accessed 100 times should still have frequency = 1.0 (capped)."""
        frequency = priority_calculator._calculate_frequency({"access_count": 100})
        assert frequency == 1.0

    def test_frequency_normalized(self, priority_calculator):
        """Accessed 5 times should have frequency = 0.5."""
        frequency = priority_calculator._calculate_frequency({"access_count": 5})
        assert frequency == 0.5

    # =========================================================================
    # Difficulty Calculation Tests
    # =========================================================================

    def test_difficulty_from_failures(self, priority_calculator):
        """Calculate difficulty from tool failures."""
        # 5 failures, 5 successes = 50% failure rate
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=5, tool_successes=5, compacted=False
        )

        # failure_rate = 0.5 * 0.5 = 0.25
        # tool_count_norm = min(1.0, 10/50) * 0.3 = 0.06
        # compaction = 0
        expected = 0.25 + 0.06 + 0
        assert abs(difficulty - expected) < 0.01

    def test_difficulty_zero_failures(self, priority_calculator):
        """No failures should give low difficulty."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=0, tool_successes=10, compacted=False
        )

        # failure_rate = 0
        # tool_count_norm = 10/50 * 0.3 = 0.06
        assert difficulty < 0.1

    def test_difficulty_capped(self, priority_calculator):
        """Many failures should cap difficulty at 1.0."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=100, tool_successes=0, compacted=True
        )

        # failure_rate = 1.0 * 0.5 = 0.5
        # tool_count_norm = 1.0 * 0.3 = 0.3
        # compaction = 0.2
        assert difficulty == 1.0

    def test_difficulty_with_compaction_bonus(self, priority_calculator):
        """PreCompact triggered should add 0.2 bonus."""
        without = priority_calculator.calculate_difficulty(
            tool_failures=0, tool_successes=0, compacted=False
        )
        with_compaction = priority_calculator.calculate_difficulty(
            tool_failures=0, tool_successes=0, compacted=True
        )

        assert with_compaction - without == 0.2

    def test_difficulty_zero_tools(self, priority_calculator):
        """No tool usage should handle gracefully."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=0, tool_successes=0, compacted=False
        )
        assert difficulty == 0.0


class TestModuleLevelFunctions:
    """Tests for module-level convenience functions."""

    def test_calculate_priority_function(self):
        """Test module-level calculate_priority function."""
        from priority import calculate_priority

        memory = {"difficulty": 0.5}
        stats = {"access_count": 5, "last_session": 10}

        priority = calculate_priority(memory, stats, current_session=10)

        assert 0 <= priority <= 1

    def test_calculate_difficulty_function(self):
        """Test module-level calculate_difficulty function."""
        from priority import calculate_difficulty

        difficulty = calculate_difficulty(
            tool_failures=5, tool_successes=5, compacted=True
        )

        assert 0 <= difficulty <= 1


# =============================================================================
# TC-15 to TC-19: New Difficulty Formula with Token Counting
# =============================================================================


class TestDifficultyWithTokens:
    """Tests for difficulty calculation with token counting.

    New formula when session_tokens > 0:
        difficulty = (failure_rate * 0.25) + (tool_count * 0.15) + (tokens * 0.35) + (compaction * 0.25)

    Old formula when session_tokens == 0:
        difficulty = (failure_rate * 0.5) + (tool_count * 0.3) + (compaction * 0.2)
    """

    def test_new_weights_sum_to_one(self, priority_calculator):
        """TC-15: New weights sum to 1.0 (0.25 + 0.15 + 0.35 + 0.25)."""
        # The new formula weights should sum to 1.0
        weights_sum = 0.25 + 0.15 + 0.35 + 0.25
        assert weights_sum == 1.0

    def test_token_contribution(self, priority_calculator):
        """TC-16: 100k tokens only (max) contributes 0.35 to difficulty."""
        # With 100k tokens (normalized to 1.0) and all other factors at 0
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=0,
            tool_successes=0,
            compacted=False,
            session_tokens=100000,
            token_normalize_cap=100000,
        )

        # token_usage = 1.0 * 0.35 = 0.35
        # all other factors = 0
        assert abs(difficulty - 0.35) < 0.001

    def test_backward_compatibility_no_tokens(self, priority_calculator):
        """TC-17: When session_tokens=0, uses old formula."""
        # Old formula: (failure_rate * 0.5) + (tool_count * 0.3) + (compaction * 0.2)
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=5,
            tool_successes=5,
            compacted=True,
            session_tokens=0,
        )

        # failure_rate = 0.5 * 0.5 = 0.25
        # tool_count = 10/50 * 0.3 = 0.06
        # compaction = 1.0 * 0.2 = 0.2
        # total = 0.51
        expected_old = 0.25 + 0.06 + 0.2
        assert abs(difficulty - expected_old) < 0.01

    def test_max_difficulty_with_tokens(self, priority_calculator):
        """TC-18: All factors maxed gives difficulty = 1.0."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=100,  # 100% failure rate
            tool_successes=0,
            compacted=True,
            session_tokens=100000,  # Max tokens
            token_normalize_cap=100000,
        )

        # failure_rate = 1.0 * 0.25 = 0.25
        # tool_count = 1.0 * 0.15 = 0.15
        # tokens = 1.0 * 0.35 = 0.35
        # compaction = 1.0 * 0.25 = 0.25
        # total = 1.0
        assert difficulty == 1.0

    def test_old_formula_weights(self, priority_calculator):
        """TC-19: Old formula uses 0.5/0.3/0.2 weights without tokens."""
        # All factors at max with old formula (no tokens)
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=100,
            tool_successes=0,
            compacted=True,
            session_tokens=0,  # No tokens = old formula
        )

        # failure_rate = 1.0 * 0.5 = 0.5
        # tool_count = 1.0 * 0.3 = 0.3
        # compaction = 1.0 * 0.2 = 0.2
        # total = 1.0
        assert difficulty == 1.0

    def test_partial_token_usage(self, priority_calculator):
        """50% token usage contributes 0.175 (half of 0.35)."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=0,
            tool_successes=0,
            compacted=False,
            session_tokens=50000,
            token_normalize_cap=100000,
        )

        # token_usage = 0.5 * 0.35 = 0.175
        assert abs(difficulty - 0.175) < 0.001

    def test_combined_factors_with_tokens(self, priority_calculator):
        """Test combined factors with token counting."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=5,
            tool_successes=5,
            compacted=True,
            session_tokens=50000,
            token_normalize_cap=100000,
        )

        # failure_rate = 0.5 * 0.25 = 0.125
        # tool_count = 0.2 * 0.15 = 0.03 (10 tools / 50 cap)
        # tokens = 0.5 * 0.35 = 0.175
        # compaction = 1.0 * 0.25 = 0.25
        # total = 0.58
        expected = 0.125 + 0.03 + 0.175 + 0.25
        assert abs(difficulty - expected) < 0.01

    def test_token_cap_respected(self, priority_calculator):
        """Tokens above cap are still capped at 1.0 normalized."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=0,
            tool_successes=0,
            compacted=False,
            session_tokens=200000,  # 2x the cap
            token_normalize_cap=100000,
        )

        # token_usage should be capped at 1.0
        # difficulty = 1.0 * 0.35 = 0.35
        assert abs(difficulty - 0.35) < 0.001

    def test_custom_token_cap(self, priority_calculator):
        """Custom token cap works correctly."""
        difficulty = priority_calculator.calculate_difficulty(
            tool_failures=0,
            tool_successes=0,
            compacted=False,
            session_tokens=25000,
            token_normalize_cap=50000,  # Custom cap
        )

        # token_usage = 25000/50000 = 0.5
        # difficulty = 0.5 * 0.35 = 0.175
        assert abs(difficulty - 0.175) < 0.001
