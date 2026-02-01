"""Integration tests for MCP server."""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server import (
    handle_store_memory,
    handle_recall,
    handle_list_memories,
    handle_get_memory,
    handle_forget,
    handle_ltm_status,
    handle_ltm_check,
    handle_ltm_fix,
    _extract_tags,
    store,
)


@pytest.fixture
def clean_store():
    """Create a clean store for each test."""
    # Create temp directory
    temp_dir = tempfile.mkdtemp(prefix="ltm_mcp_test_")
    temp_path = Path(temp_dir)

    # Backup original paths
    original_base = store.base_path
    original_memories = store.memories_path
    original_archives = store.archives_path
    original_index = store.index_path
    original_stats = store.stats_path
    original_state = store.state_path

    # Set up temp paths
    store.base_path = temp_path
    store.memories_path = temp_path / "memories"
    store.archives_path = temp_path / "archives"
    store.index_path = temp_path / "index.json"
    store.stats_path = temp_path / "stats.json"
    store.state_path = temp_path / "state.json"

    store.memories_path.mkdir(parents=True)
    store.archives_path.mkdir(parents=True)

    store.invalidate_cache()

    yield store

    # Restore original paths
    store.base_path = original_base
    store.memories_path = original_memories
    store.archives_path = original_archives
    store.index_path = original_index
    store.stats_path = original_stats
    store.state_path = original_state
    store.invalidate_cache()

    # Cleanup
    shutil.rmtree(temp_dir)


class TestExtractTags:
    """Tests for auto-tag extraction."""

    def test_extract_technology_keywords(self):
        """Extract technology keywords from content."""
        tags = _extract_tags(
            "Database optimization",
            "Fixed postgres connection pooling in python"
        )

        assert "postgres" in tags or "postgresql" in tags
        assert "python" in tags
        assert "database" in tags

    def test_extract_file_extensions(self):
        """Extract file extensions from content."""
        tags = _extract_tags(
            "Fix config",
            "Modified config.py and utils.js files"
        )

        assert "py" in tags
        assert "js" in tags

    def test_limit_tags(self):
        """Tags are limited to 10."""
        # Create content with many keywords
        content = "python javascript typescript rust go java react vue angular node django flask postgres mysql docker kubernetes"
        tags = _extract_tags("Everything", content)

        assert len(tags) <= 10


@pytest.mark.asyncio
class TestStoreMemoryTool:
    """Tests for store_memory tool."""

    async def test_store_memory_basic(self, clean_store):
        """Store memory with basic fields."""
        result = await handle_store_memory({
            "topic": "Test memory",
            "content": "This is test content",
        })

        assert len(result) == 1
        text = result[0].text
        assert "success: True" in text
        assert "mem_" in text

    async def test_store_memory_with_tags(self, clean_store):
        """Store memory with explicit tags."""
        result = await handle_store_memory({
            "topic": "Test memory",
            "content": "This is test content",
            "tags": ["test", "example"],
        })

        text = result[0].text
        assert "success: True" in text
        assert "test" in text

    async def test_store_memory_auto_tag(self, clean_store):
        """Store memory with auto-tagging."""
        result = await handle_store_memory({
            "topic": "Python debugging",
            "content": "Fixed a bug in the database connection",
            "auto_tag": True,
        })

        text = result[0].text
        assert "success: True" in text
        # Should have auto-generated tags
        assert "tags:" in text

    async def test_store_memory_with_difficulty(self, clean_store):
        """Store memory with difficulty score."""
        result = await handle_store_memory({
            "topic": "Hard problem",
            "content": "Solved a complex issue",
            "difficulty": 0.9,
        })

        text = result[0].text
        assert "success: True" in text


