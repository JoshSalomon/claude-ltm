#!/usr/bin/env python3
"""
LTM Hook: SessionEnd

Trigger: At end of Claude Code session
Action: Persist state, update priorities, run eviction if needed

Input (stdin): JSON with session_id and transcript_path
Output: None (updates state silently)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add ltm directory to path for imports (hooks are in ltm_hooks, modules in ltm)
sys.path.insert(0, str(Path(__file__).parent.parent / "ltm"))

from store import MemoryStore
from priority import PriorityCalculator
from eviction import EvictionManager, EvictionConfig


def main() -> None:
    """Persist state and run eviction at session end."""
    try:
        # Read hook payload from stdin
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No input or invalid JSON - still proceed
        payload = {}

    # Initialize store and calculator
    store = MemoryStore()
    priority_calc = PriorityCalculator()

    # Load current state
    state = store._read_state()
    current_session_num = state.get("session_count", 1)
    session = state.get("current_session", {})

    # Calculate session difficulty
    tool_failures = session.get("tool_failures", 0)
    tool_successes = session.get("tool_successes", 0)
    compacted = session.get("compacted", False)

    session_difficulty = priority_calc.calculate_difficulty(
        tool_failures, tool_successes, compacted
    )

    # Update priorities for all memories
    stats = store._read_stats()
    index = store._read_index()

    for memory_id, mem_stats in stats.get("memories", {}).items():
        # Get memory metadata from index
        mem_meta = index.get("memories", {}).get(memory_id, {})
        if not mem_meta:
            continue

        # Recalculate priority
        priority = priority_calc.calculate(mem_meta, mem_stats, current_session_num)
        mem_stats["priority"] = priority

    store._write_stats(stats)

    # Check if eviction is needed
    config = state.get("config", {})
    eviction_config = EvictionConfig(
        max_memories=config.get("max_memories", 100),
        batch_size=config.get("eviction_batch_size", 10),
    )

    eviction_manager = EvictionManager(store, eviction_config)
    if eviction_manager.needs_eviction():
        eviction_manager.run()
        state["last_eviction"] = datetime.now(timezone.utc).isoformat()

    # Reset current session state
    state["current_session"] = {}
    store._write_state(state)


if __name__ == "__main__":
    main()
