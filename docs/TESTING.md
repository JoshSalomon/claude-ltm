# Long-Term Memory (LTM) System - Testing Strategy

**Version: 1.0.0 | Last Updated: 2026-01-28**

---

## 1. Overview

This document defines the testing strategy for the LTM system, following Test-Driven Development (TDD) principles. Tests are organized into three levels: unit tests, integration tests, and end-to-end tests.

### Test Framework

- **Framework**: pytest
- **Location**: `.claude/ltm/tests/`
- **Naming Convention**: `test_<module>.py`

### Directory Structure

```
.claude/ltm/
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Shared fixtures
│   ├── test_store.py            # Unit tests for store.py
│   ├── test_priority.py         # Unit tests for priority.py
│   ├── test_eviction.py         # Unit tests for eviction.py
│   ├── test_mcp_server.py       # Integration tests for MCP server
│   ├── test_hooks.py            # Integration tests for hooks
│   ├── test_container.py        # Containerized deployment tests
│   ├── test_e2e.py              # End-to-end tests
│   ├── fixtures/
│   │   ├── memories/            # Sample memory files
│   │   ├── index.json           # Sample index
│   │   ├── stats.json           # Sample stats
│   │   └── state.json           # Sample state
│   └── scripts/
│       └── test_container_parity.sh  # Container parity test script
```

---

## 2. Unit Tests

### 2.1 store.py - Memory Storage

Test file: `tests/test_store.py`

#### Create Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_create_memory_minimal` | Create memory with only required fields (topic, content) | Memory file created, ID returned, index updated |
| `test_create_memory_with_tags` | Create memory with explicit tags | Tags stored in frontmatter and tag_index |
| `test_create_memory_auto_tag` | Create memory with `auto_tag=True` | Tags auto-generated from content |
| `test_create_memory_with_difficulty` | Create memory with explicit difficulty | Difficulty stored in frontmatter |
| `test_create_memory_generates_id` | Verify unique ID generation | ID follows `mem_<hash>` pattern |
| `test_create_memory_sets_timestamps` | Verify timestamps set correctly | `created_at` set to current time |
| `test_create_memory_initializes_phase` | Verify phase starts at 0 | `phase: 0` in frontmatter |
| `test_create_memory_summary_and_content` | Verify two-part content structure | `## Summary` and `## Content` sections present |

#### Read Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_read_memory_by_id` | Read existing memory by ID | Full memory content returned |
| `test_read_memory_not_found` | Read non-existent memory | Raises `MemoryNotFoundError` |
| `test_read_memory_updates_stats` | Reading updates access stats | `access_count` incremented in stats.json |
| `test_read_memory_updates_accessed_at` | Reading updates timestamp | `accessed_at` updated in stats.json |

#### Update Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_update_memory_content` | Update memory content | Content section updated, summary unchanged |
| `test_update_memory_tags` | Update memory tags | Tags updated in file and tag_index |
| `test_update_memory_not_found` | Update non-existent memory | Raises `MemoryNotFoundError` |
| `test_update_memory_preserves_metadata` | Update preserves other fields | ID, created_at, difficulty unchanged |

#### Delete Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_delete_memory` | Delete existing memory | File removed, index updated |
| `test_delete_memory_not_found` | Delete non-existent memory | Raises `MemoryNotFoundError` |
| `test_delete_memory_removes_from_tag_index` | Verify tag_index cleanup | Memory ID removed from all tag entries |
| `test_delete_memory_removes_stats` | Verify stats cleanup | Memory entry removed from stats.json |

#### List Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_list_memories_empty` | List with no memories | Empty list returned |
| `test_list_memories_all` | List all memories | All memories returned |
| `test_list_memories_filter_by_phase` | Filter by phase | Only matching phase returned |
| `test_list_memories_filter_by_tag` | Filter by tag | Only memories with tag returned |
| `test_list_memories_filter_by_keyword` | Filter by keyword in topic | Only matching topics returned |
| `test_list_memories_combined_filters` | Multiple filters | Intersection of filters returned |
| `test_list_memories_pagination` | Limit and offset | Correct subset returned |
| `test_list_memories_sorted_by_priority` | Verify priority ordering | Highest priority first |

