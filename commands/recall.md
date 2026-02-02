---
description: Search memories by keyword
---

# Search Memories

Search the Long-Term Memory system for relevant memories.

## Usage

- `/ltm:recall <query>` - Search memories by keyword

## Instructions

Arguments: $ARGUMENTS

**If no query provided**:
Ask the user: "What would you like to search for?"

**If query is provided**:
Call `mcp__ltm__recall` with:
- `query`: The search query from arguments
- `limit`: 10 (default)

Display the result directly without any additional formatting or commentary. The MCP tool returns pre-formatted markdown output - show it as-is.

Do not add introductory text or summary text. Just show the raw result.
