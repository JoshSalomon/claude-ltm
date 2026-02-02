# Long-Term Memory (LTM) System - Architecture Document

**Version: 1.3.0 | Last Updated: 2026-02-02**

---

## 1. System Overview

The LTM system enables Claude Code to maintain persistent memory across sessions. Distributed as a Claude Code plugin, it uses a hybrid hooks + MCP server architecture with containerized deployment.

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           Claude Code Session                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐                                                   │
│  │  Hook Scripts    │                                                   │
│  │  (shell + curl)  │                                                   │
│  ├──────────────────┤                                                   │
│  │ session_start.sh │──┐                                                │
│  │ post_tool_use.sh │  │                                                │
│  │ pre_compact.sh   │  │  HTTP POST                                     │
│  │ session_end.sh   │  │  127.0.0.1:PORT                                │
│  └──────────────────┘  │                                                │
│                        │                                                │
└────────────────────────┼────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Container (podman/docker)                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌───────────────────┐    ┌──────────────────────────────────────────┐  │
│  │  Hooks Server     │    │              MCP Server                  │  │
│  │  (Flask/HTTP)     │    │              (stdio)                     │  │
│  ├───────────────────┤    ├──────────────────────────────────────────┤  │
│  │/hook/session_start│    │ store_memory  │ recall    │ list_memories│  │
│  │/hook/post_tool_use│    │ get_memory    │ forget    │ ltm_status   │  │
│  │/hook/pre_compact  │    │ ltm_check     │ ltm_fix   │              │  │
│  │/hook/session_end  │    └───────────────┴───────────┴──────────────┘  │
│  └───────────────────┘                      │                           │
│         │                                   │                           │
│         └───────────────┬───────────────────┘                           │
│                         ▼                                               │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                      Storage Layer                               │   │
│  ├──────────────────┬────────────────────┬──────────────────────────┤   │
│  │    store.py      │    priority.py     │       eviction.py        │   │
│  │   (CRUD ops)     │   (scoring)        │   (phase transitions)    │   │
│  └──────────────────┴────────────────────┴──────────────────────────┘   │
│                         │                                               │
└─────────────────────────┼───────────────────────────────────────────────┘
                          │ (volume mount)
                          ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          File System (host)                             │
├─────────────────────────────────────────────────────────────────────────┤
│  .claude/ltm/                                                           │
│  ├── index.json       (git-tracked)   Lightweight lookup index          │
│  ├── stats.json       (git-ignored)   Volatile access statistics        │
│  ├── state.json       (git-ignored)   Session state and config          │
│  ├── server.json      (git-ignored)   Container connection info         │
│  ├── memories/        (git-tracked)   Memory files (markdown + YAML)    │
│  └── archives/        (git-tracked)   Archived content from eviction    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Responsibilities

| Component         | Responsibility                                                        |
|-------------|-----------------------------------------------------------------------|
| **Hooks**         | Automatic operations during session lifecycle (no user action needed) |
| **MCP Server**    | On-demand memory operations via tool calls                            |
| **Storage Layer** | Core business logic for memory CRUD, priority, and eviction           |
| **File System**   | Persistent storage with git-friendly format                           |

### 1.3 Data Flow Summary

| Flow       | Trigger       | Path                                              |
|------------|---------------|---------------------------------------------------|
| **Load**   | Session start | Hook → store.py → index.json + memories/ → stdout |
| **Store**  | User command  | MCP tool → store.py → memories/ + index.json      |
| **Recall** | User query    | MCP tool → store.py → search → memories/ → response |
| **Evict**  | Session end   | Hook → eviction.py → memories/ → archives/        |

---

## 2. Component Design

### 2.1 Storage Layer

#### store.py - Core Storage Operations

```python
# .claude/ltm/store.py

class MemoryStore:
    """Core storage operations for memories."""

    def __init__(self, base_path: str = ".claude/ltm"):
        self.base_path = Path(base_path)
        self.memories_path = self.base_path / "memories"
        self.archives_path = self.base_path / "archives"
        self.index_path = self.base_path / "index.json"
        self.stats_path = self.base_path / "stats.json"

    # CRUD Operations
    def create(self, topic: str, content: str,
               tags: list[str] = None, difficulty: float = 0.5) -> str:
        """Create new memory, return ID."""

    def read(self, memory_id: str) -> dict:
        """Read memory by ID, update access stats."""

    def update(self, memory_id: str, **fields) -> bool:
        """Update memory fields."""

    def delete(self, memory_id: str, archive: bool = True) -> bool:
        """Delete memory, optionally archive first."""

    def list(self, phase: int = None, tag: str = None,
             keyword: str = None, limit: int = 50) -> list[dict]:
        """List memories with optional filtering."""

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search memories by keyword in topic/content."""

    # Internal helpers
    def _generate_id(self) -> str:
        """Generate unique memory ID (mem_<hash>)."""

    def _read_index(self) -> dict:
        """Load index.json with caching."""

    def _write_index(self, data: dict) -> None:
        """Atomic write to index.json."""

    def _read_stats(self) -> dict:
        """Load stats.json, create if missing."""

    def _write_stats(self, data: dict) -> None:
        """Atomic write to stats.json."""

    def _parse_memory_file(self, path: Path) -> dict:
        """Parse markdown file with YAML frontmatter."""

    def _write_memory_file(self, memory_id: str, data: dict) -> None:
        """Write memory as markdown with YAML frontmatter."""
```