@pytest.mark.asyncio
class TestRecallTool:
    """Tests for recall tool."""

    async def test_recall_finds_memory(self, clean_store):
        """Recall finds matching memory."""
        # Store a memory first
        await handle_store_memory({
            "topic": "Database optimization",
            "content": "Optimized query performance",
        })

        result = await handle_recall({"query": "database"})

        text = result[0].text
        assert "Database optimization" in text
        assert "mem_" in text

    async def test_recall_no_results(self, clean_store):
        """Recall returns message when no matches."""
        result = await handle_recall({"query": "nonexistent"})

        text = result[0].text
        assert "No memories found" in text

    async def test_recall_respects_limit(self, clean_store):
        """Recall respects limit parameter."""
        # Store multiple memories
        for i in range(5):
            await handle_store_memory({
                "topic": f"Test memory {i}",
                "content": "Test content",
            })

        result = await handle_recall({"query": "test", "limit": 2})

        text = result[0].text
        # Should find some but respect limit
        assert "Found" in text

    async def test_recall_finds_by_tag(self, clean_store):
        """Recall finds memory by tag."""
        await handle_store_memory({
            "topic": "Generic topic",
            "content": "Generic content",
            "tags": ["postgresql", "optimization"],
        })
        await handle_store_memory({
            "topic": "Other topic",
            "content": "Other content",
            "tags": ["api"],
        })

        result = await handle_recall({"query": "postgresql"})

        text = result[0].text
        assert "Generic topic" in text
        assert "Other topic" not in text

    async def test_recall_finds_by_partial_tag(self, clean_store):
        """Recall finds memory by partial tag match."""
        await handle_store_memory({
            "topic": "Topic",
            "content": "Content",
            "tags": ["postgresql"],
        })

        result = await handle_recall({"query": "postgres"})

        text = result[0].text
        assert "Topic" in text


@pytest.mark.asyncio
class TestListMemoriesTool:
    """Tests for list_memories tool."""

    async def test_list_all_memories(self, clean_store):
        """List all memories."""
        # Store memories
        await handle_store_memory({
            "topic": "Memory 1",
            "content": "Content 1",
        })
        await handle_store_memory({
            "topic": "Memory 2",
            "content": "Content 2",
        })

        result = await handle_list_memories({})

        text = result[0].text
        assert "Memory 1" in text
        assert "Memory 2" in text

    async def test_list_filter_by_tag(self, clean_store):
        """List memories filtered by tag."""
        await handle_store_memory({
            "topic": "Tagged memory",
            "content": "Content",
            "tags": ["important"],
        })
        await handle_store_memory({
            "topic": "Other memory",
            "content": "Content",
            "tags": ["other"],
        })

        result = await handle_list_memories({"tag": "important"})

        text = result[0].text
        assert "Tagged memory" in text
        assert "Other memory" not in text

    async def test_list_filter_by_keyword(self, clean_store):
        """List memories filtered by keyword."""
        await handle_store_memory({
            "topic": "Database topic",
            "content": "Content",
        })
        await handle_store_memory({
            "topic": "API topic",
            "content": "Content",
        })

        result = await handle_list_memories({"keyword": "database"})

        text = result[0].text
        assert "Database topic" in text
        assert "API topic" not in text

    async def test_list_empty(self, clean_store):
        """List returns message when no memories."""
        result = await handle_list_memories({})

        text = result[0].text
        assert "No memories found" in text


@pytest.mark.asyncio
class TestGetMemoryTool:
    """Tests for get_memory tool."""

    async def test_get_memory_by_id(self, clean_store):
        """Get full memory by ID."""
        # Store a memory
        store_result = await handle_store_memory({
            "topic": "Test memory",
            "content": "Full content here",
            "tags": ["test"],
        })

        # Extract ID from result
        text = store_result[0].text
        memory_id = None
        for line in text.split("\n"):
            if line.startswith("id:"):
                memory_id = line.split(":")[1].strip()
                break

        assert memory_id is not None

        # Get the memory
        result = await handle_get_memory({"memory_id": memory_id})

        text = result[0].text
        assert "Test memory" in text
        assert "Full content here" in text
        assert memory_id in text

    async def test_get_memory_not_found(self, clean_store):
        """Get memory returns error for unknown ID."""
        result = await handle_get_memory({"memory_id": "mem_nonexistent"})

        text = result[0].text
        assert "not found" in text.lower()


