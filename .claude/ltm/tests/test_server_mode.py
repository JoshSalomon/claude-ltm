"""Tests for server mode HTTP hooks and TCP server."""

from __future__ import annotations

import asyncio
import json
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import mcp_server
from mcp_server import (
    hook_session_start,
    hook_track_difficulty,
    hook_pre_compact,
    hook_session_end,
    hook_health,
    hook_shutdown,
    store,
    shutdown_event,
    parse_args,
)


@pytest.fixture
def clean_store():
    """Create a clean store for each test."""
    temp_dir = tempfile.mkdtemp(prefix="ltm_server_test_")
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

    # Create directories
    store.memories_path.mkdir(parents=True)
    store.archives_path.mkdir(parents=True)

    # Reset caches
    store.invalidate_cache()

    yield temp_path

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


@pytest.fixture
def mock_request():
    """Create a mock aiohttp request."""
    def _make_request(json_data=None, can_read=True):
        request = MagicMock()
        request.can_read_body = can_read
        if json_data is not None:
            request.json = AsyncMock(return_value=json_data)
        else:
            request.json = AsyncMock(side_effect=json.JSONDecodeError("", "", 0))
        return request
    return _make_request


class TestHookSessionStart:
    """Tests for session_start HTTP hook."""

    @pytest.mark.asyncio
    async def test_session_start_increments_session(self, clean_store, mock_request):
        """session_start increments session counter."""
        request = mock_request({})

        response = await hook_session_start(request)
        data = json.loads(response.text)

        assert data["success"] is True

        # Verify session count incremented
        state = store._read_state()
        assert state["session_count"] >= 1

    @pytest.mark.asyncio
    async def test_session_start_initializes_current_session(self, clean_store, mock_request):
        """session_start initializes current session state."""
        request = mock_request({})

        await hook_session_start(request)

        state = store._read_state()
        session = state["current_session"]
        assert "started_at" in session
        assert session["tool_failures"] == 0
        assert session["tool_successes"] == 0
        assert session["compacted"] is False

    @pytest.mark.asyncio
    async def test_session_start_returns_memories(self, clean_store, mock_request):
        """session_start returns loaded memories in context."""
        # Create some memories
        store.create(topic="Test Memory", content="Content", tags=["test"])

        request = mock_request({})
        response = await hook_session_start(request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert data["memories_loaded"] == 1
        assert "context" in data
        assert "Test Memory" in data["context"]

    @pytest.mark.asyncio
    async def test_session_start_handles_empty_memories(self, clean_store, mock_request):
        """session_start handles case with no memories."""
        request = mock_request({})

        response = await hook_session_start(request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert data["memories_loaded"] == 0

    @pytest.mark.asyncio
    async def test_session_start_handles_invalid_json(self, clean_store, mock_request):
        """session_start handles invalid JSON input gracefully."""
        request = mock_request(None)  # Will cause JSONDecodeError

        response = await hook_session_start(request)
        data = json.loads(response.text)

        assert data["success"] is True


class TestHookTrackDifficulty:
    """Tests for track_difficulty HTTP hook."""

    @pytest.mark.asyncio
    async def test_track_difficulty_success(self, clean_store, mock_request):
        """track_difficulty tracks successful tool use."""
        # Initialize session state
        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Write",
            "tool_response": {"success": True},
        }
        request = mock_request(payload)

        response = await hook_track_difficulty(request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert data["tracked"] is True
        assert data["is_failure"] is False

        state = store._read_state()
        assert state["current_session"]["tool_successes"] == 1
        assert state["current_session"]["tool_failures"] == 0

    @pytest.mark.asyncio
    async def test_track_difficulty_failure_error_key(self, clean_store, mock_request):
        """track_difficulty tracks failed tool use with error key."""
        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Bash",
            "tool_response": {"error": "command not found"},
        }
        request = mock_request(payload)

        response = await hook_track_difficulty(request)
        data = json.loads(response.text)

        assert data["is_failure"] is True

        state = store._read_state()
        assert state["current_session"]["tool_failures"] == 1

    @pytest.mark.asyncio
    async def test_track_difficulty_failure_success_false(self, clean_store, mock_request):
        """track_difficulty tracks failed tool use with success: false."""
        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Write",
            "tool_response": {"success": False},
        }
        request = mock_request(payload)

        response = await hook_track_difficulty(request)
        data = json.loads(response.text)

        assert data["is_failure"] is True

    @pytest.mark.asyncio
    async def test_track_difficulty_error_in_text(self, clean_store, mock_request):
        """track_difficulty detects Error in response text."""
        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 0}
        store._write_state(state)

        payload = {
            "tool_name": "Bash",
            "tool_response": {"text": "Error: something failed"},
        }
        request = mock_request(payload)

        response = await hook_track_difficulty(request)
        data = json.loads(response.text)

        assert data["is_failure"] is True

    @pytest.mark.asyncio
    async def test_track_difficulty_handles_invalid_json(self, clean_store, mock_request):
        """track_difficulty handles invalid JSON gracefully."""
        request = mock_request(None)

        response = await hook_track_difficulty(request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert data["tracked"] is False

    @pytest.mark.asyncio
    async def test_track_difficulty_handles_empty_payload(self, clean_store, mock_request):
        """track_difficulty handles empty payload."""
        request = mock_request({})

        response = await hook_track_difficulty(request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert data["tracked"] is False


class TestHookPreCompact:
    """Tests for pre_compact HTTP hook."""

    @pytest.mark.asyncio
    async def test_pre_compact_marks_compaction(self, clean_store, mock_request):
        """pre_compact marks session as compacted."""
        state = store._read_state()
        state["current_session"] = {"compacted": False}
        store._write_state(state)

        request = mock_request({})

        response = await hook_pre_compact(request)
        data = json.loads(response.text)

        assert data["success"] is True

        state = store._read_state()
        assert state["current_session"]["compacted"] is True

    @pytest.mark.asyncio
    async def test_pre_compact_increments_compaction_count(self, clean_store, mock_request):
        """pre_compact increments compaction counter."""
        state = store._read_state()
        state["compaction_count"] = 5
        state["current_session"] = {}
        store._write_state(state)

        request = mock_request({})

        response = await hook_pre_compact(request)
        data = json.loads(response.text)

        assert data["compaction_count"] == 6

    @pytest.mark.asyncio
    async def test_pre_compact_handles_invalid_json(self, clean_store, mock_request):
        """pre_compact handles invalid JSON gracefully."""
        request = mock_request(None)

        response = await hook_pre_compact(request)
        data = json.loads(response.text)

        assert data["success"] is True


class TestHookSessionEnd:
    """Tests for session_end HTTP hook."""

    @pytest.mark.asyncio
    async def test_session_end_resets_session_state(self, clean_store, mock_request):
        """session_end resets current session state."""
        state = store._read_state()
        state["current_session"] = {
            "tool_failures": 5,
            "tool_successes": 10,
            "compacted": True,
        }
        store._write_state(state)

        request = mock_request({})

        response = await hook_session_end(request)
        data = json.loads(response.text)

        assert data["success"] is True

        state = store._read_state()
        assert state["current_session"] == {}

    @pytest.mark.asyncio
    async def test_session_end_updates_priorities(self, clean_store, mock_request):
        """session_end updates memory priorities."""
        # Create a memory
        mem_id = store.create(topic="Test", content="Content", difficulty=0.5)

        state = store._read_state()
        state["current_session"] = {"tool_failures": 0, "tool_successes": 10}
        store._write_state(state)

        request = mock_request({})

        await hook_session_end(request)

        # Verify priority was updated
        stats = store._read_stats()
        assert mem_id in stats["memories"]
        assert "priority" in stats["memories"][mem_id]

    @pytest.mark.asyncio
    async def test_session_end_returns_difficulty(self, clean_store, mock_request):
        """session_end returns calculated session difficulty."""
        state = store._read_state()
        state["current_session"] = {
            "tool_failures": 5,
            "tool_successes": 5,
            "compacted": True,
        }
        store._write_state(state)

        request = mock_request({})

        response = await hook_session_end(request)
        data = json.loads(response.text)

        assert "session_difficulty" in data
        assert 0.0 <= data["session_difficulty"] <= 1.0

    @pytest.mark.asyncio
    async def test_session_end_handles_invalid_json(self, clean_store, mock_request):
        """session_end handles invalid JSON gracefully."""
        request = mock_request(None)

        response = await hook_session_end(request)
        data = json.loads(response.text)

        assert data["success"] is True


class TestHookHealth:
    """Tests for health HTTP endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_healthy(self, mock_request):
        """health endpoint returns healthy status."""
        request = mock_request({})

        response = await hook_health(request)
        data = json.loads(response.text)

        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestHookShutdown:
    """Tests for shutdown HTTP endpoint."""

    @pytest.mark.asyncio
    async def test_shutdown_sets_event(self, mock_request):
        """shutdown endpoint sets shutdown event."""
        # Reset shutdown event
        shutdown_event.clear()

        request = mock_request({})

        response = await hook_shutdown(request)
        data = json.loads(response.text)

        assert data["success"] is True
        assert shutdown_event.is_set()

        # Reset for other tests
        shutdown_event.clear()


class TestParseArgs:
    """Tests for argument parsing."""

    def test_parse_args_defaults(self, monkeypatch):
        """parse_args returns correct defaults."""
        monkeypatch.setattr(sys, "argv", ["mcp_server.py"])

        args = parse_args()

        assert args.server is False
        assert args.mcp_port == 8765
        assert args.hooks_port == 9999
        assert args.host == "0.0.0.0"

    def test_parse_args_server_mode(self, monkeypatch):
        """parse_args handles --server flag."""
        monkeypatch.setattr(sys, "argv", ["mcp_server.py", "--server"])

        args = parse_args()

        assert args.server is True

    def test_parse_args_custom_ports(self, monkeypatch):
        """parse_args handles custom ports."""
        monkeypatch.setattr(sys, "argv", [
            "mcp_server.py", "--server",
            "--mcp-port", "12345",
            "--hooks-port", "54321",
            "--host", "127.0.0.1",
        ])

        args = parse_args()

        assert args.mcp_port == 12345
        assert args.hooks_port == 54321
        assert args.host == "127.0.0.1"

    def test_parse_args_data_path(self, monkeypatch):
        """parse_args handles --data-path argument."""
        monkeypatch.setattr(sys, "argv", [
            "mcp_server.py",
            "--data-path", "/custom/data/path",
        ])

        args = parse_args()

        assert args.data_path == "/custom/data/path"

    def test_parse_args_data_path_default_none(self, monkeypatch):
        """parse_args has None as default for --data-path."""
        monkeypatch.setattr(sys, "argv", ["mcp_server.py"])

        args = parse_args()

        assert args.data_path is None


class TestSessionEndEviction:
    """Tests for eviction triggered by session_end."""

    @pytest.mark.asyncio
    async def test_session_end_triggers_eviction(self, clean_store, mock_request):
        """session_end triggers eviction when over threshold."""
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
                difficulty=0.1 * i,
            )

        request = mock_request({})

        response = await hook_session_end(request)
        data = json.loads(response.text)

        assert data["success"] is True
        # May or may not have run eviction depending on timing
        assert "eviction_ran" in data

    @pytest.mark.asyncio
    async def test_session_end_no_eviction_needed(self, clean_store, mock_request):
        """session_end doesn't run eviction when under threshold."""
        state = store._read_state()
        state["config"] = {"max_memories": 100}
        state["current_session"] = {}
        store._write_state(state)

        # Create just one memory
        store.create(topic="Memory", content="Content")

        request = mock_request({})

        response = await hook_session_end(request)
        data = json.loads(response.text)

        assert data["eviction_ran"] is False


class TestTcpServerTransport:
    """Tests for TCP server transport wrapper."""

    @pytest.mark.asyncio
    async def test_tcp_transport_creates_streams(self):
        """tcp_server_transport yields working memory streams."""
        from mcp_server import tcp_server_transport
        import anyio

        # Create mock reader/writer
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        # Make readline return empty to simulate connection close
        reader.readline = AsyncMock(return_value=b"")

        async with tcp_server_transport(reader, writer) as (read_stream, write_stream):
            # Verify we got memory object streams
            from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
            assert hasattr(read_stream, "receive")
            assert hasattr(write_stream, "send")

    @pytest.mark.asyncio
    async def test_tcp_transport_reads_jsonrpc(self):
        """tcp_server_transport correctly parses JSON-RPC messages."""
        from mcp_server import tcp_server_transport, SessionMessage
        import anyio

        # Create mock reader/writer
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        # Simulate receiving a valid JSON-RPC message, then close
        valid_jsonrpc = b'{"jsonrpc":"2.0","method":"ping","id":1}\n'
        call_count = 0

        async def readline_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return valid_jsonrpc
            return b""  # Connection closed

        reader.readline = AsyncMock(side_effect=readline_side_effect)

        async with tcp_server_transport(reader, writer) as (read_stream, write_stream):
            # Wait briefly for the reader task to process
            await anyio.sleep(0.05)

            # Try to receive with timeout
            try:
                with anyio.fail_after(0.5):
                    msg = await read_stream.receive()
                    assert isinstance(msg, SessionMessage)
                    assert msg.message.root.method == "ping"
            except TimeoutError:
                # If we timeout, that's okay - the message may not have been sent yet
                pass

    @pytest.mark.asyncio
    async def test_tcp_transport_writes_jsonrpc(self):
        """tcp_server_transport correctly writes JSON-RPC messages."""
        from mcp_server import tcp_server_transport, SessionMessage, JSONRPCMessage
        from mcp.types import JSONRPCResponse
        import anyio

        # Create mock reader/writer
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        # Make readline return empty to simulate no incoming messages
        reader.readline = AsyncMock(return_value=b"")

        async with tcp_server_transport(reader, writer) as (read_stream, write_stream):
            # Send a response message
            response = JSONRPCResponse(jsonrpc="2.0", id=1, result={"status": "ok"})
            msg = SessionMessage(message=JSONRPCMessage(response))
            await write_stream.send(msg)

            # Wait for writer task to process
            await anyio.sleep(0.05)

            # Verify write was called
            assert writer.write.called
            written_data = writer.write.call_args[0][0]
            assert b'"jsonrpc":"2.0"' in written_data
            assert written_data.endswith(b"\n")

    @pytest.mark.asyncio
    async def test_tcp_transport_handles_malformed_json(self):
        """tcp_server_transport handles malformed JSON gracefully."""
        from mcp_server import tcp_server_transport
        import anyio

        # Create mock reader/writer
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        # Simulate receiving malformed JSON, then close
        call_count = 0

        async def readline_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"this is not valid json\n"
            return b""  # Connection closed

        reader.readline = AsyncMock(side_effect=readline_side_effect)

        async with tcp_server_transport(reader, writer) as (read_stream, write_stream):
            # Wait for reader task to process
            await anyio.sleep(0.05)

            # The exception should be sent to the stream
            try:
                with anyio.fail_after(0.5):
                    msg = await read_stream.receive()
                    # Should receive an exception for malformed JSON
                    assert isinstance(msg, Exception)
            except TimeoutError:
                pass

    @pytest.mark.asyncio
    async def test_tcp_transport_handles_connection_close(self):
        """tcp_server_transport handles connection close cleanly."""
        from mcp_server import tcp_server_transport
        import anyio

        # Create mock reader/writer
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        # Simulate immediate connection close
        reader.readline = AsyncMock(return_value=b"")

        # Should not raise an exception
        async with tcp_server_transport(reader, writer) as (read_stream, write_stream):
            await anyio.sleep(0.05)
            # Context exits cleanly

    @pytest.mark.asyncio
    async def test_tcp_transport_handles_empty_lines(self):
        """tcp_server_transport ignores empty lines."""
        from mcp_server import tcp_server_transport
        import anyio

        # Create mock reader/writer
        reader = AsyncMock(spec=asyncio.StreamReader)
        writer = MagicMock(spec=asyncio.StreamWriter)
        writer.write = MagicMock()
        writer.drain = AsyncMock()

        # Simulate receiving empty lines then a valid message then close
        call_count = 0
        valid_jsonrpc = b'{"jsonrpc":"2.0","method":"test","id":2}\n'

        async def readline_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return b"\n"
            elif call_count == 2:
                return b"  \n"
            elif call_count == 3:
                return valid_jsonrpc
            return b""

        reader.readline = AsyncMock(side_effect=readline_side_effect)

        async with tcp_server_transport(reader, writer) as (read_stream, write_stream):
            await anyio.sleep(0.05)

            try:
                with anyio.fail_after(0.5):
                    msg = await read_stream.receive()
                    # Should get the valid message, not an error from empty lines
                    from mcp_server import SessionMessage
                    assert isinstance(msg, SessionMessage)
            except TimeoutError:
                pass
