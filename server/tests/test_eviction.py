"""Unit tests for eviction module."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from store import MemoryStore
from eviction import EvictionManager, EvictionConfig


@pytest.fixture
def temp_ltm_dir():
    """Create a temporary LTM directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="ltm_eviction_test_")
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
def eviction_manager(store):
    """Create an EvictionManager with default config."""
    return EvictionManager(store)


class TestEvictionConfig:
    """Tests for EvictionConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EvictionConfig()
        assert config.max_memories == 100
        assert config.batch_size == 10
        assert config.hint_max_chars == 200
        assert config.abstract_max_chars == 100

    def test_custom_config(self):
        """Test custom configuration values."""
        config = EvictionConfig(
            max_memories=50,
            batch_size=5,
            hint_max_chars=150,
            abstract_max_chars=75,
        )
        assert config.max_memories == 50
        assert config.batch_size == 5
        assert config.hint_max_chars == 150
        assert config.abstract_max_chars == 75


class TestEvictionManagerInit:
    """Tests for EvictionManager initialization."""

    def test_init_with_default_config(self, store):
        """Initialize with default config."""
        manager = EvictionManager(store)
        assert manager.store == store
        assert manager.config.max_memories == 100

    def test_init_with_custom_config(self, store):
        """Initialize with custom config."""
        config = EvictionConfig(max_memories=25)
        manager = EvictionManager(store, config)
        assert manager.config.max_memories == 25


class TestNeedsEviction:
    """Tests for needs_eviction method."""

    def test_needs_eviction_when_under_limit(self, store):
        """No eviction needed when under limit."""
        config = EvictionConfig(max_memories=10)
        manager = EvictionManager(store, config)

        # Create fewer memories than limit
        for i in range(5):
            store.create(topic=f"Memory {i}", content=f"Content {i}")

        assert not manager.needs_eviction()

    def test_needs_eviction_when_at_limit(self, store):
        """No eviction needed when exactly at limit."""
        config = EvictionConfig(max_memories=5)
        manager = EvictionManager(store, config)

        for i in range(5):
            store.create(topic=f"Memory {i}", content=f"Content {i}")

        assert not manager.needs_eviction()

    def test_needs_eviction_when_over_limit(self, store):
        """Eviction needed when over limit."""
        config = EvictionConfig(max_memories=5)
        manager = EvictionManager(store, config)

        for i in range(7):
            store.create(topic=f"Memory {i}", content=f"Content {i}")

        assert manager.needs_eviction()


class TestRunEviction:
    """Tests for run method."""

    def test_run_returns_stats(self, store):
        """Run returns eviction statistics."""
        config = EvictionConfig(max_memories=2, batch_size=2)
        manager = EvictionManager(store, config)

        for i in range(5):
            store.create(topic=f"Memory {i}", content=f"Content {i}", difficulty=0.1 * i)

        stats = manager.run()

        assert "processed" in stats
        assert "phase_transitions" in stats
        assert "archived" in stats
        assert "deleted" in stats

    def test_run_no_eviction_needed(self, store):
        """Run returns zeros when no eviction needed."""
        config = EvictionConfig(max_memories=10)
        manager = EvictionManager(store, config)

        store.create(topic="Single Memory", content="Content")

        stats = manager.run()

        assert stats["processed"] == 0
        assert stats["archived"] == 0

    def test_run_phase0_to_phase1(self, store):
        """Run transitions Phase 0 to Phase 1."""
        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Test", content="Original content")

        stats = manager.run()

        assert stats["phase_transitions"]["0_to_1"] >= 1

        # Verify phase changed
        index = store._read_index()
        assert index["memories"][mem_id]["phase"] == 1

    def test_run_phase1_to_phase2(self, store):
        """Run transitions Phase 1 to Phase 2."""
        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Test", content="Content")
        store.update(mem_id, phase=1)

        stats = manager.run()

        assert stats["phase_transitions"]["1_to_2"] >= 1

        index = store._read_index()
        assert index["memories"][mem_id]["phase"] == 2

    def test_run_phase2_to_phase3(self, store):
        """Run transitions Phase 2 to Phase 3 (deletion)."""
        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Test", content="Content")
        store.update(mem_id, phase=2)

        stats = manager.run()

        assert stats["phase_transitions"]["2_to_3"] >= 1
        assert stats["deleted"] >= 1

        # Verify deleted
        index = store._read_index()
        assert mem_id not in index["memories"]

    def test_run_skips_phase3(self, store):
        """Run skips memories already at Phase 3."""
        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Test", content="Content")
        store.update(mem_id, phase=3)

        stats = manager.run()

        # Should not process phase 3 memories
        assert stats["processed"] == 0

    def test_run_processes_batch_size(self, store):
        """Run processes only batch_size memories."""
        config = EvictionConfig(max_memories=0, batch_size=2)
        manager = EvictionManager(store, config)

        for i in range(5):
            store.create(topic=f"Memory {i}", content=f"Content {i}")

        stats = manager.run()

        # Should process only 2 (batch_size)
        assert stats["processed"] == 2

    def test_run_processes_lowest_priority_first(self, store):
        """Run evicts lowest priority memories first."""
        config = EvictionConfig(max_memories=2, batch_size=2)
        manager = EvictionManager(store, config)

        # Create memories with different priorities
        low_id = store.create(topic="Low Priority", content="Content", difficulty=0.1)
        high_id = store.create(topic="High Priority", content="Content", difficulty=0.9)
        mid_id = store.create(topic="Mid Priority", content="Content", difficulty=0.5)

        # Update stats with priorities
        stats = store._read_stats()
        stats["memories"][low_id] = {"priority": 0.1}
        stats["memories"][high_id] = {"priority": 0.9}
        stats["memories"][mid_id] = {"priority": 0.5}
        store._write_stats(stats)

        manager.run()

        # Low priority should be evicted first
        index = store._read_index()
        assert index["memories"][low_id]["phase"] > 0
        # High priority should remain at phase 0
        assert index["memories"][high_id]["phase"] == 0


class TestArchiveMemory:
    """Tests for _archive_memory method."""

    def test_archive_creates_file(self, store, eviction_manager):
        """Archive creates file in archives directory."""
        mem_id = store.create(topic="To Archive", content="Full content here")

        result = eviction_manager._archive_memory(mem_id)

        assert result is True
        archive_path = store.archives_path / f"{mem_id}.md"
        assert archive_path.exists()

    def test_archive_skips_existing(self, store, eviction_manager):
        """Archive skips if already archived."""
        mem_id = store.create(topic="Already Archived", content="Content")

        # Create archive first
        archive_path = store.archives_path / f"{mem_id}.md"
        archive_path.write_text("Existing archive content")

        result = eviction_manager._archive_memory(mem_id)

        assert result is False
        # Should not overwrite
        assert archive_path.read_text() == "Existing archive content"

    def test_archive_nonexistent_returns_false(self, store, eviction_manager):
        """Archive returns False for nonexistent memory."""
        result = eviction_manager._archive_memory("nonexistent_id")
        assert result is False


class TestReduceToHint:
    """Tests for _reduce_to_hint method."""

    def test_reduce_with_summary_section(self, store, eviction_manager):
        """Reduce keeps Summary section when present."""
        content = "## Summary\nBrief summary.\n\n## Content\nDetailed content here."
        mem_id = store.create(topic="Test", content=content)

        eviction_manager._reduce_to_hint(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "Brief summary" in memory["content"]
        assert "[Content reduced" in memory["content"]
        assert "Detailed content" not in memory["content"]

    def test_reduce_truncates_long_content(self, store):
        """Reduce truncates content over max chars."""
        config = EvictionConfig(hint_max_chars=50)
        manager = EvictionManager(store, config)

        long_content = "A" * 100
        mem_id = store.create(topic="Long", content=long_content)

        manager._reduce_to_hint(mem_id)

        memory = store.read(mem_id, update_stats=False)
        # Content should be truncated to 50 chars + suffix
        assert "A" * 100 not in memory["content"]
        assert "A" * 50 in memory["content"]
        assert "..." in memory["content"]
        assert "[Content reduced" in memory["content"]

    def test_reduce_keeps_short_content(self, store, eviction_manager):
        """Reduce keeps short content as-is."""
        short_content = "Short content"
        mem_id = store.create(topic="Short", content=short_content)

        eviction_manager._reduce_to_hint(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "Short content" in memory["content"]

    def test_reduce_nonexistent_does_not_raise(self, store, eviction_manager):
        """Reduce handles nonexistent memory gracefully."""
        # Should not raise
        eviction_manager._reduce_to_hint("nonexistent_id")


class TestReduceToAbstract:
    """Tests for _reduce_to_abstract method."""

    def test_reduce_extracts_first_line(self, store, eviction_manager):
        """Reduce extracts first non-header line."""
        content = "First line of content.\nSecond line here."
        mem_id = store.create(topic="Test", content=content)

        eviction_manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "First line of content" in memory["content"]
        assert "Abstract" in memory["content"]

    def test_reduce_skips_header_lines(self, store, eviction_manager):
        """Reduce skips lines starting with ##."""
        content = "## Header Line\nActual content here.\nMore content."
        mem_id = store.create(topic="Header", content=content)

        eviction_manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "Actual content here" in memory["content"]
        assert "Header Line" not in memory["content"]

    def test_reduce_truncates_long_first_line(self, store):
        """Reduce truncates first line over max chars."""
        config = EvictionConfig(abstract_max_chars=50)
        manager = EvictionManager(store, config)

        long_line = "A" * 100
        mem_id = store.create(topic="Long", content=long_line)

        manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "..." in memory["content"]

    def test_reduce_handles_empty_content(self, store, eviction_manager):
        """Reduce handles empty content."""
        mem_id = store.create(topic="Empty", content="")

        eviction_manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "Abstract" in memory["content"]

    def test_reduce_handles_header_only(self, store, eviction_manager):
        """Reduce handles content with only headers."""
        content = "## Header Only"
        mem_id = store.create(topic="HeaderOnly", content=content)

        eviction_manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "Abstract" in memory["content"]

    def test_reduce_nonexistent_does_not_raise(self, store, eviction_manager):
        """Reduce handles nonexistent memory gracefully."""
        # Should not raise
        eviction_manager._reduce_to_abstract("nonexistent_id")