**Key Design Decisions:**

- **Atomic writes**: All file writes use temp file + rename pattern
- **Index caching**: Index loaded once per operation batch
- **Stats separation**: Volatile data in stats.json, not in memory files

#### priority.py - Priority Scoring

```python
# .claude/ltm/priority.py

class PriorityCalculator:
    """Calculate memory priority scores."""

    DIFFICULTY_WEIGHT = 0.4
    RECENCY_WEIGHT = 0.3
    FREQUENCY_WEIGHT = 0.3
    FREQUENCY_CAP = 10  # Max accesses for normalization

    def calculate(self, memory: dict, stats: dict,
                  current_session: int) -> float:
        """
        Calculate priority score for a memory.

        priority = (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)
        """
        difficulty = memory.get("difficulty", 0.5)
        recency = self._calculate_recency(stats, current_session)
        frequency = self._calculate_frequency(stats)

        return (
            difficulty * self.DIFFICULTY_WEIGHT +
            recency * self.RECENCY_WEIGHT +
            frequency * self.FREQUENCY_WEIGHT
        )

    def _calculate_recency(self, stats: dict, current_session: int) -> float:
        """
        Recency decays based on sessions since last access.
        Formula: 1 / (1 + sessions_since_access)
        """
        last_session = stats.get("last_session", 0)
        sessions_since = current_session - last_session
        return 1.0 / (1.0 + sessions_since)

    def _calculate_frequency(self, stats: dict) -> float:
        """
        Frequency normalized by FREQUENCY_CAP.
        Formula: min(1.0, access_count / FREQUENCY_CAP)
        """
        access_count = stats.get("access_count", 0)
        return min(1.0, access_count / self.FREQUENCY_CAP)

    def calculate_difficulty(self, tool_failures: int,
                            tool_successes: int,
                            compacted: bool) -> float:
        """
        Calculate difficulty from session metrics.

        difficulty = (failure_rate * 0.5) + (tool_count_norm * 0.3) + (compaction * 0.2)
        """
        total = tool_failures + tool_successes
        if total == 0:
            failure_rate = 0.0
            tool_count_norm = 0.0
        else:
            failure_rate = tool_failures / total
            tool_count_norm = min(1.0, total / 50)  # Normalize by 50 tools

        compaction_bonus = 0.2 if compacted else 0.0

        return (
            failure_rate * 0.5 +
            tool_count_norm * 0.3 +
            compaction_bonus * 0.2
        )
```

#### eviction.py - Phased Eviction

```python
# .claude/ltm/eviction.py

class EvictionManager:
    """Manage memory eviction through phases."""

    PHASES = {
        0: "full",      # Complete content
        1: "hint",      # Summary + key points
        2: "abstract",  # One-line summary
        3: "removed"    # Archived only
    }

    def __init__(self, store: MemoryStore):
        self.store = store

    def run_eviction(self, threshold: int = 100,
                     batch_size: int = 10) -> list[str]:
        """
        Run eviction if memory count exceeds threshold.
        Returns list of evicted memory IDs.
        """
        memories = self.store.list()
        if len(memories) <= threshold:
            return []

        # Sort by priority (lowest first)
        sorted_memories = sorted(memories, key=lambda m: m.get("priority", 0))

        evicted = []
        for memory in sorted_memories[:batch_size]:
            self.advance_phase(memory["id"])
            evicted.append(memory["id"])

        return evicted

    def advance_phase(self, memory_id: str) -> int:
        """
        Advance memory to next eviction phase.
        Returns new phase number.
        """
        memory = self.store.read(memory_id)
        current_phase = memory.get("phase", 0)

        if current_phase >= 3:
            return current_phase  # Already removed

        new_phase = current_phase + 1

        if current_phase == 0:
            # Phase 0 → 1: Archive full content, reduce to hint
            self._archive(memory_id, memory)
            reduced_content = self._reduce_to_hint(memory["content"])
            self.store.update(memory_id, phase=1, content=reduced_content)

        elif current_phase == 1:
            # Phase 1 → 2: Reduce to abstract
            abstract_content = self._reduce_to_abstract(memory["content"])
            self.store.update(memory_id, phase=2, content=abstract_content)

        elif current_phase == 2:
            # Phase 2 → 3: Remove from active storage
            self.store.delete(memory_id, archive=False)  # Already archived

        return new_phase

    def _archive(self, memory_id: str, memory: dict) -> None:
        """Archive full memory content before reduction."""
        archive_path = self.store.archives_path / f"{memory_id}.md"
        if not archive_path.exists():
            self.store._write_memory_file(archive_path, memory)

    def _reduce_to_hint(self, content: str) -> str:
        """Extract first paragraph and key points."""
        # Preserve ## Summary, reduce ## Content
        lines = content.split("\n")
        # ... reduction logic

    def _reduce_to_abstract(self, content: str) -> str:
        """Extract one-line summary only."""
        # Keep only first sentence of ## Summary
        # ... reduction logic
```