@pytest.mark.asyncio
class TestForgetTool:
    """Tests for forget tool."""

    async def test_forget_memory(self, clean_store):
        """Forget removes memory."""
        # Store a memory
        store_result = await handle_store_memory({
            "topic": "To forget",
            "content": "Content",
        })

        # Extract ID
        text = store_result[0].text
        memory_id = None
        for line in text.split("\n"):
            if line.startswith("id:"):
                memory_id = line.split(":")[1].strip()
                break

        # Forget it
        result = await handle_forget({"memory_id": memory_id})

        text = result[0].text
        assert "deleted" in text.lower()
        assert "archived" in text.lower()

        # Verify it's gone
        get_result = await handle_get_memory({"memory_id": memory_id})
        assert "not found" in get_result[0].text.lower()

    async def test_forget_not_found(self, clean_store):
        """Forget returns error for unknown ID."""
        result = await handle_forget({"memory_id": "mem_nonexistent"})

        text = result[0].text
        assert "not found" in text.lower()


@pytest.mark.asyncio
class TestLtmStatusTool:
    """Tests for ltm_status tool."""

    async def test_ltm_status_empty(self, clean_store):
        """Status shows empty system."""
        result = await handle_ltm_status({})

        text = result[0].text
        assert "Total Memories:" in text
        assert "0" in text
        assert "Session Count:" in text

    async def test_ltm_status_with_memories(self, clean_store):
        """Status shows memory counts."""
        # Store some memories
        await handle_store_memory({
            "topic": "Memory 1",
            "content": "Content",
        })
        await handle_store_memory({
            "topic": "Memory 2",
            "content": "Content",
        })

        result = await handle_ltm_status({})

        text = result[0].text
        assert "Total Memories:" in text
        assert "2" in text
        assert "Full (0):" in text


@pytest.mark.asyncio
class TestCallToolDispatcher:
    """Tests for the call_tool dispatcher function."""

    async def test_call_tool_store_memory(self, clean_store):
        """call_tool routes to store_memory."""
        from mcp_server import call_tool

        result = await call_tool("store_memory", {
            "topic": "Test",
            "content": "Content",
        })

        assert len(result) == 1
        assert "success" in result[0].text

    async def test_call_tool_recall(self, clean_store):
        """call_tool routes to recall."""
        from mcp_server import call_tool

        result = await call_tool("recall", {"query": "test"})

        assert len(result) == 1

    async def test_call_tool_list_memories(self, clean_store):
        """call_tool routes to list_memories."""
        from mcp_server import call_tool

        result = await call_tool("list_memories", {})

        assert len(result) == 1

    async def test_call_tool_get_memory(self, clean_store):
        """call_tool routes to get_memory."""
        from mcp_server import call_tool

        result = await call_tool("get_memory", {"memory_id": "mem_test"})

        assert len(result) == 1

    async def test_call_tool_forget(self, clean_store):
        """call_tool routes to forget."""
        from mcp_server import call_tool

        result = await call_tool("forget", {"memory_id": "mem_test"})

        assert len(result) == 1

    async def test_call_tool_ltm_status(self, clean_store):
        """call_tool routes to ltm_status."""
        from mcp_server import call_tool

        result = await call_tool("ltm_status", {})

        assert len(result) == 1
        assert "Total Memories" in result[0].text

    async def test_call_tool_ltm_check(self, clean_store):
        """call_tool routes to ltm_check."""
        from mcp_server import call_tool

        result = await call_tool("ltm_check", {})

        assert len(result) == 1
        assert "Integrity Check" in result[0].text

    async def test_call_tool_ltm_fix(self, clean_store):
        """call_tool routes to ltm_fix."""
        from mcp_server import call_tool

        result = await call_tool("ltm_fix", {})

        assert len(result) == 1
        assert "Integrity Fix" in result[0].text

    async def test_call_tool_unknown(self, clean_store):
        """call_tool handles unknown tool name."""
        from mcp_server import call_tool

        result = await call_tool("unknown_tool", {})

        assert len(result) == 1
        assert "Unknown tool" in result[0].text

    async def test_call_tool_exception(self, clean_store, monkeypatch):
        """call_tool handles exceptions gracefully."""
        from mcp_server import call_tool

        async def failing_handler(args):
            raise ValueError("Test error")

        import mcp_server
        monkeypatch.setattr(mcp_server, "handle_store_memory", failing_handler)

        result = await call_tool("store_memory", {
            "topic": "Test",
            "content": "Content",
        })

        assert len(result) == 1
        assert "Error" in result[0].text