#### Search Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_search_by_topic` | Search keyword in topic | Matching memories returned |
| `test_search_by_content` | Search keyword in content | Matching memories returned |
| `test_search_case_insensitive` | Case-insensitive search | Matches regardless of case |
| `test_search_no_results` | Search with no matches | Empty list returned |
| `test_search_respects_limit` | Search with limit | Max `limit` results returned |

### 2.2 priority.py - Priority Scoring

Test file: `tests/test_priority.py`

#### Score Calculation

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_priority_formula` | Verify formula: `(difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)` | Correct calculation |
| `test_priority_max_score` | Maximum values for all factors | Priority = 1.0 |
| `test_priority_min_score` | Minimum values for all factors | Priority = 0.0 |
| `test_priority_difficulty_weight` | Verify difficulty contributes 40% | Correct weighting |
| `test_priority_recency_weight` | Verify recency contributes 30% | Correct weighting |
| `test_priority_frequency_weight` | Verify frequency contributes 30% | Correct weighting |

#### Recency Calculation

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_recency_current_session` | Memory accessed this session | Recency = 1.0 |
| `test_recency_one_session_ago` | Memory accessed 1 session ago | Recency = 0.5 |
| `test_recency_decay_curve` | Verify decay: `1 / (1 + sessions_since)` | Correct decay |
| `test_recency_missing_stats` | No stats.json entry | Default recency based on created_session |

#### Frequency Calculation

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_frequency_zero_access` | Never accessed | Frequency = 0.0 |
| `test_frequency_ten_accesses` | Accessed 10 times | Frequency = 1.0 |
| `test_frequency_capped` | Accessed 100 times | Frequency = 1.0 (capped) |
| `test_frequency_normalized` | Accessed 5 times | Frequency = 0.5 |

#### Difficulty Calculation

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_difficulty_from_failures` | Calculate from tool failures | Correct normalization |
| `test_difficulty_zero_failures` | No failures | Difficulty = 0.0 |
| `test_difficulty_capped` | Many failures | Difficulty = 1.0 (capped) |
| `test_difficulty_with_compaction_bonus` | PreCompact triggered | +0.2 bonus applied |

### 2.3 eviction.py - Phased Eviction

Test file: `tests/test_eviction.py`

#### Phase Transitions

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_evict_phase_0_to_1` | Full → Hint transition | Content reduced, summary preserved |
| `test_evict_phase_1_to_2` | Hint → Abstract transition | Content minimized |
| `test_evict_phase_2_to_3` | Abstract → Removed transition | File moved to archives |
| `test_evict_already_removed` | Evict phase 3 memory | No change |

#### Archive Creation

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_archive_created_on_phase_1` | Archive on first eviction | Full content saved to archives/ |
| `test_archive_not_overwritten` | Subsequent evictions | Archive unchanged |
| `test_archive_path` | Verify archive location | `.claude/ltm/archives/{id}.md` |

#### Eviction Trigger

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_eviction_threshold` | Memories exceed threshold | Eviction triggered |
| `test_eviction_below_threshold` | Memories below threshold | No eviction |
| `test_eviction_batch_size` | Evict N lowest priority | Correct batch processed |
| `test_eviction_priority_order` | Lowest priority first | Correct ordering |

#### Content Reduction

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_reduce_to_hint` | Generate hint from full content | Key points extracted |
| `test_reduce_to_abstract` | Generate abstract from hint | One-line summary |
| `test_summary_unchanged` | Summary preserved through phases | `## Summary` never modified |

---

## 3. Integration Tests

### 3.1 MCP Server

