# Long-Term Memory (LTM) System - Product Requirements Document

**Version: 1.4.1 | Last Updated: 2026-02-01**

---

## 1. Problem Statement

Claude Code sessions are ephemeral by design. When a session ends or context is compacted, valuable learnings are lost:

- **Debugging insights**: Solutions to complex bugs that took significant effort to diagnose
- **Project-specific patterns**: Architectural decisions, coding conventions, and domain knowledge
- **User preferences**: Communication style, preferred tools, and workflow patterns
- **Historical context**: What was tried before, what failed, and why certain approaches were chosen

Developers repeatedly explain the same context, re-discover the same solutions, and lose productivity to this "session amnesia." A long-term memory system would allow Claude Code to retain and recall important information across sessions.

---

## 2. Goals & Non-Goals

### Goals

1. **Automatic context loading**: Surface relevant memories at session start without user intervention
2. **Explicit memory storage**: Allow users and Claude to store important learnings on-demand
3. **Semantic search**: Enable keyword and tag-based memory retrieval
4. **Graceful degradation**: Implement phased eviction to manage storage while preserving core insights
5. **Difficulty tracking**: Prioritize memories from challenging tasks that required significant effort
6. **Human readability**: Store memories in formats that users can read, edit, and version control
7. **GitOps compatibility**: Support version control workflows with merge-friendly files, minimal conflicts, and easy branch synchronization

### Non-Goals

1. **Cross-project memory sharing**: Memories are scoped to the project directory
2. **Cloud synchronization**: All storage is local; cloud sync is out of scope
3. **Natural language understanding**: Initial search is keyword/tag-based, not semantic AI search
4. **Automatic memory creation**: The system stores what it's told; it doesn't auto-extract insights
5. **Memory merging/deduplication**: Related memories remain separate; no automatic consolidation
6. **Real-time collaboration**: Single-user focus; no multi-user memory sharing

---

## 3. User Stories

### US-1: Remember Past Debugging Sessions
> As a developer, I want Claude to remember past debugging sessions so that when I encounter similar issues, Claude can reference what worked before.

**Acceptance Criteria:**
- Memories from previous debugging sessions are loaded at session start
- Memories include the problem description, solution, and relevant context
- Higher-difficulty debugging sessions are prioritized in recall

### US-2: Explicitly Store Important Learnings
> As a developer, I want to explicitly store important learnings so that they persist beyond the current session.

**Acceptance Criteria:**
- I can instruct Claude to "remember this" and provide content to store
- Stored memories include topic, content, and optional tags
- Tags can be auto-generated from content when not explicitly provided
- Confirmation is provided when a memory is successfully stored

### US-3: Search Memories by Keyword/Tag
> As a developer, I want to search memories by keyword or tag so that I can find relevant information quickly.

**Acceptance Criteria:**
- I can filter memories by tag (e.g., "show memories tagged 'database'")
- I can search memories by keyword in the topic
- Results are sorted by priority (difficulty, recency, frequency)

### US-4: Graceful Memory Degradation
> As a developer, I want memories to gracefully degrade over time so that storage remains manageable while core insights are preserved.

**Acceptance Criteria:**
- Memories transition through phases: Full → Hint → Abstract → Removed
- Detailed content is archived before being reduced
- High-priority memories are retained longer than low-priority ones

### US-5: Track Task Difficulty
> As a developer, I want the system to track task difficulty so that memories from challenging tasks are prioritized.

**Acceptance Criteria:**
- Tool failures and retries increase the difficulty score
- Difficulty is factored into the priority algorithm
- I can see difficulty scores in memory metadata

### US-6: View Memory System Status
> As a developer, I want to view the memory system status so that I understand storage usage and system health.

**Acceptance Criteria:**
- I can see total memory count and storage size
- I can see breakdown by eviction phase
- I can see session count and last eviction timestamp

---

## 4. Functional Requirements

### FR-1: Memory Storage (CRUD Operations)

| Operation | Description |
|-----------|-------------|
| **Create** | Store a new memory with topic, content, tags, and metadata |
| **Read** | Retrieve a specific memory by ID |
| **Update** | Modify an existing memory's content or metadata |
| **Delete** | Remove a memory (soft delete to archive, then hard delete) |
| **List** | List memories with optional filtering by phase, tag, or keyword |
| **Search** | Find memories matching a keyword in topic or content |

### FR-2: Automatic Context Loading (SessionStart Hook)