### 2.2 MCP Server

```python
# .claude/ltm/mcp_server.py

from mcp import Server, Tool
from store import MemoryStore
from priority import PriorityCalculator

server = Server("ltm")
store = MemoryStore()
priority_calc = PriorityCalculator()

@server.tool()
async def store_memory(
    topic: str,
    content: str,
    tags: list[str] = None,
    auto_tag: bool = False,
    difficulty: float = 0.5
) -> dict:
    """Store a new memory."""
    if auto_tag and not tags:
        tags = _extract_tags(topic, content)

    memory_id = store.create(topic, content, tags, difficulty)
    return {"success": True, "id": memory_id}

@server.tool()
async def recall(query: str, limit: int = 10) -> dict:
    """Search memories by query."""
    results = store.search(query, limit)
    return {"memories": results, "total": len(results)}

@server.tool()
async def list_memories(
    phase: int = None,
    tag: str = None,
    keyword: str = None,
    limit: int = 50,
    offset: int = 0
) -> dict:
    """List memories with optional filtering."""
    results = store.list(phase=phase, tag=tag, keyword=keyword, limit=limit)
    return {
        "memories": results[offset:offset+limit],
        "total": len(results),
        "has_more": len(results) > offset + limit
    }

@server.tool()
async def get_memory(memory_id: str) -> dict:
    """Get full memory content by ID."""
    return store.read(memory_id)

@server.tool()
async def forget(memory_id: str) -> dict:
    """Delete a memory (archives first)."""
    success = store.delete(memory_id, archive=True)
    return {"success": success, "archived": True}

@server.tool()
async def ltm_status() -> dict:
    """Get system status and statistics."""
    memories = store.list()
    by_phase = {0: 0, 1: 0, 2: 0}
    for m in memories:
        phase = m.get("phase", 0)
        if phase in by_phase:
            by_phase[phase] += 1

    state = store._read_state()
    return {
        "total_memories": len(memories),
        "by_phase": by_phase,
        "session_count": state.get("session_count", 0),
        "storage_path": str(store.base_path)
    }

def _extract_tags(topic: str, content: str) -> list[str]:
    """Auto-extract tags from topic and content."""
    # Extract technology names, file extensions, etc.
    # ... tag extraction logic
    pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(server.run())
```

**Plugin Distribution:**

The MCP server is distributed as part of the Claude Code plugin and runs in an ephemeral container:

```bash
# Installation from GitHub
claude plugin marketplace add https://github.com/JoshSalomon/claude-ltm.git
claude plugin install ltm@claude-ltm

# The plugin configures MCP automatically via .mcp.json
```

### 2.3 Hooks

Hooks are defined in `hooks/hooks.json` and auto-loaded by the plugin system. The hooks use a **shell script + HTTP** architecture where shell scripts invoke HTTP endpoints on the running container.

#### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Claude Code                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Hook Event (e.g., SessionStart)                                    │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────┐                                            │
│  │  hooks/hooks.json   │  Defines which shell script to run        │
│  └──────────┬──────────┘                                            │
│             │                                                       │
│             ▼                                                       │
│  ┌─────────────────────┐     HTTP POST      ┌────────────────────┐ │
│  │  session_start.sh   │ ─────────────────> │    Container       │ │
│  │  (shell script)     │   127.0.0.1:PORT   │  (hooks endpoint)  │ │
│  └─────────────────────┘                    └────────────────────┘ │
│                                                      │              │
│                                                      ▼              │
│                                             ┌────────────────────┐ │
│                                             │  Python handlers   │ │
│                                             │  (store.py, etc.)  │ │
│                                             └────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

**Why HTTP instead of direct Python execution:**
- Container isolation: All Python code runs inside the container
- No local Python dependencies required
- Hooks can execute quickly (shell + curl)
- Container handles state management and file access

