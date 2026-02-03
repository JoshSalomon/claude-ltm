"""Shared test fixtures for LTM tests."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add server directory to path for imports
# tests are at: server/tests/ -> go up one level to server/
_server_path = Path(__file__).parent.parent
sys.path.insert(0, str(_server_path))

from store import MemoryStore
from priority import PriorityCalculator


@pytest.fixture
def temp_ltm_dir():
    """Create a temporary LTM directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="ltm_test_")
    temp_path = Path(temp_dir)

    # Create subdirectories
    (temp_path / "memories").mkdir()
    (temp_path / "archives").mkdir()

    yield temp_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def store(temp_ltm_dir):
    """Create a MemoryStore with temporary directory."""
    return MemoryStore(base_path=temp_ltm_dir)


@pytest.fixture
def priority_calculator():
    """Create a PriorityCalculator instance."""
    return PriorityCalculator()


@pytest.fixture
def sample_memory():
    """Sample memory data for testing."""
    return {
        "topic": "Database connection pooling optimization",
        "content": """## Summary
Optimized database connection pooling to handle high-concurrency batch operations.

## Content
### Problem
Database connections were being exhausted during peak batch processing.

### Solution
1. Increased connection pool from 10 to 50
2. Added connection timeout of 60 seconds
""",
        "tags": ["database", "performance", "postgres"],
        "difficulty": 0.7,
    }


@pytest.fixture
def sample_index():
    """Sample index.json data."""
    return {
        "version": 1,
        "memories": {
            "mem_test001": {
                "topic": "Database connection pooling",
                "tags": ["database", "performance"],
                "phase": 0,
                "difficulty": 0.7,
                "created_at": "2026-01-15T10:00:00Z",
            },
            "mem_test002": {
                "topic": "API rate limiting",
                "tags": ["api", "security"],
                "phase": 1,
                "difficulty": 0.5,
                "created_at": "2026-01-10T14:00:00Z",
            },
            "mem_test003": {
                "topic": "Authentication refresh tokens",
                "tags": ["auth", "security"],
                "phase": 2,
                "difficulty": 0.3,
                "created_at": "2026-01-01T09:00:00Z",
            },
        },
    }


@pytest.fixture
def sample_stats():
    """Sample stats.json data."""
    return {
        "version": 1,
        "memories": {
            "mem_test001": {
                "access_count": 5,
                "accessed_at": "2026-01-28T10:00:00Z",
                "last_session": 20,
                "priority": 0.85,
            },
            "mem_test002": {
                "access_count": 2,
                "accessed_at": "2026-01-25T14:00:00Z",
                "last_session": 15,
                "priority": 0.55,
            },
            "mem_test003": {
                "access_count": 1,
                "accessed_at": "2026-01-20T09:00:00Z",
                "last_session": 10,
                "priority": 0.25,
            },
        },
    }


@pytest.fixture
def sample_state():
    """Sample state.json data."""
    return {
        "version": 1,
        "session_count": 25,
        "current_session": {
            "started_at": "2026-01-28T09:00:00Z",
            "tool_failures": 0,
            "tool_successes": 0,
            "compacted": False,
        },
        "compaction_count": 3,
        "config": {
            "max_memories": 100,
            "memories_to_load": 10,
            "eviction_batch_size": 10,
        },
    }


@pytest.fixture
def populated_store(temp_ltm_dir, sample_index, sample_stats, sample_state):
    """Create a store with pre-populated test data."""
    # Write index
    with open(temp_ltm_dir / "index.json", "w") as f:
        json.dump(sample_index, f)

    # Write stats
    with open(temp_ltm_dir / "stats.json", "w") as f:
        json.dump(sample_stats, f)

    # Write state
    with open(temp_ltm_dir / "state.json", "w") as f:
        json.dump(sample_state, f)

    # Create memory files
    for mem_id in sample_index["memories"]:
        mem_data = sample_index["memories"][mem_id]
        content = f"""---
id: "{mem_id}"
topic: "{mem_data['topic']}"
tags:
  - {chr(10) + '  - '.join(mem_data['tags'])}
phase: {mem_data['phase']}
difficulty: {mem_data['difficulty']}
created_at: "{mem_data['created_at']}"
---

## Summary
Test memory for {mem_data['topic']}.

## Content
This is test content for memory {mem_id}.
"""
        with open(temp_ltm_dir / "memories" / f"{mem_id}.md", "w") as f:
            f.write(content)

    return MemoryStore(base_path=temp_ltm_dir)