Test file: `tests/test_mcp_server.py`

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_server_starts` | MCP server initializes | No errors, server running |
| `test_store_memory_tool` | Invoke store_memory tool | Memory created successfully |
| `test_recall_tool` | Invoke recall tool | Matching memories returned |
| `test_list_memories_tool` | Invoke list_memories with filters | Filtered results returned |
| `test_get_memory_tool` | Invoke get_memory tool | Full memory content returned |
| `test_forget_tool` | Invoke forget tool | Memory deleted |
| `test_ltm_status_tool` | Invoke ltm_status tool | System stats returned |
| `test_tool_error_handling` | Invalid parameters | Graceful error response |
| `test_concurrent_operations` | Multiple simultaneous requests | No race conditions |

### 3.2 Hooks

Test file: `tests/test_hooks.py`

#### session_start.py

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_session_start_loads_memories` | Hook outputs memories to stdout | Top-N memories in output |
| `test_session_start_increments_session` | Session counter updated | state.json session_count +1 |
| `test_session_start_timeout` | Completes within 5s | Execution < 5000ms |
| `test_session_start_empty_memories` | No memories exist | Empty output, no error |
| `test_session_start_priority_order` | Memories ordered by priority | Highest priority first |

#### track_difficulty.py

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_track_difficulty_success` | Tool success via stdin | Success count incremented |
| `test_track_difficulty_failure` | Tool failure via stdin | Failure count incremented |
| `test_track_difficulty_score` | Calculate difficulty score | Correct formula applied |
| `test_track_difficulty_persists` | State persisted | state.json updated |

#### pre_compact.py

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_pre_compact_saves_state` | Hook saves current state | state.json updated |
| `test_pre_compact_increments_compaction` | Compaction counter updated | compaction_count +1 |
| `test_pre_compact_difficulty_bonus` | Adds compaction bonus | +0.2 to current difficulty |

#### session_end.py

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_session_end_persists_changes` | Pending changes saved | All files written |
| `test_session_end_runs_eviction` | Eviction triggered if needed | Low-priority memories evicted |
| `test_session_end_updates_recency` | Accessed memories updated | last_session set |
| `test_session_end_resets_session_state` | Session state cleared | current_session reset |

### 3.3 Storage File Operations

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_atomic_write_memory` | Write doesn't corrupt on crash | Temp file then rename |
| `test_atomic_write_index` | Index write is atomic | Temp file then rename |
| `test_concurrent_file_access` | Multiple readers/writers | No corruption |
| `test_missing_directories` | Directories auto-created | memories/, archives/ created |
| `test_gitignore_created` | .gitignore exists | stats.json, state.json ignored |

### 3.4 Containerized Deployment

Test file: `tests/test_container.py`

#### Container Build

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_dockerfile_builds` | Docker build succeeds | Image created without errors |
| `test_image_size` | Image is reasonably sized | < 200MB |
| `test_container_starts` | Container starts successfully | Exit code 0 or running |
| `test_container_healthcheck` | Health endpoint responds | Healthy status |

#### Volume Mount

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_volume_mount_memories` | memories/ accessible in container | Files readable/writable |
| `test_volume_mount_persistence` | Data persists after container restart | Memories survive restart |
| `test_volume_permissions` | Correct file permissions | Container user can read/write |
| `test_missing_volume` | Container handles missing mount | Graceful error or creates dirs |

#### Functional Parity

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_container_store_memory` | store_memory works in container | Identical to local behavior |
| `test_container_recall` | recall works in container | Identical to local behavior |
| `test_container_list_memories` | list_memories with filters | Identical to local behavior |
| `test_container_get_memory` | get_memory works in container | Identical to local behavior |
| `test_container_forget` | forget works in container | Identical to local behavior |
| `test_container_ltm_status` | ltm_status works in container | Identical to local behavior |

#### Container-Specific Scenarios

| Test Case | Description | Expected Result |
|-----------|-------------|-----------------|
| `test_container_stdio_transport` | MCP stdio works via docker run -i | Bidirectional communication |
| `test_container_graceful_shutdown` | SIGTERM handling | Clean shutdown, data saved |
| `test_container_resource_limits` | Memory/CPU constraints | Operates within limits |
| `test_container_concurrent_access` | Multiple container instances | No data corruption |

#### Container Build & Run Commands

```bash
# Build the container
docker build -t ltm-mcp-server .claude/ltm/

# Verify build
docker images ltm-mcp-server

# Test container starts
docker run --rm ltm-mcp-server --help

