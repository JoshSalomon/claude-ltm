# LTM Testing Guide

This guide walks you through testing the Long-Term Memory system in a live Claude Code session.

## Prerequisites

1. **Plugin Installed**
   ```bash
   # Add the LTM marketplace and install the plugin
   claude plugin marketplace add https://github.com/JoshSalomon/claude-ltm.git
   claude plugin install ltm@claude-ltm

   # Verify installation
   claude plugin list
   ```

2. **Container Running**

   The MCP server runs in a container. It starts automatically when Claude Code connects.

   Verify the container is running:
   ```bash
   podman ps | grep ltm
   ```

3. **Clean State (Optional)**

   For a fresh test, reset the LTM data:
   ```bash
   rm -rf .claude/ltm/memories/*
   rm -rf .claude/ltm/archives/*
   rm -f .claude/ltm/index.json
   rm -f .claude/ltm/stats.json
   rm -f .claude/ltm/state.json
   rm -f .claude/ltm/server.json
   ```

---

## Test 1: Basic Commands

### 1.1 Check System Status

```
/ltm:status
```

**Expected:** Shows system status with:
- Total memories count
- Breakdown by phase
- Configuration settings

### 1.2 Show Help

```
/ltm:help
```

**Expected:** Displays table of all available commands.

### 1.3 List Memories (Empty)

```
/ltm:list
```

**Expected:** Shows empty list or "No memories found" message.

---

## Test 2: Storing Memories

### 2.1 Store with Topic

```
/ltm:remember Database connection pooling fix
```

**Expected:** Claude prompts for content, then stores the memory. Confirms with memory ID.

### 2.2 Store Interactively

```
/ltm:remember
```

**Expected:** Claude prompts for both topic and content.

### 2.3 Verify Storage

```
/ltm:list
```

**Expected:** Shows the memories you just created.

---

## Test 3: Searching Memories

### 3.1 Search by Keyword

```
/ltm:recall database
```

**Expected:** Returns memories matching "database" in topic or content.

### 3.2 Search with No Results

```
/ltm:recall xyznonexistent
```

**Expected:** Shows "No memories found" with suggestions.

### 3.3 Filter by Tag

```
/ltm:list --tag database
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
/ltm:forget mem_XXXXX
```

**Expected:**
1. Claude shows the memory content for confirmation
2. After confirmation, deletes and archives the memory
3. Confirms deletion with archive path

### 4.3 Verify Deletion

```
/ltm:list
```

**Expected:** Deleted memory no longer appears.

---

## Test 5: Integrity Tools

### 5.1 Check Integrity (Healthy)

```
/ltm:check
```

**Expected:** Shows "Healthy" status with no issues.

### 5.2 Create Integrity Issue (Manual)

Create an orphaned file for testing:

```bash
echo -e "---\nid: orphan_test\ntopic: Orphan\n---\nOrphan content" > .claude/ltm/memories/orphan_test.md
```

### 5.3 Check Integrity (Issues Found)

```
/ltm:check
```

**Expected:** Shows "Issues Found" with orphaned file listed.

### 5.4 Fix Integrity Issues

```
/ltm:fix
```

**Expected:**
- Archives the orphaned file
- Removes it from memories
- Reports "System is now healthy"

### 5.5 Verify Fix

```
/ltm:check
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

Perform some operations that might fail (e.g., try to read a non-existent file). The `post_tool_use.sh` hook calls the container to track tool failures.

### 6.3 Session End

Exit the session:

```
/exit
```

**Expected:** Session end hook runs (via HTTP call to container), persisting any state changes.

---

## Test 7: Eviction (Advanced)

To test eviction, you need many memories:

### 7.1 Create Multiple Memories

Store 10+ memories on different topics:

```
/ltm:remember API authentication patterns
/ltm:remember Error handling best practices
/ltm:remember Database migration strategy
/ltm:remember Caching implementation
/ltm:remember Logging configuration
...
```

### 7.2 Check Phases

```
/ltm:list --phase 0
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
/ltm:list --phase 1
```

**Expected:** Shows memories that have been reduced to "Hint" phase.

---

## Test 8: Multi-Session Recency

### 8.1 Access a Memory

```
/ltm:recall database
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
- `stats.json`, `state.json`, and `server.json` are ignored

### 9.2 Commit Memories

```bash
git add .claude/ltm/memories/ .claude/ltm/index.json
git commit -m "Add LTM memories"
```

**Expected:** Only memory content is committed, not volatile stats.

---

## Troubleshooting

### Plugin Not Working

```bash
# Check installation
claude plugin list

# Reinstall if needed
claude plugin uninstall ltm
claude plugin install ltm@claude-ltm
```

### Container Not Running

```bash
# Check container status
podman ps -a | grep ltm

# Check server.json exists
cat .claude/ltm/server.json

# Manually start if needed (usually auto-starts)
bash scripts/run-mcp.sh
```

### Hooks Not Running

Hooks are auto-loaded from the plugin's `hooks/hooks.json`. If they're not running:

1. Verify plugin is installed: `claude plugin list`
2. Check the container is running and `server.json` exists
3. Hooks silently exit if container isn't available

### Reset Everything

```bash
# Stop container
podman stop ltm-server 2>/dev/null || true
podman rm ltm-server 2>/dev/null || true

# Clear data
rm -rf .claude/ltm/memories/*
rm -rf .claude/ltm/archives/*
rm -f .claude/ltm/index.json
rm -f .claude/ltm/stats.json
rm -f .claude/ltm/state.json
rm -f .claude/ltm/server.json
```

---

## Quick Test Checklist

| Test | Command | Pass |
|------|---------|------|
| Show status | `/ltm:status` | [ ] |
| Show help | `/ltm:help` | [ ] |
| List memories | `/ltm:list` | [ ] |
| Store memory | `/ltm:remember Test topic` | [ ] |
| Search memories | `/ltm:recall test` | [ ] |
| Filter by tag | `/ltm:list --tag test` | [ ] |
| Delete memory | `/ltm:forget mem_XXX` | [ ] |
| Check integrity | `/ltm:check` | [ ] |
| Fix integrity | `/ltm:fix` | [ ] |

---

## Expected Test Duration

- Basic commands: 5 minutes
- Full test suite: 15-20 minutes
- Including eviction tests: 30 minutes
