#!/usr/bin/env python3
"""
LTM Hook: PreCompact

Trigger: Before context compaction
Action: Save state, mark compaction (adds difficulty bonus)

Input (stdin): JSON with session_id and transcript_path
Output: None (updates state silently)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add ltm directory to path for imports (hooks are in ltm_hooks, modules in ltm)
sys.path.insert(0, str(Path(__file__).parent.parent / "ltm"))

from store import MemoryStore


def main() -> None:
    """Save state before context compaction."""
    try:
        # Read hook payload from stdin
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No input or invalid JSON - still proceed
        payload = {}

    # Initialize store
    store = MemoryStore()

    # Load current state
    state = store._read_state()
    session = state.get("current_session", {})

    # Mark that compaction occurred (adds difficulty bonus)
    session["compacted"] = True

    # Increment compaction counter
    state["compaction_count"] = state.get("compaction_count", 0) + 1

    # Save updated state
    state["current_session"] = session
    store._write_state(state)


if __name__ == "__main__":
    main()