# Test with volume mount
docker run -i --rm \
  -v "$(pwd)/.claude/ltm:/data" \
  ltm-mcp-server

# Test MCP tool invocation (interactive)
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"ltm_status"},"id":1}' | \
  docker run -i --rm \
  -v "$(pwd)/.claude/ltm:/data" \
  ltm-mcp-server
```

#### Parity Test Script

```bash
#!/bin/bash
# tests/scripts/test_container_parity.sh
# Runs same test suite against local and containerized server

set -e

# Test against local server
echo "Testing local server..."
python .claude/ltm/mcp_server.py &
LOCAL_PID=$!
sleep 2
pytest .claude/ltm/tests/test_mcp_server.py -v
kill $LOCAL_PID

# Test against containerized server
echo "Testing containerized server..."
docker run -d --name ltm-test \
  -v "$(pwd)/.claude/ltm:/data" \
  ltm-mcp-server
sleep 2
LTM_CONTAINER=1 pytest .claude/ltm/tests/test_mcp_server.py -v
docker stop ltm-test
docker rm ltm-test

echo "Parity tests passed!"
```

#### Claude Code Registration Test

```bash
# Register containerized server with Claude Code
claude mcp add --transport stdio ltm -- docker run -i --rm \
  -v "$(pwd)/.claude/ltm:/data" ltm-mcp-server

# Verify registration
claude mcp list | grep ltm

# Test in Claude Code session
# "Show LTM status" → should return stats from container

# Cleanup
claude mcp remove ltm
```

---

## 4. End-to-End Tests

Test file: `tests/test_e2e.py`

### 4.1 Full Session Cycle

| Test Case | Description | Steps |
|-----------|-------------|-------|
| `test_full_session_cycle` | Complete workflow | 1. SessionStart hook runs<br>2. Store memory via MCP<br>3. Recall memory via MCP<br>4. SessionEnd hook runs<br>5. Verify persistence |

### 4.2 Multi-Session Recency

| Test Case | Description | Steps |
|-----------|-------------|-------|
| `test_recency_across_sessions` | Recency decay over sessions | 1. Create memory in session 1<br>2. Simulate sessions 2-5<br>3. Verify recency score decay<br>4. Access memory in session 5<br>5. Verify recency reset |

### 4.3 Eviction Progression

| Test Case | Description | Steps |
|-----------|-------------|-------|
| `test_eviction_full_cycle` | Memory through all phases | 1. Create memory (phase 0)<br>2. Trigger eviction → phase 1<br>3. Verify archive created<br>4. Trigger eviction → phase 2<br>5. Trigger eviction → phase 3<br>6. Verify removed from memories/ |

### 4.4 Priority-Based Loading

| Test Case | Description | Steps |
|-----------|-------------|-------|
| `test_priority_loading` | High-priority memories load first | 1. Create 20 memories with varying priority<br>2. Configure load limit = 5<br>3. Run SessionStart<br>4. Verify top 5 by priority loaded |

### 4.5 Tag and Keyword Filtering

| Test Case | Description | Steps |
|-----------|-------------|-------|
| `test_filter_workflow` | Filter memories in session | 1. Create memories with various tags<br>2. List with tag filter<br>3. List with keyword filter<br>4. Verify correct filtering |

---

## 5. Test Fixtures

### 5.1 Sample Memory Files

Located in `tests/fixtures/memories/`

#### Phase 0 Memory (Full)

```yaml
# tests/fixtures/memories/mem_fixture_phase0.md
---
id: "mem_fixture_phase0"
topic: "Database connection pooling optimization"
tags:
  - database
  - performance
  - postgres
phase: 0
difficulty: 0.7
created_at: "2026-01-15T10:00:00Z"
created_session: 10
---

## Summary
Optimized database connection pooling to handle high-concurrency batch operations. Increased pool size and added connection timeout handling.

## Content
### Problem
Database connections were being exhausted during peak batch processing, causing timeouts.

### Solution
1. Increased connection pool from 10 to 50
2. Added connection timeout of 60 seconds
3. Implemented exponential backoff retry

