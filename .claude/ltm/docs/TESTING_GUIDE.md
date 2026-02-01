# LTM Testing Guide

This guide walks you through testing the Long-Term Memory system in a live Claude Code session.

## Prerequisites

1. **MCP Server Registered**
   ```bash
   # Verify the LTM MCP server is registered
   claude mcp list

   # If not registered, add it:
   claude mcp add --transport stdio ltm -- python .claude/ltm/mcp_server.py
   ```

2. **Hooks Configured**

   Verify `.claude/settings.local.json` contains the hooks configuration (should already be set up).

3. **Clean State (Optional)**

   For a fresh test, reset the LTM data:
   ```bash
   rm -rf .claude/ltm/memories/*
   rm -rf .claude/ltm/archives/*
   rm -f .claude/ltm/index.json
   rm -f .claude/ltm/stats.json
   rm -f .claude/ltm/state.json
   ```

---

## Test 1: Basic Commands

### 1.1 Check System Status

```
/ltm
```

**Expected:** Shows system status with:
- Total memories count
- Breakdown by phase
- Configuration settings

### 1.2 Show Help

```
/ltm help
```

**Expected:** Displays table of all available commands.

### 1.3 List Memories (Empty)

```
/ltm list
```

**Expected:** Shows empty list or "No memories found" message.

---

## Test 2: Storing Memories

### 2.1 Store with Topic

```
/remember Database connection pooling fix
```

**Expected:** Claude prompts for content, then stores the memory. Confirms with memory ID.

### 2.2 Store Interactively

```
/remember
```

**Expected:** Claude prompts for both topic and content.

### 2.3 Verify Storage

```
/ltm list
```

**Expected:** Shows the memories you just created.

---

## Test 3: Searching Memories

### 3.1 Search by Keyword

```
/recall database
```

**Expected:** Returns memories matching "database" in topic or content.

### 3.2 Search with No Results

```
/recall xyznonexistent
```

**Expected:** Shows "No memories found" with suggestions.

### 3.3 Filter by Tag

```
/ltm list --tag database
```

**Expected:** Shows only memories tagged with "database".

---

## Test 4: Memory Management

### 4.1 Get Full Memory

Ask Claude to retrieve a specific memory:

```
Can you show me the full content of memory mem_XXXXX?
```

**Expected:** Claude uses `get_memory` tool and displays full content.

### 4.2 Delete a Memory

```
/forget mem_XXXXX
```

**Expected:**
1. Claude shows the memory content for confirmation
2. After confirmation, deletes and archives the memory
3. Confirms deletion with archive path

### 4.3 Verify Deletion

```
/ltm list
```

**Expected:** Deleted memory no longer appears.

---

## Test 5: Integrity Tools

### 5.1 Check Integrity (Healthy)

```
/ltm check
```

**Expected:** Shows "Healthy" status with no issues.

### 5.2 Create Integrity Issue (Manual)

Create an orphaned file for testing:

```bash
echo -e "---\nid: orphan_test\ntopic: Orphan\n---\nOrphan content" > .claude/ltm/memories/orphan_test.md
```

### 5.3 Check Integrity (Issues Found)

```
/ltm check
```

**Expected:** Shows "Issues Found" with orphaned file listed.

### 5.4 Fix Integrity Issues

```
/ltm fix
```

**Expected:**
- Archives the orphaned file
- Removes it from memories
- Reports "System is now healthy"

### 5.5 Verify Fix

```
/ltm check
```

**Expected:** Shows "Healthy" status.

---

## Test 6: Session Lifecycle

### 6.1 Session Start Hook

Start a new Claude Code session:

```bash
claude
```

**Expected:** If memories exist, top memories are loaded into context automatically.

### 6.2 Difficulty Tracking

Perform some operations that might fail (e.g., try to read a non-existent file). The `track_difficulty.py` hook tracks tool failures.

### 6.3 Session End

Exit the session:

```
/exit
```

**Expected:** Session end hook runs, persisting any state changes.

---

## Test 7: Eviction (Advanced)

To test eviction, you need many memories:

### 7.1 Create Multiple Memories

Store 10+ memories on different topics:

```
/remember API authentication patterns
/remember Error handling best practices
/remember Database migration strategy
/remember Caching implementation
/remember Logging configuration
...
```

### 7.2 Check Phases

```
/ltm list --phase 0
```

**Expected:** All new memories are in phase 0 (Full).

### 7.3 Trigger Eviction

Eviction runs automatically at session end when memory count exceeds `max_memories`.

To test manually, lower the threshold in state.json:

```json
{
  "config": {
    "max_memories": 5
  }
}
```

Then exit and restart the session. Low-priority memories should transition to phase 1.

### 7.4 Verify Phase Transitions

```
/ltm list --phase 1
```

**Expected:** Shows memories that have been reduced to "Hint" phase.

---

## Test 8: Multi-Session Recency

### 8.1 Access a Memory

```
/recall database
```

### 8.2 Exit and Restart

```
/exit
```

Start new session, then check the memory's priority (it should be higher due to recent access).

---

## Test 9: Git Integration

### 9.1 Check Git Status

```bash
git status
```

**Expected:**
- `memories/*.md` and `index.json` are trackable
- `stats.json` and `state.json` are ignored

### 9.2 Commit Memories

```bash
git add .claude/ltm/memories/ .claude/ltm/index.json
git commit -m "Add LTM memories"
```

**Expected:** Only memory content is committed, not volatile stats.

---

## Troubleshooting

### MCP Server Not Working

```bash
# Check registration
claude mcp list

# Remove and re-add
claude mcp remove ltm
claude mcp add --transport stdio ltm -- python .claude/ltm/mcp_server.py
```

### Hooks Not Running

Check `.claude/settings.local.json` has correct hook configuration.

### Reset Everything

```bash
rm -rf .claude/ltm/memories/*
rm -rf .claude/ltm/archives/*
rm -f .claude/ltm/index.json
rm -f .claude/ltm/stats.json
rm -f .claude/ltm/state.json
```

---

## Quick Test Checklist

| Test | Command | Pass |
|------|---------|------|
| Show status | `/ltm` | [ ] |
| Show help | `/ltm help` | [ ] |
| List memories | `/ltm list` | [ ] |
| Store memory | `/remember Test topic` | [ ] |
| Search memories | `/recall test` | [ ] |
| Filter by tag | `/ltm list --tag test` | [ ] |
| Delete memory | `/forget mem_XXX` | [ ] |
| Check integrity | `/ltm check` | [ ] |
| Fix integrity | `/ltm fix` | [ ] |

---

## Expected Test Duration

- Basic commands: 5 minutes
- Full test suite: 15-20 minutes
- Including eviction tests: 30 minutes
