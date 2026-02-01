#!/usr/bin/env python3
"""
LTM Hook: SessionStart

Trigger: At beginning of Claude Code session
Action: Load top-N memories into context, increment session counter

Input (stdin): JSON with session_id and transcript_path
Output (stdout): Memories formatted for context injection
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


def main() -> None:
    """Load memories at session start."""
    try:
        # Read hook payload from stdin
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No input or invalid JSON - still run with defaults
        payload = {}

    # Initialize store and calculator
    store = MemoryStore()
    priority_calc = PriorityCalculator()

    # Load and update state
    state = store._read_state()
    state["session_count"] = state.get("session_count", 0) + 1
    state["current_session"] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "tool_failures": 0,
        "tool_successes": 0,
        "compacted": False,
    }
    store._write_state(state)

    # Get configuration
    config = state.get("config", {})
    limit = config.get("memories_to_load", 10)

    # Get top memories by priority
    memories = store.list(limit=limit)

    if not memories:
        # No memories to load
        return

    # Output memories for context injection
    print("## Long-Term Memory Context\n")
    print(f"*Loaded {len(memories)} memories from previous sessions*\n")

    for mem in memories:
        print(f"### {mem['topic']}")
        if mem.get("tags"):
            print(f"*Tags: {', '.join(mem['tags'])}*")
        print(f"*Priority: {mem.get('priority', 0):.2f} | Phase: {mem.get('phase', 0)}*")
        print()

        # Read full content for high-priority memories (phase 0)
        if mem.get("phase", 0) == 0:
            try:
                full_mem = store.read(mem["id"], update_stats=False)
                content = full_mem.get("content", "")
                # Limit content length to avoid overwhelming context
                if len(content) > 500:
                    content = content[:500] + "..."
                print(content)
            except Exception:
                pass  # Skip if can't read

        print("\n---\n")


if __name__ == "__main__":
    main()