### Key Files
- src/db/pool.py:45
- config/database.yaml
```

#### Phase 1 Memory (Hint)

```yaml
# tests/fixtures/memories/mem_fixture_phase1.md
---
id: "mem_fixture_phase1"
topic: "API rate limiting implementation"
tags:
  - api
  - security
phase: 1
difficulty: 0.5
created_at: "2026-01-10T14:00:00Z"
created_session: 5
---

## Summary
Implemented token bucket rate limiting for public API endpoints to prevent abuse.

## Content
Rate limit: 100 req/min per API key. Token bucket in Redis. See src/middleware/rate_limit.py.
```

#### Phase 2 Memory (Abstract)

```yaml
# tests/fixtures/memories/mem_fixture_phase2.md
---
id: "mem_fixture_phase2"
topic: "OAuth2 refresh token rotation"
tags:
  - auth
  - security
phase: 2
difficulty: 0.3
created_at: "2026-01-01T09:00:00Z"
created_session: 1
---

## Summary
Implemented refresh token rotation for OAuth2 to improve security posture.

## Content
Refresh tokens rotate on use. See auth service.
```

### 5.2 Sample Index File

```json
// tests/fixtures/index.json
{
  "version": 1,
  "memories": {
    "mem_fixture_phase0": {
      "topic": "Database connection pooling optimization",
      "tags": ["database", "performance", "postgres"],
      "phase": 0,
      "difficulty": 0.7,
      "created_at": "2026-01-15T10:00:00Z"
    },
    "mem_fixture_phase1": {
      "topic": "API rate limiting implementation",
      "tags": ["api", "security"],
      "phase": 1,
      "difficulty": 0.5,
      "created_at": "2026-01-10T14:00:00Z"
    },
    "mem_fixture_phase2": {
      "topic": "OAuth2 refresh token rotation",
      "tags": ["auth", "security"],
      "phase": 2,
      "difficulty": 0.3,
      "created_at": "2026-01-01T09:00:00Z"
    }
  },
  "tag_index": {
    "database": ["mem_fixture_phase0"],
    "performance": ["mem_fixture_phase0"],
    "postgres": ["mem_fixture_phase0"],
    "api": ["mem_fixture_phase1"],
    "security": ["mem_fixture_phase1", "mem_fixture_phase2"],
    "auth": ["mem_fixture_phase2"]
  }
}
```

### 5.3 Sample Stats File

```json
// tests/fixtures/stats.json
{
  "version": 1,
  "memories": {
    "mem_fixture_phase0": {
      "access_count": 5,
      "accessed_at": "2026-01-28T10:00:00Z",
      "last_session": 20,
      "priority": 0.85
    },
    "mem_fixture_phase1": {
      "access_count": 2,
      "accessed_at": "2026-01-25T14:00:00Z",
      "last_session": 15,
      "priority": 0.55
    },
    "mem_fixture_phase2": {
      "access_count": 1,
      "accessed_at": "2026-01-20T09:00:00Z",
      "last_session": 10,
      "priority": 0.25
    }
  }
}
```

### 5.4 Sample State File

```json
// tests/fixtures/state.json
{
  "version": 1,
  "session_count": 25,
  "current_session": {
    "started_at": "2026-01-28T09:00:00Z",
    "difficulty_score": 0.0,
    "tool_failures": 0,
    "tool_successes": 0
  },
  "last_eviction": "2026-01-20T00:00:00Z",
  "compaction_count": 3,
  "config": {
    "max_memories": 100,
    "memories_to_load": 10,
    "eviction_batch_size": 10
  }
}
```

### 5.5 Mock Hook Payloads

```python
# tests/fixtures/hook_payloads.py

SESSION_START_PAYLOAD = {
    "session_id": "test-session-001",
    "transcript_path": "/tmp/test-transcript.jsonl"
}

POST_TOOL_USE_SUCCESS = {
    "session_id": "test-session-001",
    "transcript_path": "/tmp/test-transcript.jsonl",
    "tool_name": "Write",
    "tool_input": {"file_path": "/tmp/test.py", "content": "print('hello')"},
    "tool_response": {"success": True},
    "tool_use_id": "toolu_test123"
}