class TestRestoreFromArchive:
    """Tests for restore_from_archive method."""

    def test_restore_success(self, store):
        """Restore memory from archive."""
        # Use custom config with small hint_max_chars to ensure reduction
        config = EvictionConfig(hint_max_chars=20)
        manager = EvictionManager(store, config)

        original_content = "Original full content that is long enough to be reduced"
        mem_id = store.create(topic="To Restore", content=original_content)

        # Archive and reduce
        manager._archive_memory(mem_id)
        manager._reduce_to_hint(mem_id)
        store.update(mem_id, phase=1)

        # Verify content was reduced
        memory = store.read(mem_id, update_stats=False)
        assert memory["content"] != original_content

        # Restore
        result = manager.restore_from_archive(mem_id)

        assert result is True
        memory = store.read(mem_id, update_stats=False)
        assert memory["content"] == original_content
        index = store._read_index()
        assert index["memories"][mem_id]["phase"] == 0

    def test_restore_nonexistent_archive(self, store, eviction_manager):
        """Restore returns False when archive doesn't exist."""
        mem_id = store.create(topic="No Archive", content="Content")

        result = eviction_manager.restore_from_archive(mem_id)

        assert result is False

    def test_restore_archive_without_frontmatter(self, store, eviction_manager):
        """Restore handles archive file without frontmatter."""
        mem_id = store.create(topic="No Frontmatter", content="Original")

        # Create archive without frontmatter (parser treats whole file as content)
        archive_path = store.archives_path / f"{mem_id}.md"
        archive_path.write_text("plain text content without frontmatter")

        result = eviction_manager.restore_from_archive(mem_id)

        # Should succeed - parser treats entire file as content
        assert result is True
        memory = store.read(mem_id, update_stats=False)
        assert memory["content"] == "plain text content without frontmatter"