- Load top-N highest-priority memories at session start
- Output memories to stdout for context injection
- Complete within 5-second timeout
- Configurable number of memories to load (default: 10)

### FR-3: Difficulty Tracking (PostToolUse Hook)

- Track tool invocation outcomes (success/failure)
- Increment difficulty score on failures and retries
- Associate difficulty with current task/memory
- Persist difficulty scores to state

### FR-4: State Preservation (PreCompact Hook)

- Save current session state before context compaction
- Preserve any in-flight memory operations
- Update session counter and timestamps

### FR-5: Session Cleanup (SessionEnd Hook)

- Persist all pending memory changes
- Run eviction if threshold exceeded
- Update recency scores for accessed memories
- Increment session counter

### FR-6: Phased Eviction

| Phase | Name | Content | Stored |
|-------|------|---------|--------|
| 0 | Full | Complete content | `memories/` |
| 1 | Hint | Topic + key points | `memories/` |
| 2 | Abstract | One-line summary | `memories/` |
| 3 | Removed | Archived only | `archives/` |

**Eviction Rules:**
- Trigger when total memories exceed configurable threshold (default: 100)
- Process lowest-priority memories first
- Advance one phase per eviction cycle
- Archive detailed content before reduction

### FR-7: Priority Algorithm

```
priority = (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)
```

| Factor | Range | Description |
|--------|-------|-------------|
| `difficulty` | 0.0-1.0 | Normalized score based on tool failures |
| `recency` | 0.0-1.0 | Sessions since last access (decay curve) |
| `frequency` | 0.0-1.0 | Normalized access count |

### FR-8: MCP Tools

| Tool | Parameters | Description |
|------|------------|-------------|
| `store_memory` | `topic`, `content`, `tags[]`, `auto_tag?`, `difficulty?` | Store a new memory |
| `recall` | `query`, `limit?` | Search memories by query |
| `list_memories` | `phase?`, `tag?`, `keyword?`, `limit?` | List memories with filters |
| `get_memory` | `id` | Get full memory content |
| `forget` | `id` | Delete a memory |
| `ltm_status` | (none) | Get system status |
| `ltm_check` | (none) | Check system integrity |
| `ltm_fix` | `archive_orphans?`, `clean_orphaned_archives?` | Fix integrity issues |

### FR-9: Slash Commands (User Interface)

Claude Code slash commands provide a user-friendly interface to the LTM system.

#### Basic Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/remember` | Store a memory interactively | `/remember` → prompts for topic and content |
| `/remember <topic>` | Store a memory with given topic | `/remember Fix for auth bug` |
| `/recall <query>` | Search memories by keyword | `/recall database timeout` |
| `/forget <id>` | Delete a memory by ID | `/forget mem_abc123` |

#### Status and Listing Commands

| Command | Description |
|---------|-------------|
| `/ltm` | Show LTM system status (memory count, storage, health) |
| `/ltm help` | Show command summary |
| `/ltm list` | List all memories with priority scores |
| `/ltm list --tag <tag>` | List memories filtered by tag |
| `/ltm list --phase <n>` | List memories filtered by eviction phase |

#### Setup and Maintenance Commands

| Command | Description |
|---------|-------------|
| `/ltm init` | Initialize LTM for the project (configure hooks + add CLAUDE.md instructions) |
| `/ltm check` | Check LTM integrity (detect orphaned files and missing references) |
| `/ltm fix` | Fix LTM integrity issues (remove orphans, clean up broken references) |
| `/ltm fix --clean-archives` | Fix issues and also remove orphaned archive files |

**Initialization (`/ltm init`):**
- Configure hooks in `.claude/settings.local.json` (no manual JSON editing required)
- Add proactive memory usage instructions to project's CLAUDE.md
- Remind user to restart Claude Code for hooks to take effect

**Integrity Check (`/ltm check`):**
- Detect memory files in `memories/` with no corresponding index entry
- Detect index entries with no corresponding memory file
- Detect stats entries with no corresponding index entry
- Report archive files that reference deleted memories
- Return summary of issues found (or "All clear" if none)

**Integrity Fix (`/ltm fix`):**
- Remove orphaned memory files (files with no index entry)
- Remove orphaned index entries (entries with no memory file)
- Remove orphaned stats entries (entries with no index entry)
- Archive orphaned memory files before deletion (default: true)
- With `--clean-archives`: also remove orphaned archive files
- Return summary of actions taken

