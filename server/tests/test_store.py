"""Unit tests for store.py - Memory Storage."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from store import MemoryStore, MemoryNotFoundError


class TestCreateOperations:
    """Tests for memory create operations."""

    def test_create_memory_minimal(self, store, sample_memory):
        """Create memory with only required fields."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        assert memory_id.startswith("mem_")
        assert len(memory_id) == 12  # mem_ + 8 chars

        # Verify file created
        memory_path = store.memories_path / f"{memory_id}.md"
        assert memory_path.exists()

        # Verify index updated
        index = store._read_index()
        assert memory_id in index["memories"]

    def test_create_memory_with_tags(self, store, sample_memory):
        """Create memory with explicit tags."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            tags=sample_memory["tags"],
        )

        # Verify tags in index
        index = store._read_index()
        assert index["memories"][memory_id]["tags"] == sample_memory["tags"]

    def test_create_memory_with_difficulty(self, store, sample_memory):
        """Create memory with explicit difficulty."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            difficulty=0.9,
        )

        index = store._read_index()
        assert index["memories"][memory_id]["difficulty"] == 0.9

    def test_create_memory_generates_id(self, store, sample_memory):
        """Verify unique ID generation."""
        id1 = store.create(topic="Test 1", content="Content 1")
        id2 = store.create(topic="Test 2", content="Content 2")

        assert id1 != id2
        assert id1.startswith("mem_")
        assert id2.startswith("mem_")

    def test_create_memory_sets_timestamps(self, store, sample_memory):
        """Verify timestamps set correctly."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        index = store._read_index()
        assert "created_at" in index["memories"][memory_id]
        assert index["memories"][memory_id]["created_at"]

    def test_create_memory_initializes_phase(self, store, sample_memory):
        """Verify phase starts at 0."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        index = store._read_index()
        assert index["memories"][memory_id]["phase"] == 0

    def test_create_memory_difficulty_clamped(self, store):
        """Verify difficulty is clamped to [0.0, 1.0]."""
        id1 = store.create(topic="Test", content="Content", difficulty=-0.5)
        id2 = store.create(topic="Test", content="Content", difficulty=1.5)

        index = store._read_index()
        assert index["memories"][id1]["difficulty"] == 0.0
        assert index["memories"][id2]["difficulty"] == 1.0


class TestReadOperations:
    """Tests for memory read operations."""

    def test_read_memory_by_id(self, store, sample_memory):
        """Read existing memory by ID."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            tags=sample_memory["tags"],
        )

        memory = store.read(memory_id)

        assert memory["id"] == memory_id
        assert memory["topic"] == sample_memory["topic"]
        assert sample_memory["content"].strip() in memory["content"]

    def test_read_memory_not_found(self, store):
        """Read non-existent memory raises error."""
        with pytest.raises(MemoryNotFoundError):
            store.read("mem_nonexistent")

    def test_read_memory_updates_stats(self, store, sample_memory):
        """Reading updates access stats."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        # Read twice
        store.read(memory_id)
        store.invalidate_cache()
        store.read(memory_id)

        stats = store._read_stats()
        assert stats["memories"][memory_id]["access_count"] == 2

    def test_read_memory_updates_accessed_at(self, store, sample_memory):
        """Reading updates timestamp."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        store.read(memory_id)

        stats = store._read_stats()
        assert "accessed_at" in stats["memories"][memory_id]

    def test_read_memory_no_stats_update(self, store, sample_memory):
        """Reading with update_stats=False doesn't update stats."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        initial_stats = store._read_stats()
        initial_count = initial_stats["memories"][memory_id]["access_count"]

        store.read(memory_id, update_stats=False)

        stats = store._read_stats()
        assert stats["memories"][memory_id]["access_count"] == initial_count