class TestGetArchivedContent:
    """Tests for get_archived_content method."""

    def test_get_existing_archive(self, store, eviction_manager):
        """Get content from existing archive."""
        content = "Archived content here"
        mem_id = store.create(topic="Archived", content=content)
        eviction_manager._archive_memory(mem_id)

        result = eviction_manager.get_archived_content(mem_id)

        assert result == content

    def test_get_nonexistent_archive(self, store, eviction_manager):
        """Get returns None for nonexistent archive."""
        result = eviction_manager.get_archived_content("nonexistent_id")
        assert result is None


class TestListArchives:
    """Tests for list_archives method."""

    def test_list_empty(self, store, eviction_manager):
        """List returns empty when no archives."""
        result = eviction_manager.list_archives()
        assert result == []

    def test_list_archives(self, store, eviction_manager):
        """List returns all archived memory IDs."""
        # Create and archive some memories
        ids = []
        for i in range(3):
            mem_id = store.create(topic=f"Memory {i}", content=f"Content {i}")
            eviction_manager._archive_memory(mem_id)
            ids.append(mem_id)

        result = eviction_manager.list_archives()

        assert len(result) == 3
        for mem_id in ids:
            assert mem_id in result


class TestEvictionIntegration:
    """Integration tests for full eviction workflow."""

    def test_full_eviction_cycle(self, store):
        """Test complete eviction cycle from Phase 0 to deletion."""
        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        # Create a memory
        mem_id = store.create(
            topic="Full Cycle Test",
            content="## Summary\nBrief.\n\n## Content\nDetailed content here.",
        )

        # First eviction: Phase 0 -> 1
        stats1 = manager.run()
        assert stats1["phase_transitions"]["0_to_1"] == 1
        assert stats1["archived"] == 1

        index = store._read_index()
        assert index["memories"][mem_id]["phase"] == 1

        # Verify archive exists
        archive_path = store.archives_path / f"{mem_id}.md"
        assert archive_path.exists()

        # Second eviction: Phase 1 -> 2
        stats2 = manager.run()
        assert stats2["phase_transitions"]["1_to_2"] == 1

        index = store._read_index()
        assert index["memories"][mem_id]["phase"] == 2

        # Third eviction: Phase 2 -> 3 (deletion)
        stats3 = manager.run()
        assert stats3["phase_transitions"]["2_to_3"] == 1
        assert stats3["deleted"] == 1

        index = store._read_index()
        assert mem_id not in index["memories"]

        # Archive should still exist
        assert archive_path.exists()

    def test_restore_after_eviction(self, store):
        """Test restoring a memory after eviction."""
        config = EvictionConfig(max_memories=0, batch_size=1, hint_max_chars=50)
        manager = EvictionManager(store, config)

        # Use content longer than hint_max_chars to ensure reduction
        original_content = "A" * 100 + " Important content to preserve"
        mem_id = store.create(topic="Restorable", content=original_content)

        # Evict to Phase 1
        manager.run()

        # Verify content was reduced (should be truncated + suffix)
        memory = store.read(mem_id, update_stats=False)
        assert memory["content"] != original_content
        assert "[Content reduced" in memory["content"]

        # Restore from archive
        result = manager.restore_from_archive(mem_id)
        assert result is True

        # Verify original content restored
        memory = store.read(mem_id, update_stats=False)
        assert memory["content"] == original_content

        index = store._read_index()
        assert index["memories"][mem_id]["phase"] == 0