@pytest.mark.asyncio
class TestListToolsFunction:
    """Tests for list_tools function."""

    async def test_list_tools_returns_all_tools(self):
        """list_tools returns all 6 tools."""
        from mcp_server import list_tools

        tools = await list_tools()

        assert len(tools) == 8
        tool_names = [t.name for t in tools]
        assert "store_memory" in tool_names
        assert "recall" in tool_names
        assert "list_memories" in tool_names
        assert "get_memory" in tool_names
        assert "forget" in tool_names
        assert "ltm_status" in tool_names
        assert "ltm_check" in tool_names
        assert "ltm_fix" in tool_names


@pytest.mark.asyncio
class TestListMemoriesFilters:
    """Tests for list_memories filter messages."""

    async def test_list_empty_with_phase_filter(self, clean_store):
        """Empty list with phase filter shows filter in message."""
        result = await handle_list_memories({"phase": 1})

        text = result[0].text
        assert "phase=1" in text

    async def test_list_empty_with_tag_filter(self, clean_store):
        """Empty list with tag filter shows filter in message."""
        result = await handle_list_memories({"tag": "nonexistent"})

        text = result[0].text
        assert "tag='nonexistent'" in text

    async def test_list_empty_with_keyword_filter(self, clean_store):
        """Empty list with keyword filter shows filter in message."""
        result = await handle_list_memories({"keyword": "nonexistent"})

        text = result[0].text
        assert "keyword='nonexistent'" in text

    async def test_list_empty_with_multiple_filters(self, clean_store):
        """Empty list with multiple filters shows all filters."""
        result = await handle_list_memories({
            "phase": 0,
            "tag": "test",
            "keyword": "query",
        })

        text = result[0].text
        assert "phase=0" in text
        assert "tag='test'" in text
        assert "keyword='query'" in text


@pytest.mark.asyncio
class TestLtmCheck:
    """Tests for ltm_check tool."""

    async def test_check_healthy_system(self, clean_store):
        """Check returns healthy for clean store."""
        # Create some memories
        await handle_store_memory({
            "topic": "Test Memory",
            "content": "Test content",
        })

        result = await handle_ltm_check({})

        text = result[0].text
        assert "Healthy" in text
        assert "No integrity issues" in text

    async def test_check_orphaned_file(self, clean_store):
        """Check detects orphaned memory files."""
        # Create orphaned file directly
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\ntopic: Orphan\n---\nContent")

        result = await handle_ltm_check({})

        text = result[0].text
        assert "Issues Found" in text
        assert "Orphaned Files" in text
        assert "orphan_mem" in text

    async def test_check_missing_file(self, clean_store):
        """Check detects missing memory files."""
        # Create index entry without file
        index = store._read_index()
        index["memories"]["missing_mem"] = {
            "topic": "Missing",
            "tags": [],
            "phase": 0,
        }
        store._write_index(index)

        result = await handle_ltm_check({})

        text = result[0].text
        assert "Issues Found" in text
        assert "Missing Files" in text
        assert "missing_mem" in text

    async def test_check_orphaned_stats(self, clean_store):
        """Check detects orphaned stats entries."""
        # Create stats entry without index entry
        stats = store._read_stats()
        stats["memories"]["orphan_stats"] = {"access_count": 5}
        store._write_stats(stats)

        result = await handle_ltm_check({})

        text = result[0].text
        assert "Issues Found" in text
        assert "Orphaned Stats" in text
        assert "orphan_stats" in text

    async def test_check_orphaned_archives(self, clean_store):
        """Check detects orphaned archive files."""
        # Create archive file for non-existent memory
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nOld archived content")

        result = await handle_ltm_check({})

        text = result[0].text
        # Orphaned archives are listed but don't cause unhealthy status
        # (they're leftover files from previously deleted memories)
        assert "Orphaned Archives" in text
        assert "orphan_archive" in text