class TestUpdateOperations:
    """Tests for memory update operations."""

    def test_update_memory_content(self, store, sample_memory):
        """Update memory content."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        new_content = "Updated content"
        store.update(memory_id, content=new_content)

        memory = store.read(memory_id, update_stats=False)
        assert new_content in memory["content"]

    def test_update_memory_tags(self, store, sample_memory):
        """Update memory tags."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            tags=["old_tag"],
        )

        store.update(memory_id, tags=["new_tag", "another_tag"])

        index = store._read_index()
        assert index["memories"][memory_id]["tags"] == ["new_tag", "another_tag"]

    def test_update_memory_not_found(self, store):
        """Update non-existent memory raises error."""
        with pytest.raises(MemoryNotFoundError):
            store.update("mem_nonexistent", content="New content")

    def test_update_memory_preserves_metadata(self, store, sample_memory):
        """Update preserves other fields."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            tags=sample_memory["tags"],
            difficulty=0.8,
        )

        store.update(memory_id, content="New content")

        memory = store.read(memory_id, update_stats=False)
        index = store._read_index()

        assert memory["topic"] == sample_memory["topic"]
        assert index["memories"][memory_id]["difficulty"] == 0.8


class TestDeleteOperations:
    """Tests for memory delete operations."""

    def test_delete_memory(self, store, sample_memory):
        """Delete existing memory."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        result = store.delete(memory_id)

        assert result is True
        assert not (store.memories_path / f"{memory_id}.md").exists()

    def test_delete_memory_not_found(self, store):
        """Delete non-existent memory raises error."""
        with pytest.raises(MemoryNotFoundError):
            store.delete("mem_nonexistent")

    def test_delete_memory_removes_from_index(self, store, sample_memory):
        """Verify index cleanup after delete."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            tags=sample_memory["tags"],
        )

        store.delete(memory_id)

        index = store._read_index()
        assert memory_id not in index["memories"]

    def test_delete_memory_removes_stats(self, store, sample_memory):
        """Verify stats cleanup after delete."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        store.delete(memory_id)

        stats = store._read_stats()
        assert memory_id not in stats["memories"]

    def test_delete_memory_archives(self, store, sample_memory):
        """Delete with archive=True creates archive."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        store.delete(memory_id, archive=True)

        archive_path = store.archives_path / f"{memory_id}.md"
        assert archive_path.exists()

    def test_delete_memory_no_archive(self, store, sample_memory):
        """Delete with archive=False doesn't create archive."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
        )

        store.delete(memory_id, archive=False)

        archive_path = store.archives_path / f"{memory_id}.md"
        assert not archive_path.exists()


class TestListOperations:
    """Tests for memory list operations."""

    def test_list_memories_empty(self, store):
        """List with no memories returns empty list."""
        result = store.list()
        assert result == []

    def test_list_memories_all(self, store, sample_memory):
        """List all memories."""
        ids = []
        for i in range(3):
            mem_id = store.create(
                topic=f"Memory {i}",
                content=f"Content {i}",
            )
            ids.append(mem_id)

        result = store.list()

        assert len(result) == 3
        result_ids = [m["id"] for m in result]
        for mem_id in ids:
            assert mem_id in result_ids

    def test_list_memories_filter_by_phase(self, store):
        """Filter by phase."""
        id1 = store.create(topic="Phase 0", content="Content")
        id2 = store.create(topic="Phase 1", content="Content")

        # Update phase for id2
        store.update(id2, phase=1)

        result = store.list(phase=0)
        assert len(result) == 1
        assert result[0]["id"] == id1

        result = store.list(phase=1)
        assert len(result) == 1
        assert result[0]["id"] == id2

    def test_list_memories_filter_by_tag(self, store):
        """Filter by tag."""
        id1 = store.create(topic="Tagged", content="Content", tags=["important"])
        store.create(topic="Not tagged", content="Content", tags=["other"])

        result = store.list(tag="important")

        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_list_memories_filter_by_keyword(self, store):
        """Filter by keyword in topic."""
        id1 = store.create(topic="Database optimization", content="Content")
        store.create(topic="API design", content="Content")

        result = store.list(keyword="database")

        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_list_memories_keyword_case_insensitive(self, store):
        """Keyword filter is case-insensitive."""
        id1 = store.create(topic="DATABASE optimization", content="Content")

        result = store.list(keyword="database")
        assert len(result) == 1
        assert result[0]["id"] == id1

        result = store.list(keyword="DATABASE")
        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_list_memories_combined_filters(self, store):
        """Multiple filters return intersection."""
        store.create(
            topic="Database optimization",
            content="Content",
            tags=["performance"],
        )
        id2 = store.create(
            topic="Database security",
            content="Content",
            tags=["security"],
        )
        store.create(
            topic="API security",
            content="Content",
            tags=["security"],
        )

        result = store.list(keyword="database", tag="security")

        assert len(result) == 1
        assert result[0]["id"] == id2

    def test_list_memories_pagination(self, store):
        """Limit and offset work correctly."""
        for i in range(10):
            store.create(topic=f"Memory {i}", content=f"Content {i}")

        result = store.list(limit=3)
        assert len(result) == 3

        result = store.list(limit=3, offset=3)
        assert len(result) == 3

        result = store.list(limit=3, offset=9)
        assert len(result) == 1

    def test_list_memories_sorted_by_priority(self, store):
        """Verify priority ordering (highest first)."""
        # Create with different difficulties
        id_low = store.create(
            topic="Low priority", content="Content", difficulty=0.1
        )
        id_high = store.create(
            topic="High priority", content="Content", difficulty=0.9
        )
        id_med = store.create(
            topic="Medium priority", content="Content", difficulty=0.5
        )

        result = store.list()

        # Higher difficulty = higher priority
        assert result[0]["id"] == id_high
        assert result[1]["id"] == id_med
        assert result[2]["id"] == id_low


