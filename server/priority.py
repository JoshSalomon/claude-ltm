"""
Priority calculation for LTM memories.

Priority determines which memories are loaded at session start and which
are evicted first. The formula balances three factors:

    priority = (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)

- difficulty: How hard was the task that created this memory (0.0-1.0)
- recency: How recently was this memory accessed, in sessions (0.0-1.0)
- frequency: How often is this memory accessed (0.0-1.0)

Difficulty calculation uses two formulas:

With token counting (session_tokens > 0):
    difficulty = (failure_rate * 0.25) + (tool_count * 0.15) +
                 (token_usage * 0.35) + (compaction * 0.25)

Without token counting (backward compatible):
    difficulty = (failure_rate * 0.5) + (tool_count * 0.3) + (compaction * 0.2)
"""

from __future__ import annotations


class PriorityCalculator:
    """Calculate memory priority scores."""

    # Weight distribution for priority factors
    DIFFICULTY_WEIGHT = 0.4
    RECENCY_WEIGHT = 0.3
    FREQUENCY_WEIGHT = 0.3

    # Normalization constants
    FREQUENCY_CAP = 10  # Max accesses for full frequency score
    TOOL_COUNT_CAP = 50  # Max tool invocations for normalization

    def calculate(
        self,
        memory: dict,
        stats: dict | None,
        current_session: int,
    ) -> float:
        """
        Calculate priority score for a memory.

        Args:
            memory: Memory metadata dict with 'difficulty' field
            stats: Stats dict with 'access_count', 'last_session' fields
                   (may be None for new memories)
            current_session: Current session number

        Returns:
            Priority score between 0.0 and 1.0
        """
        if stats is None:
            stats = {}

        difficulty = memory.get("difficulty", 0.5)
        recency = self._calculate_recency(stats, current_session)
        frequency = self._calculate_frequency(stats)

        priority = (
            difficulty * self.DIFFICULTY_WEIGHT
            + recency * self.RECENCY_WEIGHT
            + frequency * self.FREQUENCY_WEIGHT
        )

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, priority))

    def _calculate_recency(self, stats: dict, current_session: int) -> float:
        """
        Calculate recency score based on sessions since last access.

        Uses decay curve: recency = 1 / (1 + sessions_since_access)

        This gives:
        - Current session: 1.0
        - 1 session ago: 0.5
        - 2 sessions ago: 0.33
        - 9 sessions ago: 0.1
        """
        last_session = stats.get("last_session", 0)
        sessions_since = max(0, current_session - last_session)
        return 1.0 / (1.0 + sessions_since)

    def _calculate_frequency(self, stats: dict) -> float:
        """
        Calculate frequency score based on access count.

        Normalized by FREQUENCY_CAP and capped at 1.0.
        """
        access_count = stats.get("access_count", 0)
        return min(1.0, access_count / self.FREQUENCY_CAP)

    # Default token normalization cap
    DEFAULT_TOKEN_NORMALIZE_CAP = 100000

    def calculate_difficulty(
        self,
        tool_failures: int,
        tool_successes: int,
        compacted: bool,
        session_tokens: int = 0,
        token_normalize_cap: int = DEFAULT_TOKEN_NORMALIZE_CAP,
    ) -> float:
        """
        Calculate difficulty score from session metrics.

        When token counting is available (session_tokens > 0), uses new formula:
            difficulty = (failure_rate * 0.25) + (tool_count_norm * 0.15) +
                        (token_usage * 0.35) + (compaction * 0.25)

        When token counting is not available (session_tokens == 0), uses old formula:
            difficulty = (failure_rate * 0.5) + (tool_count_norm * 0.3) + (compaction * 0.2)

        Args:
            tool_failures: Number of failed tool invocations
            tool_successes: Number of successful tool invocations
            compacted: Whether context compaction occurred
            session_tokens: Total tokens counted in session (0 = disabled)
            token_normalize_cap: Maximum tokens for 1.0 score (default: 100000)

        Returns:
            Difficulty score between 0.0 and 1.0
        """
        total = tool_failures + tool_successes

        if total == 0:
            failure_rate = 0.0
            tool_count_norm = 0.0
        else:
            failure_rate = tool_failures / total
            tool_count_norm = min(1.0, total / self.TOOL_COUNT_CAP)

        compaction_bonus = 1.0 if compacted else 0.0

        if session_tokens > 0:
            # New formula with token usage component
            token_usage_norm = min(1.0, session_tokens / token_normalize_cap)
            difficulty = (
                failure_rate * 0.25
                + tool_count_norm * 0.15
                + token_usage_norm * 0.35
                + compaction_bonus * 0.25
            )
        else:
            # Old formula (backward compatible when token counting disabled)
            difficulty = (
                failure_rate * 0.5
                + tool_count_norm * 0.3
                + compaction_bonus * 0.2
            )

        return max(0.0, min(1.0, difficulty))


# Module-level instance for convenience
_calculator = PriorityCalculator()


def calculate_priority(
    memory: dict,
    stats: dict | None,
    current_session: int,
) -> float:
    """Convenience function for priority calculation."""
    return _calculator.calculate(memory, stats, current_session)


def calculate_difficulty(
    tool_failures: int,
    tool_successes: int,
    compacted: bool,
    session_tokens: int = 0,
    token_normalize_cap: int = PriorityCalculator.DEFAULT_TOKEN_NORMALIZE_CAP,
) -> float:
    """Convenience function for difficulty calculation."""
    return _calculator.calculate_difficulty(
        tool_failures, tool_successes, compacted, session_tokens, token_normalize_cap
    )