---

## 5. Non-Functional Requirements

### NFR-1: Performance

| Requirement | Target |
|-------------|--------|
| Hook execution time | < 5 seconds (Claude Code timeout) |
| MCP tool response time | < 2 seconds |
| Memory load at session start | < 3 seconds for 100 memories |
| Search latency | < 1 second for 1000 memories |

### NFR-2: Storage

| Requirement | Details |
|-------------|---------|
| Format | Markdown with YAML frontmatter |
| Location | `.claude/ltm/` in project root |
| Git-friendly | Human-readable, diff-able files |
| Index | JSON file for fast lookups |

### NFR-3: Isolation

| Environment | Implementation |
|-------------|----------------|
| Development | Local Python with pip dependencies |
| Production | Containerized MCP server via Docker |

### NFR-4: Reliability

| Requirement | Details |
|-------------|---------|
| Data integrity | Atomic writes to prevent corruption |
| Crash recovery | State file enables recovery on restart |
| Graceful degradation | System functions if MCP unavailable |

### NFR-5: Security

| Requirement | Details |
|-------------|---------|
| Data location | All data stored locally in project |
| No network access | MCP server operates offline |
| File permissions | Standard user permissions apply |

---

## 6. API Specification

### MCP Tool: `store_memory`

Store a new memory in the system.

**Parameters:**
```python
{
    "topic": str,           # Brief description (required)
    "content": str,         # Full content to store (required)
    "tags": list[str],      # Optional categorization tags
    "auto_tag": bool,       # Auto-generate tags from content (default: False)
    "difficulty": float,    # Optional difficulty score (0.0-1.0)
}
```

**Auto-tagging behavior:**
- MCP tool: Explicit control via `auto_tag` parameter (default: `False`)
- User command (e.g., "remember this"): `auto_tag` defaults to `True` when no tags provided, `False` when tags are explicitly specified

When auto-tagging is enabled, the system extracts relevant tags from the topic and content (e.g., file extensions, technology names, common patterns).

**Response:**
```python
{
    "success": bool,
    "id": str,              # Generated memory ID
    "message": str,         # Confirmation message
}
```

### MCP Tool: `recall`

Search memories by query string.

**Parameters:**
```python
{
    "query": str,           # Search query (required)
    "limit": int,           # Max results (default: 10)
}
```

**Response:**
```python
{
    "memories": [
        {
            "id": str,
            "topic": str,
            "summary": str,     # Truncated content
            "priority": float,
            "phase": int,
            "tags": list[str],
        }
    ],
    "total": int,
}
```

### MCP Tool: `list_memories`

List memories with optional filtering.

**Parameters:**
```python
{
    "phase": int | None,        # Filter by eviction phase (0-3)
    "tag": str | None,          # Filter by tag
    "keyword": str | None,      # Filter by keyword in topic
    "limit": int,               # Max results (default: 50)
    "offset": int,              # Pagination offset (default: 0)
}
```

**Response:**
```python
{
    "memories": [
        {
            "id": str,
            "topic": str,
            "phase": int,
            "priority": float,
            "tags": list[str],
            "created_at": str,
            "accessed_at": str,
        }
    ],
    "total": int,
    "has_more": bool,
}
```

### MCP Tool: `get_memory`

Retrieve full content of a specific memory.

**Parameters:**
```python
{
    "id": str,              # Memory ID (required)
}
```

**Response:**
```python
{
    "id": str,
    "topic": str,
    "content": str,         # Full content
    "tags": list[str],
    "phase": int,
    "priority": float,
    "difficulty": float,
    "access_count": int,
    "created_at": str,
    "accessed_at": str,
    "created_session": int,
    "last_session": int,
}
```

### MCP Tool: `forget`

Delete a memory from the system.

**Parameters:**
```python
{
    "id": str,              # Memory ID (required)
}
```

**Response:**
```python
{
    "success": bool,
    "message": str,
    "archived": bool,       # True if content was archived
}
```

### MCP Tool: `ltm_status`

Get system status and statistics.

**Parameters:** None

**Response:**
```python
{
    "total_memories": int,
    "by_phase": {
        "full": int,
        "hint": int,
        "abstract": int,
    },
    "total_archived": int,
    "session_count": int,
    "last_eviction": str | None,
    "storage_size_bytes": int,
}
```

---

## 7. Storage Architecture

### Design Decision: Volatile vs Stable Metadata

