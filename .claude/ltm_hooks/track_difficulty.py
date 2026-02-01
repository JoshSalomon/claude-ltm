#!/usr/bin/env python3
"""
LTM Hook: PostToolUse (track_difficulty)

Trigger: After each tool invocation
Action: Track success/failure for difficulty scoring

Input (stdin): JSON with tool_name, tool_input, tool_response, tool_use_id
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
    """Track tool success/failure for difficulty scoring."""
    try:
        # Read hook payload from stdin
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No input or invalid JSON - nothing to track
        return

    tool_name = payload.get("tool_name", "")
    tool_response = payload.get("tool_response", {})

    # Initialize store
    store = MemoryStore()

    # Load current state
    state = store._read_state()
    session = state.get("current_session", {})

    # Determine success/failure
    # A tool is considered failed if:
    # - response contains "error" key
    # - response has "success": false
    # - response contains error indicators
    is_failure = False

    if isinstance(tool_response, dict):
        if "error" in tool_response:
            is_failure = True
        elif tool_response.get("success") is False:
            is_failure = True
        elif "Error" in str(tool_response.get("text", "")):
            is_failure = True

    # Update counters
    if is_failure:
        session["tool_failures"] = session.get("tool_failures", 0) + 1
    else:
        session["tool_successes"] = session.get("tool_successes", 0) + 1

    # Save updated state
    state["current_session"] = session
    store._write_state(state)


if __name__ == "__main__":
    main()