POST_TOOL_USE_FAILURE = {
    "session_id": "test-session-001",
    "transcript_path": "/tmp/test-transcript.jsonl",
    "tool_name": "Bash",
    "tool_input": {"command": "invalid_command"},
    "tool_response": {"error": "command not found"},
    "tool_use_id": "toolu_test456"
}

PRE_COMPACT_PAYLOAD = {
    "session_id": "test-session-001",
    "transcript_path": "/tmp/test-transcript.jsonl"
}

SESSION_END_PAYLOAD = {
    "session_id": "test-session-001",
    "transcript_path": "/tmp/test-transcript.jsonl"
}
```

---

## 6. Verification Checklist

### 6.1 Manual Verification Steps

#### Memory Storage

- [ ] Create memory via "remember this" command
- [ ] Verify memory file created in `.claude/ltm/memories/`
- [ ] Verify index.json updated with new entry
- [ ] Verify stats.json updated with access data
- [ ] Verify auto-tagging works when no tags provided

#### Memory Retrieval

- [ ] Recall memory via "what do you know about X" command
- [ ] Verify correct memories returned
- [ ] Verify access_count incremented after recall
- [ ] Verify priority ordering in results

#### Filtering

- [ ] List memories filtered by tag
- [ ] List memories filtered by keyword
- [ ] List memories filtered by phase
- [ ] Verify combined filters work correctly

#### Session Lifecycle

- [ ] Start new session, verify memories loaded
- [ ] Verify session_count incremented
- [ ] End session, verify state persisted
- [ ] Start another session, verify previous memories available

#### Eviction

- [ ] Create enough memories to trigger eviction
- [ ] Verify lowest-priority memory evicted first
- [ ] Verify archive created on phase 0 → 1
- [ ] Verify summary preserved through all phases

### 6.2 MCP Tool Testing via Claude Code

```bash
# Register MCP server
claude mcp add --transport stdio ltm -- python .claude/ltm/mcp_server.py

# Test each tool interactively
# In Claude Code session:
# "Store a memory about testing the LTM system"
# "What do you know about LTM?"
# "List all memories"
# "Show LTM status"
# "Forget memory <id>"
```

### 6.3 Hook Testing via Simulated Events

```bash
# Test session_start hook
echo '{"session_id": "test"}' | python .claude/ltm/hooks/session_start.py

# Test track_difficulty hook (success)
echo '{"tool_name": "Write", "tool_response": {"success": true}}' | \
  python .claude/ltm/hooks/track_difficulty.py

# Test track_difficulty hook (failure)
echo '{"tool_name": "Bash", "tool_response": {"error": "failed"}}' | \
  python .claude/ltm/hooks/track_difficulty.py

# Test pre_compact hook
echo '{"session_id": "test"}' | python .claude/ltm/hooks/pre_compact.py

# Test session_end hook
echo '{"session_id": "test"}' | python .claude/ltm/hooks/session_end.py
```

---

## 7. Running Tests

### Prerequisites

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov

# Or with requirements
pip install -r .claude/ltm/requirements-dev.txt
```

### Run All Tests

```bash
# From project root
pytest .claude/ltm/tests/ -v

# With coverage
pytest .claude/ltm/tests/ -v --cov=.claude/ltm --cov-report=html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest .claude/ltm/tests/test_store.py .claude/ltm/tests/test_priority.py .claude/ltm/tests/test_eviction.py -v

# Integration tests only (local)
pytest .claude/ltm/tests/test_mcp_server.py .claude/ltm/tests/test_hooks.py -v

# Container tests only
pytest .claude/ltm/tests/test_container.py -v

# E2E tests only
pytest .claude/ltm/tests/test_e2e.py -v

# Container parity tests (compares local vs containerized)
bash .claude/ltm/tests/scripts/test_container_parity.sh
```

### Test in Isolation

```bash
# Use temporary directory for test data
pytest .claude/ltm/tests/ -v --basetemp=/tmp/ltm-test
```

---

## 8. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-01-28 | Initial testing strategy |

---

*Document maintained as part of the Long-Term Memory system for Claude Code.*