class TestSearchOperations:
    """Tests for memory search operations."""

    def test_search_by_topic(self, store):
        """Search keyword in topic."""
        id1 = store.create(topic="Database optimization", content="Content")
        store.create(topic="API design", content="Content")

        result = store.search("database")

        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_search_by_content(self, store):
        """Search keyword in content."""
        id1 = store.create(
            topic="Topic",
            content="This is about database optimization",
        )
        store.create(topic="Topic", content="This is about API design")

        result = store.search("database")

        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_search_case_insensitive(self, store):
        """Search is case-insensitive."""
        id1 = store.create(topic="DATABASE", content="Content")

        result = store.search("database")
        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_search_no_results(self, store):
        """Search with no matches returns empty list."""
        store.create(topic="Topic", content="Content")

        result = store.search("nonexistent")
        assert result == []

    def test_search_respects_limit(self, store):
        """Search respects limit parameter."""
        for i in range(10):
            store.create(topic=f"Database {i}", content=f"Content {i}")

        result = store.search("database", limit=3)
        assert len(result) == 3

    def test_search_returns_summary(self, store):
        """Search results include summary."""
        store.create(
            topic="Topic",
            content="This is a long content that should be truncated in the summary.",
        )

        result = store.search("topic")

        assert len(result) == 1
        assert "summary" in result[0]

    def test_search_by_tag(self, store):
        """Search finds memory by tag."""
        id1 = store.create(
            topic="Generic topic",
            content="Generic content",
            tags=["database", "optimization"],
        )
        store.create(
            topic="Other topic",
            content="Other content",
            tags=["api"],
        )

        result = store.search("database")

        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_search_by_tag_partial_match(self, store):
        """Search finds memory by partial tag match."""
        id1 = store.create(
            topic="Topic",
            content="Content",
            tags=["postgresql"],
        )

        result = store.search("postgres")

        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_search_by_tag_case_insensitive(self, store):
        """Search by tag is case-insensitive."""
        id1 = store.create(
            topic="Topic",
            content="Content",
            tags=["PostgreSQL"],
        )

        result = store.search("postgresql")

        assert len(result) == 1
        assert result[0]["id"] == id1

    def test_search_prefers_topic_over_tag(self, store):
        """Search checks topic before tags (efficiency)."""
        # If topic matches, content check is skipped
        id1 = store.create(
            topic="Database topic",
            content="Content",
            tags=["other"],
        )

        result = store.search("database")

        assert len(result) == 1
        assert result[0]["id"] == id1