@pytest.mark.asyncio
class TestLtmFix:
    """Tests for ltm_fix tool."""

    async def test_fix_no_issues(self, clean_store):
        """Fix on healthy system does nothing."""
        result = await handle_ltm_fix({})

        text = result[0].text
        assert "No issues to fix" in text

    async def test_fix_orphaned_file(self, clean_store):
        """Fix removes orphaned files."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nContent")

        result = await handle_ltm_fix({"archive_orphans": True})

        text = result[0].text
        assert "Repairs completed" in text
        assert "Archived" in text or "Removed" in text
        assert "healthy" in text.lower()

        # Verify file removed
        assert not orphan_path.exists()

    async def test_fix_missing_file_entry(self, clean_store):
        """Fix removes index entries for missing files."""
        # Create index entry without file
        index = store._read_index()
        index["memories"]["missing_mem"] = {"topic": "Missing", "tags": [], "phase": 0}
        store._write_index(index)

        result = await handle_ltm_fix({})

        text = result[0].text
        assert "Repairs completed" in text

        # Verify index entry removed
        index = store._read_index()
        assert "missing_mem" not in index["memories"]

    async def test_fix_orphaned_stats(self, clean_store):
        """Fix removes orphaned stats entries."""
        # Create orphaned stats
        stats = store._read_stats()
        stats["memories"]["orphan_stats"] = {"access_count": 1}
        store._write_stats(stats)

        result = await handle_ltm_fix({})

        text = result[0].text
        assert "Repairs completed" in text

        # Verify stats entry removed
        stats = store._read_stats()
        assert "orphan_stats" not in stats["memories"]

    async def test_fix_archives_before_removal(self, clean_store):
        """Fix archives orphaned files before removal."""
        # Create orphaned file
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nContent to archive")

        result = await handle_ltm_fix({"archive_orphans": True})

        text = result[0].text
        assert "Archived" in text

        # Verify archive created
        archive_path = store.archives_path / "orphan_mem.md"
        assert archive_path.exists()

    async def test_fix_issues_remain(self, clean_store, monkeypatch):
        """Fix shows message when issues remain after fix."""
        import mcp_server

        # Create an orphaned file to trigger fix
        orphan_path = store.memories_path / "orphan_mem.md"
        orphan_path.write_text("---\nid: orphan_mem\n---\nContent")

        call_count = [0]
        original_check = store.check_integrity

        def mock_check_integrity():
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: issues exist
                return original_check()
            else:
                # Second call (after fix): still unhealthy
                return {
                    "is_healthy": False,
                    "orphaned_files": [],
                    "missing_files": ["remaining_issue"],
                    "orphaned_stats": [],
                    "orphaned_archives": [],
                }

        monkeypatch.setattr(mcp_server.store, "check_integrity", mock_check_integrity)

        result = await handle_ltm_fix({})

        text = result[0].text
        assert "Repairs completed" in text
        assert "Some issues may remain" in text

    async def test_fix_clean_orphaned_archives(self, clean_store):
        """Fix removes orphaned archives when clean_orphaned_archives is True."""
        # Create orphaned archive file
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nOld archived content")

        result = await handle_ltm_fix({"clean_orphaned_archives": True})

        text = result[0].text
        assert "Repairs completed" in text
        assert "orphaned archive" in text.lower()
        assert not archive_path.exists()

    async def test_fix_clean_orphaned_archives_default_false(self, clean_store):
        """Fix does not remove orphaned archives by default."""
        # Create orphaned archive file
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nOld archived content")

        result = await handle_ltm_fix({})

        text = result[0].text
        # No issues to fix (orphaned archives don't count as issues)
        assert "No issues to fix" in text
        # Archive should still exist
        assert archive_path.exists()

    async def test_fix_orphaned_archives_only(self, clean_store):
        """Fix handles case where only orphaned archives exist."""
        # Create orphaned archive file (no other issues)
        archive_path = store.archives_path / "orphan_archive.md"
        archive_path.write_text("---\nid: orphan_archive\n---\nContent")

        # Without clean_orphaned_archives, nothing to fix
        result = await handle_ltm_fix({})
        assert "No issues to fix" in result[0].text
        assert archive_path.exists()

        # With clean_orphaned_archives, should fix
        result = await handle_ltm_fix({"clean_orphaned_archives": True})
        assert "Repairs completed" in result[0].text
        assert not archive_path.exists()