Memory data is separated into versioned (git-tracked) and volatile (git-ignored) components:

| Data Type | Examples | Storage Location | Git Status |
|-----------|----------|------------------|------------|
| **Stable** | id, topic, tags, content, created_at, difficulty | Memory files, index.json | Tracked |
| **Volatile** | access_count, accessed_at, last_session, priority | stats.json | Ignored |

**Rationale:**
- Memory files stay clean and merge-friendly (no conflicts on access counts)
- Volatile data updates are fast (small JSON file, not full memory rewrite)
- Each clone/branch starts fresh with volatile data (acceptable tradeoff)
- Priority recalculates from difficulty (in memory) + local session data

### Directory Structure

```
.claude/
├── ltm/                     # Memory data and MCP server source
│   ├── index.json           # VERSIONED: topic, tags, phase (lightweight index)
│   ├── stats.json           # GIT-IGNORED: access_count, priority, accessed_at
│   ├── state.json           # GIT-IGNORED: session counter, config
│   ├── memories/            # VERSIONED: full content, static metadata
│   │   └── mem_abc123.md
│   ├── archives/            # VERSIONED: archived content from eviction
│   │   └── mem_def456.md
│   └── .gitignore           # Ignores stats.json and state.json
├── ltm_hooks/               # Hook scripts (session lifecycle)
│   ├── session_start.py     # SessionStart: load memories into context
│   ├── track_difficulty.py  # PostToolUse: track task difficulty
│   ├── pre_compact.py       # PreCompact: save state before compaction
│   └── session_end.py       # SessionEnd: persist and run eviction
├── commands/                # Slash command definitions
│   ├── remember.md
│   ├── recall.md
│   ├── forget.md
│   └── ltm.md
└── settings.local.json      # Hooks configuration (created by /ltm init)
```

### Stats File Format

Located in `.claude/ltm/stats.json` (git-ignored):

```json
{
  "version": 1,
  "memories": {
    "mem_abc123": {
      "access_count": 3,
      "accessed_at": "2026-01-28T14:20:00Z",
      "last_session": 47,
      "priority": 0.75
    }
  }
}
```

**On fresh clone/checkout:**
- stats.json is empty/missing → priorities based on difficulty only
- First session rebuilds stats from index.json + memory files
- System fully functional, access patterns reset to zero

---

## 8. Data Models

### Memory File Format

Located in `.claude/ltm/memories/{id}.md` (git-tracked):

```yaml
---
id: "mem_abc123"
topic: "Fix database connection timeout"
tags:
  - database
  - debugging
  - postgres
phase: 0
difficulty: 0.8
created_at: "2026-01-15T10:30:00Z"
created_session: 42
---

## Summary
Database connection was timing out after 30 seconds due to pool exhaustion. Fixed by increasing pool size and adding retry logic.

## Content
### Problem
The database connection was timing out after 30 seconds. Investigation revealed the connection pool was being exhausted during batch operations.

### Solution
Increased the connection pool size from 10 to 50 and added exponential backoff retry logic.

### Key Learnings
- Always check connection pool exhaustion first
- The default timeout of 30s is too low for batch operations
```

**Two-part content structure:**

| Section | Purpose | Mutability |
|---------|---------|------------|
| `## Summary` | Human-readable description for manual review | **Constant** - never changes after creation |
| `## Content` | Detailed context for Claude, may be compressed | **Phase-dependent** - reduces or compresses with eviction |

**Note:** Volatile fields (access_count, accessed_at, last_session, priority) are stored in stats.json, not in memory files. This keeps memory files stable and merge-friendly.

**Future Enhancement:** A compression tool may transform the `## Content` section into a model-optimized format that is smaller but not human-readable. The `## Summary` section will always remain readable for manual conflict resolution and browsing.

### Index File Format

Located in `.claude/ltm/index.json` (git-tracked):

```json
{
  "version": 1,
  "memories": {
    "mem_abc123": {
      "topic": "Fix database connection timeout",
      "tags": ["database", "debugging", "postgres"],
      "phase": 0,
      "difficulty": 0.8,
      "created_at": "2026-01-15T10:30:00Z"
    }
  },
  "tag_index": {
    "database": ["mem_abc123"],
    "debugging": ["mem_abc123"],
    "postgres": ["mem_abc123"]
  }
}
```

### State File Format

Located in `.claude/ltm/state.json` (git-ignored):