class TestFileOperations:
    """Tests for file operations."""

    def test_atomic_write_creates_file(self, store):
        """Atomic write creates file."""
        test_data = {"test": "data"}
        test_path = store.base_path / "test.json"

        store._atomic_write_json(test_path, test_data)

        assert test_path.exists()
        with open(test_path) as f:
            assert json.load(f) == test_data

    def test_memory_file_format(self, store, sample_memory):
        """Verify memory file has correct format."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            tags=sample_memory["tags"],
        )

        memory_path = store.memories_path / f"{memory_id}.md"
        content = memory_path.read_text()

        # Check YAML frontmatter
        assert content.startswith("---")
        assert "topic:" in content
        assert "tags:" in content
        assert "phase:" in content
        assert "difficulty:" in content

    def test_parse_memory_file(self, store, sample_memory):
        """Parse memory file correctly."""
        memory_id = store.create(
            topic=sample_memory["topic"],
            content=sample_memory["content"],
            tags=sample_memory["tags"],
            difficulty=0.7,
        )

        memory_path = store.memories_path / f"{memory_id}.md"
        parsed = store._parse_memory_file(memory_path)

        assert parsed["id"] == memory_id
        assert parsed["topic"] == sample_memory["topic"]
        assert parsed["tags"] == sample_memory["tags"]
        assert parsed["difficulty"] == 0.7
        assert parsed["phase"] == 0

    def test_directories_auto_created(self, temp_ltm_dir):
        """Directories are auto-created if missing."""
        import shutil

        # Remove directories
        shutil.rmtree(temp_ltm_dir / "memories", ignore_errors=True)
        shutil.rmtree(temp_ltm_dir / "archives", ignore_errors=True)

        # Create new store
        store = MemoryStore(base_path=temp_ltm_dir)

        assert (temp_ltm_dir / "memories").exists()
        assert (temp_ltm_dir / "archives").exists()

    def test_parse_file_without_frontmatter(self, store):
        """Parse file without YAML frontmatter."""
        # Create a plain markdown file without frontmatter
        test_path = store.memories_path / "plain.md"
        test_path.write_text("Just plain content without frontmatter")

        parsed = store._parse_memory_file(test_path)

        assert parsed["content"] == "Just plain content without frontmatter"

    def test_parse_yaml_with_boolean(self, store):
        """Parse YAML with boolean values."""
        test_path = store.memories_path / "bool_test.md"
        test_path.write_text("""---
id: "test"
active: true
disabled: false
---
Content here
""")

        parsed = store._parse_memory_file(test_path)

        assert parsed["active"] is True
        assert parsed["disabled"] is False

    def test_parse_yaml_with_comments(self, store):
        """Parse YAML with comment lines."""
        test_path = store.memories_path / "comment_test.md"
        test_path.write_text("""---