#### hooks/hooks.json

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/session_start.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/post_tool_use.sh"
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/pre_compact.sh"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/session_end.sh"
          }
        ]
      }
    ]
  }
}
```

#### session_start.sh

```bash
#!/bin/bash
# LTM Session Start Hook
# Loads memories at the start of a Claude Code session

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SERVER_JSON="${PROJECT_ROOT}/.claude/ltm/server.json"

# Check if server.json exists (container is running)
if [[ ! -f "$SERVER_JSON" ]]; then
    # No server running, silently exit
    exit 0
fi

# Read the hooks port from server.json
PORT=$(jq -r '.hooks_port // empty' "$SERVER_JSON" 2>/dev/null)

if [[ -z "$PORT" ]]; then
    exit 0
fi

# Call the session start endpoint on the container
# Use 127.0.0.1 explicitly (not localhost) to avoid IPv6 issues
curl -s -X POST "http://127.0.0.1:${PORT}/hook/session_start" \
    -H 'Content-Type: application/json' \
    -d '{}' 2>/dev/null || true
```

#### post_tool_use.sh

```bash
#!/bin/bash
# LTM PostToolUse Hook
# Tracks tool success/failure for difficulty scoring

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SERVER_JSON="${PROJECT_ROOT}/.claude/ltm/server.json"

if [[ ! -f "$SERVER_JSON" ]]; then
    exit 0
fi

PORT=$(jq -r '.hooks_port // empty' "$SERVER_JSON" 2>/dev/null)

if [[ -z "$PORT" ]]; then
    exit 0
fi

# Read payload from stdin (Claude Code provides tool info)
PAYLOAD=$(cat)

# Forward to container's hook endpoint
curl -s -X POST "http://127.0.0.1:${PORT}/hook/post_tool_use" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD" 2>/dev/null || true
```

#### pre_compact.sh

```bash
#!/bin/bash
# LTM PreCompact Hook
# Saves state before context compaction

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SERVER_JSON="${PROJECT_ROOT}/.claude/ltm/server.json"

if [[ ! -f "$SERVER_JSON" ]]; then
    exit 0
fi

PORT=$(jq -r '.hooks_port // empty' "$SERVER_JSON" 2>/dev/null)

if [[ -z "$PORT" ]]; then
    exit 0
fi

curl -s -X POST "http://127.0.0.1:${PORT}/hook/pre_compact" \
    -H 'Content-Type: application/json' \
    -d '{}' 2>/dev/null || true
```

#### session_end.sh

```bash
#!/bin/bash
# LTM Session End Hook
# Persists state and runs eviction

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SERVER_JSON="${PROJECT_ROOT}/.claude/ltm/server.json"

if [[ ! -f "$SERVER_JSON" ]]; then
    exit 0
fi

PORT=$(jq -r '.hooks_port // empty' "$SERVER_JSON" 2>/dev/null)

if [[ -z "$PORT" ]]; then
    exit 0
fi

curl -s -X POST "http://127.0.0.1:${PORT}/hook/session_end" \
    -H 'Content-Type: application/json' \
    -d '{}' 2>/dev/null || true
```

#### Container-Side Hook Handlers

The container exposes HTTP endpoints for each hook. The handlers run Python code inside the container:

```python
# Inside container: server/hooks_server.py

from flask import Flask, request, jsonify
from store import MemoryStore
from priority import PriorityCalculator
from eviction import EvictionManager

app = Flask(__name__)
store = MemoryStore()

@app.route('/hook/session_start', methods=['POST'])
def session_start():
    """Load top memories and increment session counter."""
    state = store._read_state()
    state["session_count"] = state.get("session_count", 0) + 1
    state["current_session"] = {
        "started_at": datetime.now().isoformat(),
        "tool_failures": 0,
        "tool_successes": 0,
        "compacted": False
    }
    store._write_state(state)

    # Get top memories by priority
    config = state.get("config", {})
    limit = config.get("memories_to_load", 10)
    memories = store.list(limit=limit)

    return jsonify({"memories": memories})

@app.route('/hook/post_tool_use', methods=['POST'])
def post_tool_use():
    """Track tool success/failure for difficulty scoring."""
    payload = request.get_json() or {}
    tool_response = payload.get("tool_response", {})

    state = store._read_state()
    session = state.get("current_session", {})

    is_success = not ("error" in str(tool_response) or
                      tool_response.get("success") == False)

    if is_success:
        session["tool_successes"] = session.get("tool_successes", 0) + 1
    else:
        session["tool_failures"] = session.get("tool_failures", 0) + 1

    state["current_session"] = session
    store._write_state(state)

    return jsonify({"success": True})

@app.route('/hook/pre_compact', methods=['POST'])
def pre_compact():
    """Mark compaction occurred (adds difficulty bonus)."""
    state = store._read_state()
    session = state.get("current_session", {})
    session["compacted"] = True
    state["current_session"] = session
    state["compaction_count"] = state.get("compaction_count", 0) + 1
    store._write_state(state)

    return jsonify({"success": True})