```json
{
  "version": 1,
  "session_count": 47,
  "current_session": {
    "started_at": "2026-01-28T14:00:00Z",
    "difficulty_score": 0.3,
    "tool_failures": 2,
    "tool_successes": 15
  },
  "last_eviction": "2026-01-20T09:00:00Z",
  "compaction_count": 3,
  "config": {
    "max_memories": 100,
    "memories_to_load": 10,
    "eviction_batch_size": 10
  }
}
```

### Archive File Format

Located in `.claude/ltm/archives/{id}.md` (git-tracked):

Same format as memory files, preserving full content before eviction.

---

## 9. Difficulty Scoring

### Current Implementation: Proxy-Based Scoring

Claude Code hooks do not receive token counts directly. The current implementation uses proxy metrics available from hook payloads:

```python
difficulty = (
    (tool_failure_rate * 0.5) +     # From PostToolUse success/failure
    (tool_count_normalized * 0.3) + # Number of tool invocations
    (compaction_bonus * 0.2)        # +0.2 if PreCompact triggered
)
```

| Metric | Source | Calculation |
|--------|--------|-------------|
| `tool_failure_rate` | PostToolUse hook | `failures / (failures + successes)` |
| `tool_count_normalized` | PostToolUse hook | `min(1.0, tool_count / 50)` |
| `compaction_bonus` | PreCompact hook | `0.2` if PreCompact triggered, else `0` |

### Future Enhancement: Token-Based Scoring

**Status:** Documented for future implementation, not in current scope.

Token data is available through the `transcript_path` JSONL file provided in hook payloads. A future version could parse this transcript to extract token usage:

```python
# Future formula (not yet implemented)
difficulty = (
    (tool_failure_rate * 0.3) +
    (tool_count_normalized * 0.2) +
    (token_usage_normalized * 0.3) +  # From transcript parsing
    (compaction_bonus * 0.2)
)
```

**Implementation approach:**
1. Parse `transcript_path` JSONL on SessionEnd
2. Extract token counts from API response entries
3. Normalize by typical session token usage
4. Factor into difficulty calculation

---

## 10. Future Enhancements

This section documents planned features for future versions.

### FE-1: Memory Compression with LLMlingua

**Status:** Planned

**Problem:** Memories consume context tokens when loaded at session start. Large memories or many memories can significantly reduce available context for the actual task.