id: "test"
# This is a comment
topic: "Test topic"
---
Content here
""")

        parsed = store._parse_memory_file(test_path)

        assert parsed["id"] == "test"
        assert parsed["topic"] == "Test topic"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_list_memories_without_stats(self, temp_ltm_dir):
        """List memories when stats.json doesn't have entry for a memory."""
        store = MemoryStore(base_path=temp_ltm_dir)

        # Create a memory
        memory_id = store.create(topic="Test", content="Content")

        # Clear stats for this memory to simulate missing stats
        stats = store._read_stats()
        del stats["memories"][memory_id]
        store._write_stats(stats)
        store.invalidate_cache()

        # List should still work, calculating priority on the fly
        result = store.list()

        assert len(result) == 1
        assert result[0]["id"] == memory_id
        assert "priority" in result[0]

    def test_search_calculates_priority_when_missing(self, temp_ltm_dir):
        """Search calculates priority when not in stats."""
        store = MemoryStore(base_path=temp_ltm_dir)

        # Create a memory
        memory_id = store.create(topic="Searchable topic", content="Content")

        # Clear stats for this memory
        stats = store._read_stats()
        del stats["memories"][memory_id]
        store._write_stats(stats)
        store.invalidate_cache()

        # Search should still work
        result = store.search("searchable")

        assert len(result) == 1
        assert result[0]["id"] == memory_id

    def test_read_existing_index_from_disk(self, temp_ltm_dir):
        """Read index.json that already exists on disk."""
        # Pre-create index.json
        index_data = {
            "version": 1,
            "memories": {
                "mem_existing": {
                    "topic": "Existing memory",
                    "tags": ["test"],
                    "phase": 0,
                    "difficulty": 0.5,
                    "created_at": "2026-01-01T00:00:00Z",
                }
            },
        }
        index_path = temp_ltm_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump(index_data, f)

        # Create store and verify it reads existing index
        store = MemoryStore(base_path=temp_ltm_dir)
        index = store._read_index()

        assert "mem_existing" in index["memories"]
        assert index["memories"]["mem_existing"]["topic"] == "Existing memory"

    def test_read_existing_state_from_disk(self, temp_ltm_dir):
        """Read state.json that already exists on disk."""
        # Pre-create state.json
        state_data = {
            "version": 1,
            "session_count": 42,
            "current_session": {},
            "compaction_count": 5,
            "config": {"max_memories": 200},
        }
        state_path = temp_ltm_dir / "state.json"
        with open(state_path, "w") as f:
            json.dump(state_data, f)

        # Create store and verify it reads existing state
        store = MemoryStore(base_path=temp_ltm_dir)
        state = store._read_state()

        assert state["session_count"] == 42
        assert state["compaction_count"] == 5

    def test_read_state_merges_session_tokens_default(self, temp_ltm_dir):
        """Existing state without session_tokens gets default merged in."""
        # Pre-create state.json without session_tokens
        state_data = {
            "version": 1,
            "session_count": 10,
            "current_session": {"tool_failures": 5},
            "compaction_count": 0,
            "config": {},
        }
        state_path = temp_ltm_dir / "state.json"
        with open(state_path, "w") as f:
            json.dump(state_data, f)

        store = MemoryStore(base_path=temp_ltm_dir)
        state = store._read_state()

        # Should have session_tokens default merged in
        assert state["current_session"]["session_tokens"] == 0
        # Original values preserved
        assert state["current_session"]["tool_failures"] == 5

    def test_read_state_merges_token_counting_config(self, temp_ltm_dir):
        """Existing state without token_counting config gets defaults merged."""
        # Pre-create state.json without token_counting
        state_data = {
            "version": 1,
            "session_count": 5,
            "current_session": {},
            "compaction_count": 0,
            "config": {"max_memories": 50},
        }
        state_path = temp_ltm_dir / "state.json"
        with open(state_path, "w") as f:
            json.dump(state_data, f)

        store = MemoryStore(base_path=temp_ltm_dir)
        state = store._read_state()

        # Should have token_counting defaults merged in
        assert "token_counting" in state["config"]
        assert state["config"]["token_counting"]["enabled"] is True
        assert state["config"]["token_counting"]["normalize_cap"] == 100000
        # Original values preserved
        assert state["config"]["max_memories"] == 50

    def test_read_state_new_file_has_token_defaults(self, temp_ltm_dir):
        """New state.json includes token counting defaults."""
        store = MemoryStore(base_path=temp_ltm_dir)
        state = store._read_state()

        # Check session_tokens default
        assert state["current_session"]["session_tokens"] == 0

        # Check token_counting config defaults
        assert state["config"]["token_counting"]["enabled"] is True
        assert state["config"]["token_counting"]["normalize_cap"] == 100000

    def test_read_state_missing_current_session_key(self, temp_ltm_dir):
        """Existing state without current_session key gets default added."""
        # Pre-create state.json without current_session
        state_data = {
            "version": 1,
            "session_count": 5,
            "compaction_count": 0,
            "config": {},
        }
        state_path = temp_ltm_dir / "state.json"
        with open(state_path, "w") as f:
            json.dump(state_data, f)

        store = MemoryStore(base_path=temp_ltm_dir)
        state = store._read_state()

        # Should have current_session with session_tokens default
        assert "current_session" in state
        assert state["current_session"]["session_tokens"] == 0

    def test_read_state_missing_config_key(self, temp_ltm_dir):
        """Existing state without config key gets defaults added."""
        # Pre-create state.json without config
        state_data = {
            "version": 1,
            "session_count": 5,
            "current_session": {},
            "compaction_count": 0,
        }
        state_path = temp_ltm_dir / "state.json"
        with open(state_path, "w") as f:
            json.dump(state_data, f)

        store = MemoryStore(base_path=temp_ltm_dir)
        state = store._read_state()

        # Should have config with token_counting defaults
        assert "config" in state
        assert "token_counting" in state["config"]
        assert state["config"]["token_counting"]["enabled"] is True

    def test_write_state(self, store):
        """Test _write_state method."""
        new_state = {
            "version": 1,
            "session_count": 100,
            "current_session": {"test": True},
            "compaction_count": 10,
            "config": {},
        }

        store._write_state(new_state)
        store.invalidate_cache()

        # Read back and verify
        state = store._read_state()
        assert state["session_count"] == 100
        assert state["compaction_count"] == 10

    def test_search_missing_memory_file(self, temp_ltm_dir):
        """Search handles case where index references non-existent file."""
        store = MemoryStore(base_path=temp_ltm_dir)

        # Create a memory
        memory_id = store.create(topic="Test topic", content="Test content")

        # Delete the memory file but leave index entry
        memory_path = store.memories_path / f"{memory_id}.md"
        memory_path.unlink()

        # Search should handle missing file gracefully
        result = store.search("test")

        # Should find by topic (from index) but have empty summary
        assert len(result) == 1
        assert result[0]["summary"] == ""

    def test_search_long_content_truncated(self, store):
        """Search truncates long content in summary."""
        long_content = "A" * 300  # More than 200 chars

        memory_id = store.create(topic="Test", content=long_content)

        result = store.search("test")

        assert len(result) == 1
        assert len(result[0]["summary"]) == 203  # 200 chars + "..."
        assert result[0]["summary"].endswith("...")

    def test_parse_yaml_with_quoted_list_items(self, store):
        """Parse YAML with quoted list items."""
        test_path = store.memories_path / "quoted_list_test.md"
        test_path.write_text('''---
id: "test"
tags:
  - "quoted-tag"
  - unquoted-tag
---
Content here
''')

        parsed = store._parse_memory_file(test_path)

        assert "quoted-tag" in parsed["tags"]
        assert "unquoted-tag" in parsed["tags"]

    def test_parse_yaml_invalid_number(self, store):
        """Parse YAML where number parsing fails."""
        test_path = store.memories_path / "invalid_num_test.md"
        # Create a value that looks numeric but will fail float()
        test_path.write_text('''---
id: "test"
value: 1.2.3
---
Content here
''')

        parsed = store._parse_memory_file(test_path)

        # Should keep as string since it can't be parsed as number
        assert parsed["value"] == "1.2.3"

    def test_store_default_base_path(self, monkeypatch, tmp_path):
        """Test MemoryStore with default base_path uses cwd."""
        # Change to temp directory
        monkeypatch.chdir(tmp_path)

        # Create the .claude/ltm structure
        ltm_path = tmp_path / ".claude" / "ltm"
        ltm_path.mkdir(parents=True)

        # Create store without base_path argument
        store = MemoryStore()

        assert store.base_path == ltm_path

    def test_atomic_write_json_failure_cleanup(self, store, monkeypatch):
        """Test that atomic write cleans up temp file on failure."""
        import os
        import tempfile

        temp_files_created = []
        original_mkstemp = tempfile.mkstemp

        def tracking_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            temp_files_created.append(path)
            return fd, path

        def failing_rename(src, dst):
            raise OSError("Simulated rename failure")

        monkeypatch.setattr(tempfile, "mkstemp", tracking_mkstemp)
        monkeypatch.setattr(os, "rename", failing_rename)

        test_path = store.base_path / "fail_test.json"

        with pytest.raises(OSError):
            store._atomic_write_json(test_path, {"test": "data"})

        # Verify temp file was cleaned up
        for temp_file in temp_files_created:
            assert not os.path.exists(temp_file)

    def test_write_memory_file_failure_cleanup(self, store, monkeypatch):
        """Test that memory file write cleans up temp file on failure."""
        import os
        import tempfile

        temp_files_created = []
        original_mkstemp = tempfile.mkstemp

        def tracking_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            temp_files_created.append(path)
            return fd, path

        def failing_rename(src, dst):
            raise OSError("Simulated rename failure")

        monkeypatch.setattr(tempfile, "mkstemp", tracking_mkstemp)
        monkeypatch.setattr(os, "rename", failing_rename)

        with pytest.raises(OSError):
            store._write_memory_file(
                "test_id",
                {"id": "test_id", "topic": "Test", "content": "Content"},
            )

        # Verify temp file was cleaned up
        for temp_file in temp_files_created:
            assert not os.path.exists(temp_file)

    def test_store_uses_ltm_data_path_env(self, monkeypatch, tmp_path):
        """Test MemoryStore uses LTM_DATA_PATH environment variable."""
        # Set the environment variable
        monkeypatch.setenv("LTM_DATA_PATH", str(tmp_path))

        # Create store without base_path argument
        store = MemoryStore()

        assert store.base_path == tmp_path