@app.route('/hook/session_end', methods=['POST'])
def session_end():
    """Persist state and run eviction if needed."""
    priority_calc = PriorityCalculator()
    eviction_mgr = EvictionManager(store)

    state = store._read_state()
    current_session_num = state.get("session_count", 1)

    # Update priorities for accessed memories
    stats = store._read_stats()
    for mem_id, mem_stats in stats.get("memories", {}).items():
        if mem_stats.get("last_session") == current_session_num:
            memory = store.read(mem_id)
            priority = priority_calc.calculate(memory, mem_stats, current_session_num)
            mem_stats["priority"] = priority

    store._write_stats(stats)

    # Run eviction if needed
    config = state.get("config", {})
    threshold = config.get("max_memories", 100)
    eviction_mgr.run_eviction(threshold=threshold)

    # Reset current session state
    state["current_session"] = {}
    store._write_state(state)

    return jsonify({"success": True})
```

#### server.json

The container writes connection info to `.claude/ltm/server.json` on startup:

```json
{
  "container_id": "ltm-server-abc123",
  "mcp_port": 8080,
  "hooks_port": 8081,
  "started_at": "2026-02-02T10:30:00Z"
}
```

This allows hook scripts to discover the correct port for HTTP calls.

### 2.4 Data Files

#### index.json Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "version": {"type": "integer"},
    "memories": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "topic": {"type": "string"},
          "tags": {"type": "array", "items": {"type": "string"}},
          "phase": {"type": "integer", "minimum": 0, "maximum": 3},
          "difficulty": {"type": "number", "minimum": 0, "maximum": 1},
          "created_at": {"type": "string", "format": "date-time"}
        },
        "required": ["topic", "phase", "created_at"]
      }
    },
    "tag_index": {
      "type": "object",
      "additionalProperties": {
        "type": "array",
        "items": {"type": "string"}
      }
    }
  },
  "required": ["version", "memories"]
}
```

#### stats.json Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "version": {"type": "integer"},
    "memories": {
      "type": "object",
      "additionalProperties": {
        "type": "object",
        "properties": {
          "access_count": {"type": "integer", "minimum": 0},
          "accessed_at": {"type": "string", "format": "date-time"},
          "last_session": {"type": "integer"},
          "priority": {"type": "number", "minimum": 0, "maximum": 1}
        }
      }
    }
  },
  "required": ["version", "memories"]
}
```

#### state.json Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "version": {"type": "integer"},
    "session_count": {"type": "integer", "minimum": 0},
    "current_session": {
      "type": "object",
      "properties": {
        "started_at": {"type": "string", "format": "date-time"},
        "tool_failures": {"type": "integer"},
        "tool_successes": {"type": "integer"},
        "compacted": {"type": "boolean"}
      }
    },
    "last_eviction": {"type": "string", "format": "date-time"},
    "compaction_count": {"type": "integer"},
    "config": {
      "type": "object",
      "properties": {
        "max_memories": {"type": "integer"},
        "memories_to_load": {"type": "integer"},
        "eviction_batch_size": {"type": "integer"}
      }
    }
  },
  "required": ["version", "session_count"]
}
```

---

## 3. Sequence Diagrams

### 3.1 Session Start Flow

```
┌───────────┐     ┌─────────────────┐     ┌──────────┐     ┌─────────┐
│Claude Code│     │session_start.py │     │ store.py │     │  Files  │
└─────┬─────┘     └────────┬────────┘     └────┬─────┘     └────┬────┘
      │                    │                   │                │
      │  SessionStart      │                   │                │
      │  hook trigger      │                   │                │
      │───────────────────>│                   │                │
      │  {session_id}      │                   │                │
      │                    │                   │                │
      │                    │ _read_state()     │                │
      │                    │──────────────────>│                │
      │                    │                   │ read           │
      │                    │                   │───────────────>│
      │                    │                   │<───────────────│
      │                    │<──────────────────│ state.json     │
      │                    │                   │                │
      │                    │ increment         │                │
      │                    │ session_count     │                │
      │                    │                   │                │
      │                    │ _write_state()    │                │
      │                    │──────────────────>│                │
      │                    │                   │ atomic write   │
      │                    │                   │───────────────>│
      │                    │                   │                │
      │                    │ list(limit=10)    │                │
      │                    │──────────────────>│                │
      │                    │                   │ read           │
      │                    │                   │───────────────>│
      │                    │                   │<───────────────│
      │                    │<──────────────────│ index.json     │
      │                    │ top 10 memories   │                │
      │                    │                   │                │
      │<───────────────────│                   │                │
      │ stdout: memories   │                   │                │
      │ for context        │                   │                │
      │                    │                   │                │
```