class TestRestoreEdgeCases:
    """Edge case tests for restore and get_archived_content."""

    def test_restore_empty_archive_content(self, store, eviction_manager, monkeypatch):
        """Restore returns False when archive parses to falsy value."""
        mem_id = store.create(topic="Test", content="Original")

        # Create archive file (content doesn't matter, we'll mock the parser)
        archive_path = store.archives_path / f"{mem_id}.md"
        archive_path.write_text("dummy")

        # Mock _parse_memory_file to return empty dict (falsy)
        def return_empty(*args, **kwargs):
            return {}

        monkeypatch.setattr(store, "_parse_memory_file", return_empty)

        result = eviction_manager.restore_from_archive(mem_id)

        # Empty dict is falsy, should return False
        assert result is False

    def test_restore_exception_during_update(self, store, eviction_manager, monkeypatch):
        """Restore returns False when update raises exception."""
        mem_id = store.create(topic="Test", content="Original")

        # Create valid archive
        eviction_manager._archive_memory(mem_id)

        # Make update raise an exception
        def failing_update(*args, **kwargs):
            raise RuntimeError("Simulated update failure")

        monkeypatch.setattr(store, "update", failing_update)

        result = eviction_manager.restore_from_archive(mem_id)

        assert result is False

    def test_get_archived_content_exception(self, store, eviction_manager, monkeypatch):
        """get_archived_content returns None on exception."""
        mem_id = store.create(topic="Test", content="Original")

        # Create archive
        eviction_manager._archive_memory(mem_id)

        # Make _parse_memory_file raise an exception
        def failing_parse(*args, **kwargs):
            raise RuntimeError("Simulated parse failure")

        monkeypatch.setattr(store, "_parse_memory_file", failing_parse)

        result = eviction_manager.get_archived_content(mem_id)

        assert result is None