class TestIntegrityCheck:
    """Tests for integrity check functionality."""

    def test_check_integrity_healthy(self, store):
        """Check integrity returns healthy for clean store."""
        # Create some memories
        store.create(topic="Memory 1", content="Content 1")
        store.create(topic="Memory 2", content="Content 2")

        result = store.check_integrity()

        assert result["is_healthy"] is True
        assert result["orphaned_files"] == []
        assert result["missing_files"] == []
        assert result["orphaned_stats"] == []
        assert result["summary"]["indexed"] == 2
        assert result["summary"]["files"] == 2

    def test_check_integrity_orphaned_file(self, store):
        """Check integrity detects orphaned memory files."""
        # Create a memory file without index entry
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\ntopic: Orphan\n---\nContent")

        result = store.check_integrity()

        assert result["is_healthy"] is False
        assert "orphan_mem" in result["orphaned_files"]

    def test_check_integrity_missing_file(self, store):
        """Check integrity detects missing memory files."""
        # Create index entry without file
        index = store._read_index()
        index["memories"]["missing_mem"] = {
            "topic": "Missing",
            "tags": [],
            "phase": 0,
        }
        store._write_index(index)

        result = store.check_integrity()

        assert result["is_healthy"] is False
        assert "missing_mem" in result["missing_files"]

    def test_check_integrity_orphaned_stats(self, store):
        """Check integrity detects orphaned stats entries."""
        # Create stats entry without index entry
        stats = store._read_stats()
        stats["memories"]["orphan_stats"] = {
            "access_count": 5,
            "priority": 0.5,
        }
        store._write_stats(stats)

        result = store.check_integrity()

        assert result["is_healthy"] is False
        assert "orphan_stats" in result["orphaned_stats"]

    def test_check_integrity_orphaned_archive(self, store):
        """Check integrity detects orphaned archive files."""
        # Create archive file for non-existent memory
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nArchived content")

        result = store.check_integrity()

        # Orphaned archives don't affect is_healthy
        assert "orphan_archive" in result["orphaned_archives"]

    def test_check_integrity_multiple_issues(self, store):
        """Check integrity detects multiple issues at once."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_file.md"
        orphan_path.write_text("---\nid: orphan_file\n---\nContent")

        # Create missing file in index
        index = store._read_index()
        index["memories"]["missing_file"] = {"topic": "Missing", "tags": [], "phase": 0}
        store._write_index(index)

        # Create orphaned stats
        stats = store._read_stats()
        stats["memories"]["orphan_stats"] = {"access_count": 1}
        store._write_stats(stats)

        result = store.check_integrity()

        assert result["is_healthy"] is False
        assert "orphan_file" in result["orphaned_files"]
        assert "missing_file" in result["missing_files"]
        assert "orphan_stats" in result["orphaned_stats"]


class TestIntegrityFix:
    """Tests for integrity fix functionality."""

    def test_fix_integrity_no_issues(self, store):
        """Fix integrity on healthy store does nothing."""
        store.create(topic="Memory", content="Content")

        result = store.fix_integrity()

        assert result["archived_files"] == 0
        assert result["removed_files"] == 0
        assert result["removed_index_entries"] == 0
        assert result["removed_stats_entries"] == 0

    def test_fix_integrity_removes_orphaned_file(self, store):
        """Fix integrity removes orphaned memory files."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nContent")

        result = store.fix_integrity(archive_orphans=False)

        assert result["removed_files"] == 1
        assert not orphan_path.exists()

    def test_fix_integrity_archives_orphaned_file(self, store):
        """Fix integrity archives orphaned files before removal."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nContent")

        result = store.fix_integrity(archive_orphans=True)

        assert result["archived_files"] == 1
        assert result["removed_files"] == 1
        assert not orphan_path.exists()
        # Check archive was created
        archive_path = store.archives_path / "orphan_mem.md"
        assert archive_path.exists()

    def test_fix_integrity_removes_missing_file_index_entry(self, store):
        """Fix integrity removes index entries for missing files."""
        # Create index entry without file
        index = store._read_index()
        index["memories"]["missing_mem"] = {
            "topic": "Missing",
            "tags": [],
            "phase": 0,
        }
        store._write_index(index)

        result = store.fix_integrity()

        assert result["removed_index_entries"] == 1
        # Verify index entry removed
        index = store._read_index()
        assert "missing_mem" not in index["memories"]

    def test_fix_integrity_removes_orphaned_stats(self, store):
        """Fix integrity removes orphaned stats entries."""
        # Create stats entry without index entry
        stats = store._read_stats()
        stats["memories"]["orphan_stats"] = {
            "access_count": 5,
            "priority": 0.5,
        }
        store._write_stats(stats)

        result = store.fix_integrity()

        assert result["removed_stats_entries"] == 1
        # Verify stats entry removed
        stats = store._read_stats()
        assert "orphan_stats" not in stats["memories"]

    def test_fix_integrity_multiple_issues(self, store):
        """Fix integrity handles multiple issues at once."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_file.md"
        orphan_path.write_text("---\nid: orphan_file\n---\nContent")

        # Create missing file in index
        index = store._read_index()
        index["memories"]["missing_file"] = {"topic": "Missing", "tags": [], "phase": 0}
        store._write_index(index)

        # Create orphaned stats
        stats = store._read_stats()
        stats["memories"]["orphan_stats"] = {"access_count": 1}
        store._write_stats(stats)

        result = store.fix_integrity()

        assert result["archived_files"] == 1
        assert result["removed_files"] == 1
        assert result["removed_index_entries"] == 1
        assert result["removed_stats_entries"] == 1

        # Verify all fixed
        check = store.check_integrity()
        assert check["is_healthy"] is True

    def test_fix_integrity_skips_existing_archive(self, store):
        """Fix integrity doesn't overwrite existing archive."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nNew Content")

        # Create existing archive with different content
        archive_path = store.archives_path / "orphan_mem.md"
        archive_path.write_text("---\nid: orphan_mem\n---\nOld Content")

        result = store.fix_integrity(archive_orphans=True)

        # File should be removed but archive not overwritten
        assert result["removed_files"] == 1
        assert not orphan_path.exists()
        # Archive should still have old content
        assert "Old Content" in archive_path.read_text()

    def test_fix_integrity_archive_exception(self, store, monkeypatch):
        """fix_integrity handles exception during archive gracefully."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nContent")

        # Make shutil.copy2 raise an exception
        import shutil

        original_copy2 = shutil.copy2

        def failing_copy2(src, dst):
            raise PermissionError("Cannot copy file")

        monkeypatch.setattr(shutil, "copy2", failing_copy2)

        result = store.fix_integrity(archive_orphans=True)

        # Archive should fail (archived_files stays 0)
        assert result["archived_files"] == 0
        # File should still be removed
        assert result["removed_files"] == 1
        assert not orphan_path.exists()

    def test_fix_integrity_remove_exception(self, store, monkeypatch):
        """fix_integrity handles exception during file removal gracefully."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nContent")

        # Make Path.unlink raise an exception
        from pathlib import Path

        original_unlink = Path.unlink

        def failing_unlink(self, *args, **kwargs):
            if "orphan_mem.md" in str(self):
                raise PermissionError("Cannot delete file")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", failing_unlink)

        result = store.fix_integrity(archive_orphans=False)

        # Remove should fail
        assert result["removed_files"] == 0
        # File should still exist
        assert orphan_path.exists()

    def test_fix_integrity_clean_orphaned_archives(self, store):
        """fix_integrity removes orphaned archives when requested."""
        # Create orphaned archive file
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nOld content")

        result = store.fix_integrity(clean_orphaned_archives=True)

        assert result["removed_orphaned_archives"] == 1
        assert not archive_path.exists()

    def test_fix_integrity_clean_orphaned_archives_default_false(self, store):
        """fix_integrity does not remove orphaned archives by default."""
        # Create orphaned archive file
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nOld content")

        result = store.fix_integrity()

        assert result["removed_orphaned_archives"] == 0
        assert archive_path.exists()

    def test_fix_integrity_clean_orphaned_archives_multiple(self, store):
        """fix_integrity removes multiple orphaned archives."""
        # Create multiple orphaned archive files
        for i in range(3):
            archive_path = store.archives_path / f"orphan_{i}.md"
            archive_path.write_text(f"---\nid: orphan_{i}\n---\nContent {i}")

        result = store.fix_integrity(clean_orphaned_archives=True)

        assert result["removed_orphaned_archives"] == 3
        for i in range(3):
            assert not (store.archives_path / f"orphan_{i}.md").exists()

    def test_fix_integrity_clean_orphaned_archives_exception(self, store, monkeypatch):
        """fix_integrity handles exception during archive removal gracefully."""
        # Create orphaned archive file
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nContent")

        # Make Path.unlink raise an exception
        from pathlib import Path

        original_unlink = Path.unlink

        def failing_unlink(self, *args, **kwargs):
            if "orphan_archive.md" in str(self):
                raise PermissionError("Cannot delete archive")
            return original_unlink(self, *args, **kwargs)

        monkeypatch.setattr(Path, "unlink", failing_unlink)

        result = store.fix_integrity(clean_orphaned_archives=True)

        # Remove should fail
        assert result["removed_orphaned_archives"] == 0
        # Archive should still exist
        assert archive_path.exists()