### 3.2 Memory Storage Flow

```
┌───────────┐     ┌───────────┐     ┌──────────┐     ┌─────────┐
│   User    │     │MCP Server │     │ store.py │     │  Files  │
└─────┬─────┘     └─────┬─────┘     └────┬─────┘     └────┬────┘
      │                 │                │                │
      │"Remember this"  │                │                │
      │────────────────>│                │                │
      │                 │                │                │
      │                 │ store_memory   │                │
      │                 │ (topic,content,│                │
      │                 │  tags)         │                │
      │                 │───────────────>│                │
      │                 │                │                │
      │                 │                │ _generate_id()  │
      │                 │                │ mem_<hash>      │
      │                 │                │                │
      │                 │                │ write memory   │
      │                 │                │───────────────>│
      │                 │                │                │ memories/
      │                 │                │                │ mem_xxx.md
      │                 │                │                │
      │                 │                │ update index   │
      │                 │                │───────────────>│
      │                 │                │                │ index.json
      │                 │                │                │
      │                 │                │ init stats     │
      │                 │                │───────────────>│
      │                 │                │                │ stats.json
      │                 │                │                │
      │                 │<───────────────│                │
      │                 │ {id, success}  │                │
      │                 │                │                │
      │<────────────────│                │                │
      │"Stored memory   │                │                │
      │ mem_xxx"        │                │                │
      │                 │                │                │
```

### 3.3 Eviction Flow

```
┌─────────────────┐     ┌────────────┐     ┌──────────┐     ┌─────────┐
│session_end.py   │     │eviction.py │     │ store.py │     │  Files  │
└────────┬────────┘     └──────┬─────┘     └────┬─────┘     └────┬────┘
         │                     │                │                │
         │ run_eviction        │                │                │
         │ (threshold=100)     │                │                │
         │────────────────────>│                │                │
         │                     │                │                │
         │                     │ list()         │                │
         │                     │───────────────>│                │
         │                     │                │ read           │
         │                     │                │───────────────>│
         │                     │<───────────────│<───────────────│
         │                     │ 150 memories   │                │
         │                     │                │                │
         │                     │ sort by        │                │
         │                     │ priority (asc) │                │
         │                     │                │                │
         │                     │ for lowest 10: │                │
         │                     │                │                │
         │                     │ advance_phase  │                │
         │                     │ (phase 0→1)    │                │
         │                     │                │                │
         │                     │ _archive()     │                │
         │                     │───────────────>│                │
         │                     │                │ copy           │
         │                     │                │───────────────>│
         │                     │                │                │ archives/
         │                     │                │                │ mem_xxx.md
         │                     │                │                │
         │                     │ _reduce_to_hint│                │
         │                     │                │                │
         │                     │ update()       │                │
         │                     │───────────────>│                │
         │                     │                │ write          │
         │                     │                │───────────────>│
         │                     │                │                │ memories/
         │                     │                │                │ (reduced)
         │                     │                │                │
         │<────────────────────│                │                │
         │ [evicted IDs]       │                │                │
         │                     │                │                │
```

### 3.4 Difficulty Tracking Flow

```
┌───────────┐     ┌──────────────────┐     ┌──────────┐     ┌─────────┐
│Claude Code│     │track_difficulty.py│     │ store.py │     │  Files  │
└─────┬─────┘     └────────┬─────────┘     └────┬─────┘     └────┬────┘
      │                    │                   │                │
      │  PostToolUse       │                   │                │
      │  {tool_name,       │                   │                │
      │   tool_response}   │                   │                │
      │───────────────────>│                   │                │
      │                    │                   │                │
      │                    │ _read_state()     │                │
      │                    │──────────────────>│                │
      │                    │                   │ read           │
      │                    │                   │───────────────>│
      │                    │<──────────────────│<───────────────│
      │                    │ state             │                │
      │                    │                   │                │
      │                    │ check response    │                │
      │                    │ for error         │                │
      │                    │                   │                │
      │                    │ if error:         │                │
      │                    │   tool_failures++ │                │
      │                    │ else:             │                │
      │                    │   tool_successes++│                │
      │                    │                   │                │
      │                    │ _write_state()    │                │
      │                    │──────────────────>│                │
      │                    │                   │ write          │
      │                    │                   │───────────────>│
      │                    │                   │                │ state.json
      │                    │                   │                │
      │<───────────────────│                   │                │
      │                    │                   │                │
```

---

## 4. Data Flow

### 4.1 Read Path

```
Request
   │
   ▼
┌───────────────────┐
│    index.json     │  Fast lookup by ID, tag, keyword
│  (lightweight)    │  No content, just metadata
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│  memories/*.md    │  Full content for matched IDs
│  (on-demand)      │  Only loaded when needed
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│   stats.json      │  Access counts, priority
│  (volatile)       │  Updated on every access
└─────────┬─────────┘
          │
          ▼
     Response
```

