"""Integration tests for LTM hooks."""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
# Hooks are now in .claude/ltm_hooks (parent.parent.parent / ltm_hooks)
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ltm_hooks"))

from store import MemoryStore


@pytest.fixture
def temp_ltm_dir():
    """Create a temporary LTM directory for testing."""
    temp_dir = tempfile.mkdtemp(prefix="ltm_hooks_test_")
    temp_path = Path(temp_dir)

    # Create subdirectories
    (temp_path / "memories").mkdir()
    (temp_path / "archives").mkdir()
    (temp_path / "hooks").mkdir()

    yield temp_path

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def store(temp_ltm_dir):
    """Create a MemoryStore with temporary directory."""
    return MemoryStore(base_path=temp_ltm_dir)


class TestSessionStartHook:
    """Tests for session_start.py hook."""

    def test_session_start_increments_session(self, temp_ltm_dir, store):
        """SessionStart increments session counter."""
        import session_start

        # Patch the store to use temp directory
        with patch.object(session_start, "MemoryStore", lambda: store):
            # Simulate stdin with empty payload
            with patch("sys.stdin", io.StringIO("{}")):
                # Capture stdout
                with patch("sys.stdout", new_callable=io.StringIO):
                    session_start.main()

        # Verify session count incremented
        state = store._read_state()
        assert state["session_count"] == 2  # Started at 1, incremented to 2

    def test_session_start_initializes_current_session(self, temp_ltm_dir, store):
        """SessionStart initializes current session state."""
        import session_start

        with patch.object(session_start, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                with patch("sys.stdout", new_callable=io.StringIO):
                    session_start.main()

        state = store._read_state()
        session = state["current_session"]
        assert "started_at" in session
        assert session["tool_failures"] == 0
        assert session["tool_successes"] == 0
        assert session["compacted"] is False

    def test_session_start_outputs_memories(self, temp_ltm_dir, store):
        """SessionStart outputs memories to stdout."""
        import session_start

        # Create some memories
        store.create(topic="Test Memory 1", content="Content 1", tags=["test"])
        store.create(topic="Test Memory 2", content="Content 2", tags=["test"])

        with patch.object(session_start, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                output = io.StringIO()
                with patch("sys.stdout", output):
                    session_start.main()

        stdout_content = output.getvalue()
        assert "Long-Term Memory Context" in stdout_content
        assert "Test Memory 1" in stdout_content or "Test Memory 2" in stdout_content

    def test_session_start_handles_empty_memories(self, temp_ltm_dir, store):
        """SessionStart handles case with no memories."""
        import session_start

        with patch.object(session_start, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                output = io.StringIO()
                with patch("sys.stdout", output):
                    session_start.main()

        # Should not output anything if no memories
        stdout_content = output.getvalue()
        assert stdout_content == ""

    def test_session_start_handles_invalid_json(self, temp_ltm_dir, store):
        """SessionStart handles invalid JSON input gracefully."""
        import session_start

        with patch.object(session_start, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("invalid json")):
                with patch("sys.stdout", new_callable=io.StringIO):
                    # Should not raise
                    session_start.main()

        # Should still increment session
        state = store._read_state()
        assert state["session_count"] >= 1


class TestTrackDifficultyHook:
    """Tests for track_difficulty.py hook."""

    def test_track_difficulty_success(self, temp_ltm_dir, store):
        """Track successful tool use."""
        import track_difficulty

        # Initialize session state
        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Write",
            "tool_response": {"success": True},
        }

        with patch.object(track_difficulty, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO(json.dumps(payload))):
                track_difficulty.main()

        state = store._read_state()
        assert state["current_session"]["tool_successes"] == 1
        assert state["current_session"]["tool_failures"] == 0

    def test_track_difficulty_failure_error_key(self, temp_ltm_dir, store):
        """Track failed tool use with error key."""
        import track_difficulty

        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Bash",
            "tool_response": {"error": "command not found"},
        }

        with patch.object(track_difficulty, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO(json.dumps(payload))):
                track_difficulty.main()

        state = store._read_state()
        assert state["current_session"]["tool_failures"] == 1
        assert state["current_session"]["tool_successes"] == 0

    def test_track_difficulty_failure_success_false(self, temp_ltm_dir, store):
        """Track failed tool use with success: false."""
        import track_difficulty

        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Write",
            "tool_response": {"success": False},
        }

        with patch.object(track_difficulty, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO(json.dumps(payload))):
                track_difficulty.main()

        state = store._read_state()
        assert state["current_session"]["tool_failures"] == 1

    def test_track_difficulty_handles_invalid_json(self, temp_ltm_dir, store):
        """Track difficulty handles invalid JSON gracefully."""
        import track_difficulty

        with patch.object(track_difficulty, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("invalid")):
                # Should not raise
                track_difficulty.main()


