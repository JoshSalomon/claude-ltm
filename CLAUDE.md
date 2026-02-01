# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Open Source Project

This is an open source project. All code and dependencies must comply with the following:

- **Use only open source components and packages** (MIT, Apache 2.0, BSD, etc.)
- **No proprietary or closed-source dependencies**
- **No dependencies with restrictive licenses** (GPL is acceptable if the project adopts GPL)
- **Prefer permissively licensed packages** (MIT, Apache 2.0) when multiple options exist

## Project Overview

Long-Term Memory (LTM) system for Claude Code using a hybrid hooks + MCP server architecture. The system automatically loads context at session start, provides on-demand semantic search, and tracks task difficulty.

## Architecture

**Hybrid Approach:**
- **Hooks** (simple Python scripts): Handle automatic operations during session lifecycle
  - `SessionStart`: Load memories into context
  - `PostToolUse`: Track difficulty based on failures
  - `PreCompact`: Save state before context loss
  - `SessionEnd`: Persist and run eviction
- **MCP Server** (Python): Exposes tools for on-demand memory operations; developed locally, optionally containerized for production
  - `store_memory`, `recall`, `list_memories`, `forget`, `get_memory`, `ltm_status`

**Storage Structure:**
```
.claude/ltm/
├── index.json           # Lightweight index for fast lookup
├── state.json           # Session counter, compaction count
├── memories/            # Individual memory files (markdown + YAML frontmatter)
└── archives/            # Evicted detailed content
```

**Priority Algorithm:** `priority = (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)`

**Eviction Phases:** Full (0) → Hint (1) → Abstract (2) → Removed (3)

## Key Design Decisions

- Recency measured in sessions, not calendar time (avoids penalizing memories during project pauses)
- Memory files use markdown with YAML frontmatter for human readability
- Hooks use system Python (no dependencies); MCP server uses containerized Python for isolation

## Proactive Memory Usage

When working on tasks, proactively search for relevant memories:

- **Before debugging**: Use `mcp__ltm__recall` to search for prior solutions to similar errors
- **Before implementing features**: Search for related patterns or past decisions
- **When encountering familiar problems**: Check if there's a stored solution

Example scenarios to trigger recall:
- Error messages or exceptions → search for the error type or message
- Working on a specific component → search for that component name
- Configuration issues → search for "config" or the specific setting

After solving a difficult problem, use `mcp__ltm__store_memory` to save the solution for future reference. Always notify the user when a memory is stored (e.g., "Stored this solution to LTM for future reference.").

## Extended Thinking Memory Consultation

**IMPORTANT**: When operating in extended thinking modes ("think harder" or "ultrathink"), you MUST consult long-term memory as part of your reasoning process:

1. **At the start of extended thinking**: Search for memories related to the current task using `mcp__ltm__recall`
2. **During analysis**: Reference any relevant memories found to inform your approach
3. **Before finalizing**: Check if similar problems were solved before and what worked

This ensures that valuable past learnings are incorporated into complex reasoning tasks.

## LTM Usage

### Slash Commands

| Command | Description |
|---------|-------------|
| `/remember` | Store a new memory interactively |
| `/remember <topic>` | Store a memory with the given topic |
| `/recall <query>` | Search memories by keyword |
| `/forget <id>` | Delete a memory by ID |
| `/ltm` | Show system status |
| `/ltm help` | Show command summary |
| `/ltm list` | List all memories |
| `/ltm list --tag <tag>` | List memories with specific tag |
| `/ltm check` | Check system integrity |
| `/ltm fix` | Fix integrity issues |

### MCP Tools

The LTM MCP server provides these tools:

- `store_memory(topic, content, tags?, auto_tag?)` - Store a new memory
- `recall(query, limit?)` - Search memories
- `list_memories(phase?, tag?, keyword?)` - List with filters
- `get_memory(id)` - Get full memory content
- `forget(id)` - Delete a memory
- `ltm_status()` - Get system status
- `ltm_check()` - Check integrity
- `ltm_fix(archive_orphans?)` - Fix integrity issues

### Examples

```
# Store a debugging solution
/remember Fix for authentication timeout

# Search for database-related memories
/recall database

# Check system health
/ltm check

# List all memories tagged with "api"
/ltm list --tag api
```

### Setup

Register the MCP server with Claude Code:

```bash
# Local development
claude mcp add --transport stdio ltm -- python .claude/ltm/mcp_server.py

# Containerized (podman)
podman build -t ltm-mcp-server .claude/ltm/
claude mcp add --transport stdio ltm -- podman run -i --rm --userns=keep-id -v "$(pwd)/.claude/ltm:/data:Z" ltm-mcp-server
```

Configure hooks in `.claude/settings.local.json` (already configured).