### 4.2 Write Path

```
Store Request
   │
   ▼
┌───────────────────┐
│   Generate ID     │  mem_<8-char-hash>
│   (uuid + hash)   │
└─────────┬─────────┘
          │
          ├─────────────────────────────────────┐
          ▼                                     ▼
┌───────────────────┐              ┌───────────────────┐
│ memories/{id}.md  │              │    index.json     │
│ (YAML + markdown) │              │ (add entry)       │
└─────────┬─────────┘              └─────────┬─────────┘
          │                                  │
          └──────────────┬───────────────────┘
                         ▼
              ┌───────────────────┐
              │   stats.json      │
              │ (init entry)      │
              └───────────────────┘
```

### 4.3 Eviction Path

```
Eviction Trigger
   │
   ▼
┌───────────────────┐
│   index.json      │  List all memories
│   + stats.json    │  Sort by priority
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Lowest priority   │  Select batch for eviction
│ memories          │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Phase 0 → 1       │  Archive to archives/{id}.md
│ (archive)         │  Reduce content in memories/{id}.md
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Phase 1 → 2       │  Further reduce content
│ (reduce)          │
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Phase 2 → 3       │  Remove from memories/
│ (remove)          │  Keep in archives/
└─────────┬─────────┘
          │
          ▼
┌───────────────────┐
│ Update index.json │  Remove entry
│ Update stats.json │  Remove entry
└───────────────────┘
```

---

## 5. Design Patterns

### 5.1 Atomic File Writes

All file writes use the temp file + rename pattern to prevent corruption:

```python
import tempfile
import os

def atomic_write(path: Path, content: str) -> None:
    """Write content atomically using temp file + rename."""
    # Create temp file in same directory (same filesystem)
    dir_path = path.parent
    fd, temp_path = tempfile.mkstemp(dir=dir_path)

    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)

        # Atomic rename (POSIX guarantee)
        os.rename(temp_path, path)
    except:
        # Clean up temp file on error
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise
```

### 5.2 Separation of Volatile/Stable Data

| Data Type | Storage | Git Status | Update Frequency |
|-----------|---------|------------|------------------|
| Content | Memory files | Tracked | Rarely |
| Metadata | index.json | Tracked | On create/update |
| Access stats | stats.json | Ignored | Every access |
| Session state | state.json | Ignored | Every session |

This separation:
- Prevents git conflicts on volatile data
- Reduces I/O by not rewriting large files for small updates
- Allows fresh clone to work immediately

### 5.3 Priority Calculation Algorithm

```python
priority = (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)
```

**Factor calculations:**

| Factor | Formula | Range | Description |
|--------|---------|-------|-------------|
| difficulty | From session metrics | 0.0-1.0 | Higher = harder task |
| recency | `1 / (1 + sessions_since)` | 0.0-1.0 | Decay curve |
| frequency | `min(1.0, accesses / 10)` | 0.0-1.0 | Capped at 10 |

### 5.4 Phase-Based Content Reduction

| Phase | Content State | Reduction Logic |
|-------|---------------|-----------------|
| 0 | Full | `## Summary` + `## Content` (complete) |
| 1 | Hint | `## Summary` + `## Content` (first paragraph only) |
| 2 | Abstract | `## Summary` (first sentence only) |
| 3 | Removed | Archived only, removed from active storage |

The `## Summary` section is **never modified** to preserve human-readable context for git merges.

---

## 6. Extension Points

### 6.1 Adding New MCP Tools

1. Define tool function in `mcp_server.py`:
   ```python
   @server.tool()
   async def new_tool(param: str) -> dict:
       """Tool description."""
       # Implementation
       return {"result": ...}
   ```

2. Tool is automatically registered with MCP server

### 6.2 Custom Eviction Strategies

Subclass `EvictionManager`:

```python
class CustomEvictionManager(EvictionManager):
    def run_eviction(self, threshold: int, batch_size: int) -> list[str]:
        # Custom eviction logic
        pass

    def _reduce_to_hint(self, content: str) -> str:
        # Custom hint generation
        pass
```

### 6.3 Alternative Storage Backends

Replace `MemoryStore` with interface-compatible implementation:

```python
class AbstractStore(Protocol):
    def create(self, topic: str, content: str,
               tags: list[str], difficulty: float) -> str: ...
    def read(self, memory_id: str) -> dict: ...
    def update(self, memory_id: str, **fields) -> bool: ...
    def delete(self, memory_id: str, archive: bool) -> bool: ...
    def list(self, **filters) -> list[dict]: ...
    def search(self, query: str, limit: int) -> list[dict]: ...
```

Possible backends:
- SQLite (faster queries at scale)
- Redis (distributed access)
- S3-compatible (cloud storage)

