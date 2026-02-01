# Search Memories

Search the Long-Term Memory system for relevant memories.

## Usage

- `/recall <query>` - Search memories by keyword

## Instructions

Arguments: $ARGUMENTS

**If no query provided**:
Ask the user: "What would you like to search for?"

**If query is provided**:
1. Call `mcp__ltm__recall` with:
   - `query`: The search query from arguments
   - `limit`: 10 (default)
2. Display results in a readable format:
   - Show memory ID, topic, and a snippet of content
   - If the memory is in hint or abstract phase, indicate that
   - If no results found, inform the user

**Result format example**:
```
Found 3 memories matching "database":

1. [mem_abc123] Fix database connection timeout
   Tags: database, debugging
   "The connection timeout was caused by..."

2. [mem_def456] Database migration guide
   Tags: database, setup
   "When migrating the database..."
```
