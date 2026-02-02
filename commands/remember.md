---
description: Store a new memory in LTM
---

# Store a Memory

Store a new memory in the Long-Term Memory system.

## Usage

- `/ltm:remember` - Interactive mode: ask for topic and content
- `/ltm:remember <topic>` - Store a memory with the given topic

## Instructions

Arguments: $ARGUMENTS

**If no arguments provided**:
1. Ask the user: "What topic should this memory be stored under?"
2. After getting the topic, ask: "What content should be stored for this memory? (Use markdown formatting)"
3. Optionally ask: "Any tags to categorize this memory? (comma-separated, or leave empty)"

**If topic is provided in arguments**:
1. Use the provided text as the topic
2. Ask: "What content should be stored for this memory? (Use markdown formatting)"
3. Optionally ask: "Any tags to categorize this memory? (comma-separated, or leave empty)"

**After gathering information**:
1. Call `mcp__ltm__store_memory` with:
   - `topic`: The topic provided
   - `content`: The content provided (formatted as markdown)
   - `tags`: Array of tags if provided, otherwise omit or use `auto_tag: true`
2. Confirm to the user that the memory was stored, showing the memory ID
