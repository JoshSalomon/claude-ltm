---
description: Reset token counts (start fresh topic)
---

# LTM Reset

Reset token and tool counts to start fresh for a new topic.

## Usage

- `/ltm:reset` - Reset token segment

## Instructions

Call `mcp__ltm__reset_tokens` and display the result directly without any additional formatting, tables, or commentary. The MCP tool returns pre-formatted markdown output - show it as-is.

Do not add introductory text like "I'll reset..." or summary text after the output. Just show the raw result.

## When to Use

Use this command when:
- Switching to a completely different topic within the same session
- You want the next memory to have its own difficulty score unaffected by previous work
- Starting a new logical unit of work that should be tracked separately

## What Gets Reset

| Metric | Reset? | Description |
|--------|--------|-------------|
| Token count | ✓ Yes | Accumulated tokens from tool responses |
| Tool successes | ✓ Yes | Count of successful tool calls |
| Tool failures | ✓ Yes | Count of failed tool calls |
| Compaction flag | ✗ No | Session-level event, not topic-specific |

**Note:** The compaction flag (`compacted`) is intentionally preserved because it represents a session-level event (context was compacted), not a topic-specific metric. If context was compacted during this session, that information remains relevant for understanding the session's overall complexity.