**Solution:** Use prompt compression libraries like [LLMlingua](https://www.llmlingua.com/) to reduce token overhead while preserving semantic meaning.

**Implementation approach:**
1. Add optional compression during memory storage or eviction
2. Store both original and compressed versions
3. Load compressed versions at session start to reduce token usage
4. Provide full version on-demand via `get_memory`

**Compression strategies:**
| Strategy | When Applied | Token Reduction |
|----------|--------------|-----------------|
| On storage | When memory is created | Immediate savings |
| On eviction (Phase 1) | When transitioning to Hint phase | Progressive reduction |
| On load | At session start | Dynamic, based on available context |

**Configuration:**
```python
{
  "compression": {
    "enabled": True,
    "library": "llmlingua",  # or "longllmlingua", "llmlingua2"
    "target_ratio": 0.5,     # Target 50% token reduction
    "min_tokens": 100,       # Don't compress memories under 100 tokens
  }
}
```

**Dependencies:** `llmlingua` package (MIT license, open source)

---

### FE-2: Anthropic API Token Counting for Complexity

**Status:** Planned

**Problem:** Current difficulty scoring uses proxy metrics (tool failures, count). Actual token usage would be a more accurate measure of task complexity.

**Solution:** Use the Anthropic API's token counting endpoint to measure tool response sizes and calculate complexity scores.

**Implementation approach:**
1. In PostToolUse hook, count tokens in `tool_response` using Anthropic's `count_tokens` API
2. Accumulate token counts per session
3. On SessionEnd, calculate normalized complexity from total tokens used
4. Factor into difficulty score for memories created during that session

**API usage:**
```python
import anthropic

client = anthropic.Anthropic()

# Count tokens in tool response
token_count = client.count_tokens(
    model="claude-sonnet-4-20250514",
    messages=[{"role": "user", "content": tool_response_text}]
)

# Accumulate per session
session_tokens += token_count.input_tokens
```

**Updated difficulty formula:**
```python
difficulty = (
    (tool_failure_rate * 0.25) +
    (tool_count_normalized * 0.15) +
    (token_usage_normalized * 0.35) +  # From Anthropic API
    (compaction_bonus * 0.25)
)
```

**Configuration:**
```python
{
  "token_counting": {
    "enabled": True,
    "model": "claude-sonnet-4-20250514",  # Model for token counting
    "normalize_cap": 100000,  # Sessions with 100k+ tokens = 1.0 score
  }
}
```

**Dependencies:** `anthropic` package, API key with count_tokens access

**Privacy note:** Tool responses are sent to Anthropic API for counting. Consider implications for sensitive data.

---

### FE-3: Importance Tagging for Priority Boost

**Status:** Planned

**Problem:** All memories are scored equally by the priority algorithm. Users may want to mark certain memories as more important to ensure they're always loaded or never evicted.

**Solution:** Add importance levels that boost the calculated priority score.

**Importance levels:**

| Level | Tag | Priority Boost | Effect |
|-------|-----|----------------|--------|
| Critical | `importance:critical` | +0.5 | Always in top memories, never evicted |
| Important | `importance:important` | +0.25 | Strongly prioritized, evicted last |
| Normal | (default) | +0.0 | Standard priority calculation |
| Low | `importance:low` | -0.25 | Deprioritized, evicted first |

**Updated priority formula:**
```python
base_priority = (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)
importance_boost = get_importance_boost(memory.tags)  # -0.25 to +0.5
priority = clamp(base_priority + importance_boost, 0.0, 1.0)
```

**Usage:**
```bash
# Store a critical memory
/remember Fix for production outage
> Tags: database, critical-fix, importance:critical

# Via MCP tool
store_memory(
    topic="Security vulnerability patch",
    content="...",
    tags=["security", "importance:critical"]
)
```

**Eviction protection:**
- `importance:critical` memories skip eviction entirely
- `importance:important` memories only evict after all normal/low memories are processed

**UI enhancements:**
- `/ltm list` shows importance level in output
- `/ltm list --importance critical` filters by importance

**Implementation notes:**
- Importance is stored as a tag for simplicity (no schema changes)
- Tag prefix `importance:` is reserved for this feature
- Backward compatible: memories without importance tags work as today

---

### FE-4: Archive Search and Recovery

**Status:** Planned

**Problem:** Archived memories (from eviction Phase 3) are preserved but not searchable. Users cannot discover or recover valuable information that was evicted long ago. In extended thinking modes, Claude should be able to dig deeper into historical context.

**Solution:** Add archive search capabilities accessible to users and automatically consulted in ultrathink mode.

**User-facing features:**

| Command | Description |
|---------|-------------|
| `/recall --archives <query>` | Search only archived memories |
| `/recall --all <query>` | Search both active and archived memories |
| `/ltm list --archives` | List all archived memories |
| `/ltm restore <id>` | Restore an archived memory to active status |

**MCP tools:**

```python
@server.tool()
async def search_archives(
    query: str,
    limit: int = 10
) -> list[dict]:
    """Search archived memories by keyword."""

@server.tool()
async def restore_memory(
    memory_id: str,
    importance: str = None  # Optional: set importance on restore
) -> dict:
    """Restore an archived memory to active status (Phase 0)."""
```

**Extended thinking integration:**

When operating in ultrathink mode, Claude should automatically:
1. Search active memories first (existing behavior)
2. If no relevant results, search archives for historical context
3. Consider restoring highly relevant archived memories

**CLAUDE.md addition:**
```markdown
## Extended Thinking Archive Consultation

When in "ultrathink" mode and active memories don't provide sufficient context:
1. Use `mcp__ltm__search_archives` to find relevant historical memories
2. If a highly relevant archived memory is found, consider using `mcp__ltm__restore_memory`
3. Reference archived content in your analysis, noting it's from historical context
```

**Archive index:**

To enable fast archive searching without reading all files:
```
.claude/ltm/
├── archives/
│   ├── mem_abc123.md
│   └── ...
└── archive_index.json  # NEW: lightweight index of archived memories
```

**archive_index.json format:**
```json
{
  "version": 1,
  "memories": {
    "mem_abc123": {
      "topic": "Old debugging solution",
      "tags": ["database", "legacy"],
      "archived_at": "2026-01-15T10:30:00Z",
      "original_phase": 2,
      "reason": "eviction"
    }
  }
}
```

**Implementation notes:**
- Archive index is git-tracked (like regular index.json)
- Restoration resets memory to Phase 0 with fresh stats
- Restored memories get a `restored_from_archive: true` flag
- Users can set importance during restore to prevent re-eviction

---

### FE-5: macOS and Windows Platform Support

**Status:** Planned

**Problem:** The current implementation targets Linux (Fedora) with dependencies on Linux-specific tooling (podman, systemd paths, bash scripts). Developers on macOS and Windows cannot use the LTM system out of the box.

**Solution:** Add cross-platform support for macOS and Windows.

**Platform considerations:**

| Platform | Container Runtime | Path Handling | Shell Scripts |
|----------|-------------------|---------------|---------------|
| Linux | podman (current) | POSIX paths | bash |
| macOS | Docker Desktop or podman | POSIX paths | bash/zsh |
| Windows | Docker Desktop or WSL2 | Windows paths, WSL paths | PowerShell, cmd, or WSL bash |

**Implementation approach:**

1. **Container runtime abstraction:**
   - Detect available runtime (docker, podman)
   - Abstract container commands behind a common interface
   - Support Docker Desktop on macOS/Windows

2. **Path handling:**
   - Use `pathlib` for cross-platform path manipulation
   - Handle Windows drive letters and backslashes
   - Support WSL path translation when needed

3. **Script alternatives:**
   - Provide PowerShell equivalents for Windows-native usage
   - Ensure bash scripts work in Git Bash / WSL
   - Consider Python-based scripts for full portability

4. **Testing matrix:**
   - Linux: Fedora, Ubuntu (podman and docker)
   - macOS: Intel and Apple Silicon (Docker Desktop)
   - Windows: Native Docker Desktop and WSL2

**Migration steps:**
1. Refactor path handling to use `pathlib` throughout
2. Create platform detection module
3. Add Docker support alongside podman
4. Create PowerShell setup script for Windows
5. Update documentation with platform-specific instructions
6. Add CI/CD testing for all platforms

**Configuration:**
```python
{
  "platform": {
    "container_runtime": "auto",  # "auto", "docker", "podman"
    "shell": "auto",              # "auto", "bash", "powershell"
  }
}
```

---

## 11. Technical Debt

### TD-1: Container Auto-Stop Not Implemented

**Status:** Deferred

**Description:** The LTM container starts automatically when Claude Code connects (via `ltm-start.sh` called by MCP). However, the container does not stop automatically when Claude Code exits.

**Current Behavior:**
- **Start**: Automatic - container starts when Claude Code connects
- **Stop**: Manual - user must run `bash .claude/ltm/ltm-stop.sh` from terminal or `/ltm stop` inside Claude Code

**Why Deferred:**
- Adding auto-stop to SessionEnd hook would add startup latency on quick restarts
- Container resource usage when idle is minimal
- Users can manually stop when needed

**Future Implementation Options:**
1. Add container stop to SessionEnd hook (simple but adds restart latency)
2. Implement idle timeout in container (container stops itself after N minutes of inactivity)
3. Add systemd/launchd service for lifecycle management

**Workaround:** Run `bash .claude/ltm/ltm-stop.sh` from terminal when done with Claude Code.

---

## 12. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.4.1 | 2026-02-01 | Added FE-5 (macOS and Windows Platform Support) for cross-platform migration |
| 1.4.0 | 2026-02-01 | Added Future Enhancements section: FE-1 (Memory Compression with LLMlingua), FE-2 (Anthropic API Token Counting), FE-3 (Importance Tagging for Priority Boost), FE-4 (Archive Search and Recovery with ultrathink integration) |
| 1.3.0 | 2026-01-29 | Added persistent container architecture with server mode; HTTP-based hooks via container; `ltm-start.sh` and `ltm-stop.sh` scripts; setup.sh for one-line installation; documented TD-1 (auto-stop not implemented) |
| 1.2.0 | 2026-01-29 | Added `/ltm init` command for automatic hooks configuration; moved hooks to `.claude/ltm_hooks/`; added `ltm_check` and `ltm_fix` MCP tools; added `/ltm help` and `/ltm fix --clean-archives` |
| 1.1.0 | 2026-01-29 | Added FR-9: Slash Commands (user interface) including `/remember`, `/recall`, `/forget`, `/ltm`, `/ltm list`, `/ltm check`, `/ltm fix` |
| 1.0.0 | 2026-01-28 | Initial PRD release |

---

*Document maintained as part of the Long-Term Memory system for Claude Code.*