class TestPreCompactHook:
    """Tests for pre_compact.py hook."""

    def test_pre_compact_marks_compaction(self, temp_ltm_dir, store):
        """PreCompact marks session as compacted."""
        import pre_compact

        state = store._read_state()
        state["current_session"] = {"compacted": False}
        store._write_state(state)

        with patch.object(pre_compact, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                pre_compact.main()

        state = store._read_state()
        assert state["current_session"]["compacted"] is True

    def test_pre_compact_increments_compaction_count(self, temp_ltm_dir, store):
        """PreCompact increments compaction counter."""
        import pre_compact

        state = store._read_state()
        state["compaction_count"] = 5
        state["current_session"] = {}
        store._write_state(state)

        with patch.object(pre_compact, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                pre_compact.main()

        state = store._read_state()
        assert state["compaction_count"] == 6

    def test_pre_compact_handles_invalid_json(self, temp_ltm_dir, store):
        """PreCompact handles invalid JSON gracefully."""
        import pre_compact

        with patch.object(pre_compact, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("invalid")):
                # Should not raise
                pre_compact.main()


class TestSessionEndHook:
    """Tests for session_end.py hook."""

    def test_session_end_resets_session_state(self, temp_ltm_dir, store):
        """SessionEnd resets current session state."""
        import session_end

        state = store._read_state()
        state["current_session"] = {
            "tool_failures": 5,
            "tool_successes": 10,
            "compacted": True,
        }
        store._write_state(state)

        with patch.object(session_end, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                session_end.main()

        state = store._read_state()
        assert state["current_session"] == {}

    def test_session_end_updates_priorities(self, temp_ltm_dir, store):
        """SessionEnd updates memory priorities."""
        import session_end

        # Create a memory
        mem_id = store.create(topic="Test", content="Content", difficulty=0.5)

        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 10}
        store._write_state(state)

        with patch.object(session_end, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                session_end.main()

        # Verify priority was updated
        stats = store._read_stats()
        assert mem_id in stats["memories"]
        assert "priority" in stats["memories"][mem_id]

    def test_session_end_handles_invalid_json(self, temp_ltm_dir, store):
        """SessionEnd handles invalid JSON gracefully."""
        import session_end

        with patch.object(session_end, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("invalid")):
                # Should not raise
                session_end.main()


class TestHookScripts:
    """Tests for running hooks as scripts."""

    def test_session_start_script_runs(self, temp_ltm_dir):
        """session_start.py runs without error."""
        import subprocess

        hook_path = Path(__file__).parent.parent.parent / "ltm_hooks" / "session_start.py"

        result = subprocess.run(
            ["python", str(hook_path)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=5,
            env={"LTM_DATA_PATH": str(temp_ltm_dir)},
        )

        assert result.returncode == 0

    def test_track_difficulty_script_runs(self, temp_ltm_dir):
        """track_difficulty.py runs without error."""
        import subprocess

        hook_path = Path(__file__).parent.parent.parent / "ltm_hooks" / "track_difficulty.py"

        payload = json.dumps({
            "tool_name": "Test",
            "tool_response": {"success": True},
        })

        result = subprocess.run(
            ["python", str(hook_path)],
            input=payload,
            capture_output=True,
            text=True,
            timeout=5,
            env={"LTM_DATA_PATH": str(temp_ltm_dir)},
        )

        assert result.returncode == 0

    def test_pre_compact_script_runs(self, temp_ltm_dir):
        """pre_compact.py runs without error."""
        import subprocess

        hook_path = Path(__file__).parent.parent.parent / "ltm_hooks" / "pre_compact.py"

        result = subprocess.run(
            ["python", str(hook_path)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=5,
            env={"LTM_DATA_PATH": str(temp_ltm_dir)},
        )

        assert result.returncode == 0

    def test_session_end_script_runs(self, temp_ltm_dir):
        """session_end.py runs without error."""
        import subprocess

        hook_path = Path(__file__).parent.parent.parent / "ltm_hooks" / "session_end.py"

        result = subprocess.run(
            ["python", str(hook_path)],
            input="{}",
            capture_output=True,
            text=True,
            timeout=5,
            env={"LTM_DATA_PATH": str(temp_ltm_dir)},
        )

        assert result.returncode == 0

    def test_hooks_complete_within_timeout(self, temp_ltm_dir):
        """All hooks complete within 5 second timeout."""
        import subprocess
        import time

        hooks = [
            "session_start.py",
            "track_difficulty.py",
            "pre_compact.py",
            "session_end.py",
        ]

        for hook_name in hooks:
            hook_path = Path(__file__).parent.parent.parent / "ltm_hooks" / hook_name

            start = time.time()
            result = subprocess.run(
                ["python", str(hook_path)],
                input="{}",
                capture_output=True,
                text=True,
                timeout=5,
                env={"LTM_DATA_PATH": str(temp_ltm_dir)},
            )
            elapsed = time.time() - start

            assert result.returncode == 0, f"{hook_name} failed: {result.stderr}"
            assert elapsed < 5, f"{hook_name} took {elapsed:.2f}s (> 5s timeout)"


class TestSessionEndEviction:
    """Tests for eviction via session_end.py hook."""

    def test_session_end_triggers_eviction(self, temp_ltm_dir, store):
        """SessionEnd triggers eviction when over threshold."""
        import session_end

        # Set low threshold
        state = store._read_state()
        state["config"] = {"max_memories": 3, "eviction_batch_size": 2}
        state["current_session"] = {}
        store._write_state(state)

        # Create more memories than threshold
        for i in range(5):
            store.create(
                topic=f"Memory {i}",
                content=f"Content {i}",
                difficulty=0.1 * i,  # Varying priority
            )

        with patch.object(session_end, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                session_end.main()

        # Verify some memories were evicted (phase changed)
        memories = store.list(limit=10)
        phases = [m["phase"] for m in memories]
        # At least some should have advanced phase
        assert any(p > 0 for p in phases) or len(memories) <= 3

    def test_eviction_archives_phase0_memories(self, temp_ltm_dir, store):
        """Eviction archives Phase 0 memories before reducing."""
        import session_end

        # Create a memory
        mem_id = store.create(
            topic="To Archive",
            content="## Summary\nThis is the summary.\n\n## Content\nThis is the detailed content.",
            difficulty=0.1,
        )

        # Set very low threshold to trigger eviction
        state = store._read_state()
        state["config"] = {"max_memories": 0, "eviction_batch_size": 1}
        state["current_session"] = {}
        store._write_state(state)

        with patch.object(session_end, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                session_end.main()

        # Check archive was created
        archive_path = store.archives_path / f"{mem_id}.md"
        assert archive_path.exists()

    def test_reduce_to_hint(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_hint method."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        mem_id = store.create(
            topic="Test",
            content="## Summary\nBrief summary.\n\n## Content\nDetailed content here.",
        )

        manager._reduce_to_hint(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "Brief summary" in memory["content"]
        assert "[Content reduced" in memory["content"]

    def test_reduce_to_abstract(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_abstract method."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        mem_id = store.create(
            topic="Test",
            content="This is the first line of content.\nSecond line here.",
        )

        manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert "Abstract" in memory["content"]
        assert "[Full content archived]" in memory["content"]

    def test_archive_memory(self, temp_ltm_dir, store):
        """Test EvictionManager._archive_memory method."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        mem_id = store.create(topic="To Archive", content="Full content")

        manager._archive_memory(mem_id)

        archive_path = store.archives_path / f"{mem_id}.md"
        assert archive_path.exists()

    def test_archive_memory_skips_existing(self, temp_ltm_dir, store):
        """EvictionManager._archive_memory skips if archive already exists."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        mem_id = store.create(topic="Already Archived", content="Content")

        # Create archive first
        archive_path = store.archives_path / f"{mem_id}.md"
        archive_path.write_text("Existing archive")

        manager._archive_memory(mem_id)

        # Should not overwrite
        assert archive_path.read_text() == "Existing archive"

    def test_run_eviction_handles_phase3(self, temp_ltm_dir, store):
        """EvictionManager.run skips phase 3 memories."""
        from eviction import EvictionManager, EvictionConfig

        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Phase 3", content="Content")
        store.update(mem_id, phase=3)

        manager.run()

        # Memory should still be at phase 3 (not processed)
        index = store._read_index()
        if mem_id in index["memories"]:
            assert index["memories"][mem_id]["phase"] == 3


class TestSessionStartWithContent:
    """Additional tests for session_start with full content."""

    def test_session_start_reads_full_content_for_phase0(self, temp_ltm_dir, store):
        """SessionStart reads full content for phase 0 memories."""
        import session_start

        # Create a phase 0 memory with content
        store.create(
            topic="Detailed Memory",
            content="This is detailed content that should be shown.",
            tags=["important"],
        )

        with patch.object(session_start, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                output = io.StringIO()
                with patch("sys.stdout", output):
                    session_start.main()

        stdout_content = output.getvalue()
        assert "Detailed Memory" in stdout_content
        # Content should be included for phase 0
        assert "detailed content" in stdout_content.lower() or "This is" in stdout_content

    def test_session_start_truncates_long_content(self, temp_ltm_dir, store):
        """SessionStart truncates content longer than 500 characters."""
        import session_start

        # Create a memory with content > 500 characters
        long_content = "A" * 600
        store.create(
            topic="Long Memory",
            content=long_content,
            tags=["test"],
        )

        with patch.object(session_start, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                output = io.StringIO()
                with patch("sys.stdout", output):
                    session_start.main()

        stdout_content = output.getvalue()
        assert "Long Memory" in stdout_content
        # Content should be truncated with ...
        assert "..." in stdout_content
        # Should not contain full 600 A's
        assert "A" * 600 not in stdout_content

    def test_session_start_handles_read_exception(self, temp_ltm_dir, store):
        """SessionStart handles exception when reading memory content."""
        import session_start

        # Create a memory
        mem_id = store.create(
            topic="Broken Memory",
            content="Original content",
            tags=["test"],
        )

        # Delete the memory file to cause a read exception
        memory_path = store.memories_path / f"{mem_id}.md"
        memory_path.unlink()

        with patch.object(session_start, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                output = io.StringIO()
                with patch("sys.stdout", output):
                    # Should not raise
                    session_start.main()

        stdout_content = output.getvalue()
        # Should still output the memory header from index
        assert "Broken Memory" in stdout_content


class TestTrackDifficultyEdgeCases:
    """Additional edge case tests for track_difficulty."""

    def test_track_difficulty_error_in_text(self, temp_ltm_dir, store):
        """Track failure when Error in response text."""
        import track_difficulty

        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Bash",
            "tool_response": {"text": "Error: command failed"},
        }

        with patch.object(track_difficulty, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO(json.dumps(payload))):
                track_difficulty.main()

        state = store._read_state()
        assert state["current_session"]["tool_failures"] == 1


class TestSessionEndEvictionEdgeCases:
    """Edge case tests for eviction via session_end.py."""

    def test_stats_without_index_entry_skipped(self, temp_ltm_dir, store):
        """Memory in stats but not in index is skipped."""
        import session_end

        # Create a memory
        mem_id = store.create(topic="Test", content="Content")

        # Manually add an orphaned entry in stats (no corresponding index entry)
        stats = store._read_stats()
        stats["memories"]["orphan_id"] = {"access_count": 1, "last_session": 1}
        store._write_stats(stats)

        state = store._read_state()
        state["current_session"] = {}
        store._write_state(state)

        with patch.object(session_end, "MemoryStore", lambda: store):
            with patch("sys.stdin", io.StringIO("{}")):
                # Should not raise
                session_end.main()

    def test_phase1_to_phase2_transition(self, temp_ltm_dir, store):
        """Test Phase 1 → Phase 2 eviction transition."""
        from eviction import EvictionManager, EvictionConfig

        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Phase 1 Memory", content="Some content")
        store.update(mem_id, phase=1)

        manager.run()

        # Should now be phase 2
        index = store._read_index()
        assert index["memories"][mem_id]["phase"] == 2

    def test_phase2_to_phase3_transition(self, temp_ltm_dir, store):
        """Test Phase 2 → Phase 3 eviction (deletion)."""
        from eviction import EvictionManager, EvictionConfig

        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Phase 2 Memory", content="Content")
        store.update(mem_id, phase=2)

        manager.run()

        # Memory should be deleted
        index = store._read_index()
        assert mem_id not in index["memories"]

    def test_reduce_to_hint_long_content_no_summary(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_hint with long content and no ## Summary."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        long_content = "A" * 300  # More than 200 characters
        mem_id = store.create(topic="Long Memory", content=long_content)

        manager._reduce_to_hint(mem_id)

        memory = store.read(mem_id, update_stats=False)
        assert len(memory["content"]) < 300
        assert "[Content reduced" in memory["content"]
        assert "..." in memory["content"]

    def test_reduce_to_hint_short_content_no_summary(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_hint with short content and no ## Summary."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        short_content = "Short content"  # Less than 200 characters
        mem_id = store.create(topic="Short Memory", content=short_content)

        manager._reduce_to_hint(mem_id)

        memory = store.read(mem_id, update_stats=False)
        # Should keep the short content as-is
        assert "Short content" in memory["content"]

    def test_reduce_to_abstract_header_line(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_abstract when first line is a header."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        content = "## Header Line\nActual content here.\nMore content."
        mem_id = store.create(topic="Header Memory", content=content)

        manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        # Should skip the header and use the second line
        assert "Actual content here" in memory["content"]

    def test_reduce_to_abstract_long_first_line(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_abstract with a first line > 100 chars."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        long_line = "A" * 150  # More than 100 characters
        mem_id = store.create(topic="Long Line Memory", content=long_line)

        manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        # Should be truncated with ...
        assert "..." in memory["content"]
        assert len(memory["content"]) < 200

    def test_reduce_to_abstract_header_only(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_abstract when content is only a header."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        content = "## Header Only"
        mem_id = store.create(topic="Header Only Memory", content=content)

        manager._reduce_to_abstract(mem_id)

        memory = store.read(mem_id, update_stats=False)
        # Should produce abstract with empty first line
        assert "Abstract" in memory["content"]

    def test_archive_memory_exception_handling(self, temp_ltm_dir, store):
        """Test EvictionManager._archive_memory handles read exceptions gracefully."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        # Try to archive a non-existent memory
        result = manager._archive_memory("nonexistent_id")

        # Should return False, archive should not exist
        assert result is False
        archive_path = store.archives_path / "nonexistent_id.md"
        assert not archive_path.exists()

    def test_reduce_to_hint_exception_handling(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_hint handles exceptions gracefully."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        # Try to reduce a non-existent memory - should not raise
        manager._reduce_to_hint("nonexistent_id")

    def test_reduce_to_abstract_exception_handling(self, temp_ltm_dir, store):
        """Test EvictionManager._reduce_to_abstract handles exceptions gracefully."""
        from eviction import EvictionManager

        manager = EvictionManager(store)
        # Try to reduce a non-existent memory - should not raise
        manager._reduce_to_abstract("nonexistent_id")

    def test_run_eviction_exception_in_phase_transition(self, temp_ltm_dir, store):
        """Test EvictionManager.run handles exceptions during phase transitions."""
        from eviction import EvictionManager, EvictionConfig

        config = EvictionConfig(max_memories=0, batch_size=1)
        manager = EvictionManager(store, config)

        mem_id = store.create(topic="Test", content="Content")

        # Delete the memory file to cause an exception during processing
        memory_path = store.memories_path / f"{mem_id}.md"
        memory_path.unlink()

        # Should not raise
        manager.run()