### 6.4 Adding New Hooks

Hooks use a two-part architecture: shell scripts (host) + HTTP endpoints (container).

**Step 1: Add hook definition to `hooks/hooks.json`:**
```json
{
  "hooks": {
    "NewEvent": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/new_event.sh"
          }
        ]
      }
    ]
  }
}
```

**Step 2: Create shell script in `hooks/`:**
```bash
#!/bin/bash
# hooks/new_event.sh

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SERVER_JSON="${PROJECT_ROOT}/.claude/ltm/server.json"

if [[ ! -f "$SERVER_JSON" ]]; then
    exit 0
fi

PORT=$(jq -r '.hooks_port // empty' "$SERVER_JSON" 2>/dev/null)

if [[ -z "$PORT" ]]; then
    exit 0
fi

# Read payload from stdin if needed
PAYLOAD=$(cat)

# Call the container's hook endpoint
curl -s -X POST "http://127.0.0.1:${PORT}/hook/new_event" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD" 2>/dev/null || true
```

**Step 3: Add HTTP endpoint in container (`server/hooks_server.py`):**
```python
@app.route('/hook/new_event', methods=['POST'])
def new_event():
    """Handle new event hook."""
    payload = request.get_json() or {}
    # Process the hook...
    return jsonify({"success": True})
```

**Step 4: Rebuild container:**
```bash
podman build -t ltm-mcp-server .
```

#### Hook Payload Reference

Claude Code provides different payloads for each hook type:

| Hook | Payload Fields |
|------|----------------|
| `SessionStart` | `session_id`, `cwd`, `timestamp` |
| `PostToolUse` | `tool_name`, `tool_input`, `tool_response`, `tool_use_id` |
| `PreCompact` | `session_id`, `timestamp` |
| `SessionEnd` | `session_id`, `transcript_path`, `timestamp` |

#### Important Notes

- **Timeout**: All hooks must complete within 5 seconds (Claude Code timeout).
- **Auto-loading**: Hooks from `hooks/hooks.json` are automatically loaded by the plugin system; no manual registration needed.
- **Container dependency**: Hooks silently exit if the container isn't running (no error to user).
- **IPv6**: Use `127.0.0.1` explicitly, not `localhost`, to avoid IPv6 resolution issues on some systems.

---

## 7. Constraints & Trade-offs

### 7.1 Why File-Based Over SQLite

| Factor | File-Based | SQLite |
|--------|------------|--------|
| Git compatibility | Excellent (diff, merge) | Poor (binary) |
| Human readability | Direct editing possible | Requires tools |
| Simplicity | No database setup | Requires driver |
| Concurrent access | File locking | Built-in |
| Query performance | O(n) scan | Indexed queries |

**Decision:** File-based for git-friendliness and human readability. Performance is acceptable for expected scale (< 1000 memories).

### 7.2 Why Git-Ignored Volatile Data

| Approach | Pros | Cons |
|----------|------|------|
| All in memory files | Single source of truth | Git conflicts on access counts |
| Volatile in stats.json | No conflicts, fast updates | Two files to sync |

**Decision:** Separate stats.json (git-ignored) to prevent conflicts on volatile data. Priority can be recalculated from difficulty + local session data.

### 7.3 Why Session-Based Recency Over Time-Based

| Approach | Pros | Cons |
|----------|------|------|
| Time-based | Reflects real time | Penalizes project pauses |
| Session-based | Fair during pauses | Requires session tracking |

**Decision:** Session-based recency. A memory accessed "2 sessions ago" maintains relevance regardless of calendar time between sessions.

### 7.4 Hook Timeout Implications

Claude Code enforces a 5-second timeout on hooks. This constrains:

- **SessionStart**: Must load and output memories quickly
- **PostToolUse**: Must update state quickly (no expensive operations)
- **SessionEnd**: Eviction must be batched, not exhaustive

**Mitigation:**
- Index for fast lookups (avoid scanning all files)
- Batch eviction (10 memories per session, not all at once)
- Async processing where possible

---

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.3.0 | 2026-02-02 | Rewrote section 2.3 (Hooks) to document shell script + HTTP architecture; updated section 1.1 diagram to show container boundary; updated section 6.4 with new hook creation process |
| 1.2.0 | 2026-02-02 | Updated for plugin-based distribution; hooks now auto-loaded from `hooks/hooks.json`; MCP server runs via stdio in ephemeral container |
| 1.1.0 | 2026-02-01 | Updated "Adding New Hooks" section with container mode (HTTP) and development mode (Python scripts); added hook payload reference; documented IPv6/localhost issue |
| 1.0.0 | 2026-01-28 | Initial architecture document |

---

*Document maintained as part of the Long-Term Memory system for Claude Code.*
