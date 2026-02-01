#!/usr/bin/env python3
"""
LTM MCP Server - Long-Term Memory for Claude Code.

This MCP server provides tools for storing, retrieving, and managing
memories across Claude Code sessions.

Usage:
    python mcp_server.py                         # stdio mode (default)
    python mcp_server.py --server                # server mode with TCP MCP + HTTP hooks
    python mcp_server.py --server --mcp-port 8765 --hooks-port 9999

Registration with Claude Code:
    claude mcp add --transport stdio ltm -- python .claude/ltm/mcp_server.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream

# Add the ltm directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.shared.session import SessionMessage
from mcp.types import JSONRPCMessage, TextContent, Tool

from store import MemoryStore, MemoryNotFoundError
from priority import PriorityCalculator
from eviction import EvictionManager, EvictionConfig

# Initialize server and store
server = Server("ltm")
store = MemoryStore()
priority_calc = PriorityCalculator()

# Global shutdown event for server mode
shutdown_event = asyncio.Event()


def _extract_tags(topic: str, content: str) -> list[str]:
    """
    Auto-extract tags from topic and content.

    Extracts technology names, file extensions, and common patterns.
    """
    import re

    tags = set()
    text = f"{topic} {content}".lower()

    # Common technology keywords
    tech_keywords = [
        "python", "javascript", "typescript", "rust", "go", "java",
        "react", "vue", "angular", "node", "django", "flask", "fastapi",
        "postgres", "postgresql", "mysql", "sqlite", "mongodb", "redis",
        "docker", "kubernetes", "aws", "gcp", "azure",
        "api", "rest", "graphql", "grpc",
        "git", "github", "gitlab",
        "test", "testing", "debug", "debugging",
        "auth", "authentication", "authorization",
        "database", "cache", "queue", "async",
        "frontend", "backend", "fullstack",
        "security", "performance", "optimization",
    ]

    for keyword in tech_keywords:
        if keyword in text:
            tags.add(keyword)

    # File extensions
    extensions = re.findall(r"\.([a-z]{2,4})\b", text)
    for ext in extensions:
        if ext in ["py", "js", "ts", "rs", "go", "java", "rb", "php"]:
            tags.add(ext)

    return list(tags)[:10]  # Limit to 10 tags


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available LTM tools."""
    return [
        Tool(
            name="store_memory",
            description="Store a new memory for future recall. Use this to save important learnings, debugging solutions, or project-specific knowledge.",
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Brief topic/title for the memory (e.g., 'Fix database connection timeout')",
                    },
                    "content": {
                        "type": "string",
                        "description": "Full content to store. Use markdown formatting. Include problem description, solution, and key learnings.",
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional categorization tags (e.g., ['database', 'debugging'])",
                    },
                    "auto_tag": {
                        "type": "boolean",
                        "description": "Auto-generate tags from content if no tags provided. Default: false",
                        "default": False,
                    },
                    "difficulty": {
                        "type": "number",
                        "description": "Difficulty score from 0.0 (easy) to 1.0 (hard). Higher difficulty = higher priority. Default: 0.5",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "default": 0.5,
                    },
                },
                "required": ["topic", "content"],
            },
        ),
        Tool(
            name="recall",
            description="Search memories by keyword. Returns matching memories sorted by priority.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query - matches against topic and content",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results. Default: 10",
                        "default": 10,
                        "minimum": 1,
                        "maximum": 50,
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="list_memories",
            description="List memories with optional filtering by phase, tag, or keyword.",
            inputSchema={
                "type": "object",
                "properties": {
                    "phase": {
                        "type": "integer",
                        "description": "Filter by eviction phase: 0=Full, 1=Hint, 2=Abstract",
                        "minimum": 0,
                        "maximum": 2,
                    },
                    "tag": {
                        "type": "string",
                        "description": "Filter memories containing this tag",
                    },
                    "keyword": {
                        "type": "string",
                        "description": "Filter memories with keyword in topic",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results. Default: 20",
                        "default": 20,
                        "minimum": 1,
                        "maximum": 100,
                    },
                },
            },
        ),
        Tool(
            name="get_memory",
            description="Get full content of a specific memory by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "Memory ID (e.g., 'mem_abc12345')",
                    },
                },
                "required": ["memory_id"],
            },
        ),
        Tool(
            name="forget",
            description="Delete a memory. The memory is archived before deletion for potential recovery.",
            inputSchema={
                "type": "object",
                "properties": {
                    "memory_id": {
                        "type": "string",
                        "description": "Memory ID to delete",
                    },
                },
                "required": ["memory_id"],
            },
        ),
        Tool(
            name="ltm_status",
            description="Get LTM system status and statistics.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="ltm_check",
            description="Check LTM integrity. Detects orphaned files, missing files, and orphaned stats entries.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="ltm_fix",
            description="Fix LTM integrity issues. Archives orphaned files before removal and cleans up broken references.",
            inputSchema={
                "type": "object",
                "properties": {
                    "archive_orphans": {
                        "type": "boolean",
                        "description": "Archive orphaned files before removal (default: true)",
                        "default": True,
                    },
                    "clean_orphaned_archives": {
                        "type": "boolean",
                        "description": "Remove archive files for non-existent memories (default: false)",
                        "default": False,
                    },
                },
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    try:
        if name == "store_memory":
            return await handle_store_memory(arguments)
        elif name == "recall":
            return await handle_recall(arguments)
        elif name == "list_memories":
            return await handle_list_memories(arguments)
        elif name == "get_memory":
            return await handle_get_memory(arguments)
        elif name == "forget":
            return await handle_forget(arguments)
        elif name == "ltm_status":
            return await handle_ltm_status(arguments)
        elif name == "ltm_check":
            return await handle_ltm_check(arguments)
        elif name == "ltm_fix":
            return await handle_ltm_fix(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def handle_store_memory(args: dict) -> list[TextContent]:
    """Store a new memory."""
    topic = args["topic"]
    content = args["content"]
    tags = args.get("tags", [])
    auto_tag = args.get("auto_tag", False)
    difficulty = args.get("difficulty", 0.5)

    # Auto-generate tags if requested and no tags provided
    if auto_tag and not tags:
        tags = _extract_tags(topic, content)

    memory_id = store.create(
        topic=topic,
        content=content,
        tags=tags,
        difficulty=difficulty,
    )

    result = {
        "success": True,
        "id": memory_id,
        "message": f"Memory stored successfully with ID: {memory_id}",
    }

    if tags:
        result["tags"] = tags

    return [TextContent(type="text", text=_format_result(result))]


async def handle_recall(args: dict) -> list[TextContent]:
    """Search memories by query."""
    query = args["query"]
    limit = args.get("limit", 10)

    results = store.search(query, limit=limit)

    if not results:
        return [TextContent(
            type="text",
            text=f"No memories found matching '{query}'"
        )]

    output = f"Found {len(results)} memories matching '{query}':\n\n"

    for mem in results:
        output += f"**{mem['topic']}** (ID: {mem['id']})\n"
        output += f"Tags: {', '.join(mem.get('tags', [])) or 'none'}\n"
        output += f"Priority: {mem.get('priority', 0):.2f} | Phase: {mem.get('phase', 0)}\n"
        if mem.get("summary"):
            output += f"Summary: {mem['summary'][:100]}...\n"
        output += "\n"

    return [TextContent(type="text", text=output)]


async def handle_list_memories(args: dict) -> list[TextContent]:
    """List memories with filtering."""
    phase = args.get("phase")
    tag = args.get("tag")
    keyword = args.get("keyword")
    limit = args.get("limit", 20)

    results = store.list(phase=phase, tag=tag, keyword=keyword, limit=limit)

    if not results:
        filters = []
        if phase is not None:
            filters.append(f"phase={phase}")
        if tag:
            filters.append(f"tag='{tag}'")
        if keyword:
            filters.append(f"keyword='{keyword}'")
        filter_str = ", ".join(filters) if filters else "no filters"
        return [TextContent(
            type="text",
            text=f"No memories found with {filter_str}"
        )]

    # Build output
    output = f"Found {len(results)} memories:\n\n"

    for mem in results:
        phase_names = {0: "Full", 1: "Hint", 2: "Abstract"}
        phase_name = phase_names.get(mem.get("phase", 0), "Unknown")

        output += f"- **{mem['topic']}** (ID: `{mem['id']}`)\n"
        output += f"  Tags: {', '.join(mem.get('tags', [])) or 'none'} | "
        output += f"Phase: {phase_name} | "
        output += f"Priority: {mem.get('priority', 0):.2f}\n"

    return [TextContent(type="text", text=output)]


async def handle_get_memory(args: dict) -> list[TextContent]:
    """Get full memory content."""
    memory_id = args["memory_id"]

    try:
        memory = store.read(memory_id)
    except MemoryNotFoundError:
        return [TextContent(
            type="text",
            text=f"Memory not found: {memory_id}"
        )]

    output = f"# {memory.get('topic', 'Untitled')}\n\n"
    output += f"**ID:** {memory_id}\n"
    output += f"**Tags:** {', '.join(memory.get('tags', [])) or 'none'}\n"
    output += f"**Phase:** {memory.get('phase', 0)}\n"
    output += f"**Difficulty:** {memory.get('difficulty', 0.5):.2f}\n"
    output += f"**Created:** {memory.get('created_at', 'Unknown')}\n\n"
    output += "---\n\n"
    output += memory.get("content", "")

    return [TextContent(type="text", text=output)]


async def handle_forget(args: dict) -> list[TextContent]:
    """Delete a memory."""
    memory_id = args["memory_id"]

    try:
        store.delete(memory_id, archive=True)
    except MemoryNotFoundError:
        return [TextContent(
            type="text",
            text=f"Memory not found: {memory_id}"
        )]

    return [TextContent(
        type="text",
        text=f"Memory {memory_id} has been deleted (archived for recovery)."
    )]


async def handle_ltm_status(args: dict) -> list[TextContent]:
    """Get system status."""
    memories = store.list(limit=1000)
    state = store._read_state()

    # Count by phase
    by_phase = {0: 0, 1: 0, 2: 0}
    for mem in memories:
        phase = mem.get("phase", 0)
        if phase in by_phase:
            by_phase[phase] += 1

    # Count archives
    archives_path = store.archives_path
    archive_count = len(list(archives_path.glob("*.md"))) if archives_path.exists() else 0

    output = "# LTM System Status\n\n"
    output += f"**Total Memories:** {len(memories)}\n"
    output += f"**Archived:** {archive_count}\n"
    output += f"**Session Count:** {state.get('session_count', 0)}\n\n"

    output += "## By Phase\n"
    output += f"- Full (0): {by_phase[0]}\n"
    output += f"- Hint (1): {by_phase[1]}\n"
    output += f"- Abstract (2): {by_phase[2]}\n\n"

    config = state.get("config", {})
    output += "## Configuration\n"
    output += f"- Max Memories: {config.get('max_memories', 100)}\n"
    output += f"- Memories to Load: {config.get('memories_to_load', 10)}\n"
    output += f"- Eviction Batch Size: {config.get('eviction_batch_size', 10)}\n\n"

    output += f"**Storage Path:** `{store.base_path}`\n"

    return [TextContent(type="text", text=output)]


async def handle_ltm_check(args: dict) -> list[TextContent]:
    """Check LTM integrity."""
    result = store.check_integrity()

    output = "# LTM Integrity Check\n\n"

    if result["is_healthy"]:
        output += "**Status: Healthy** - No integrity issues found.\n\n"
    else:
        output += "**Status: Issues Found**\n\n"

    # Summary
    summary = result["summary"]
    output += "## Summary\n"
    output += f"- Indexed memories: {summary['indexed']}\n"
    output += f"- Memory files: {summary['files']}\n"
    output += f"- Stats entries: {summary['stats']}\n"
    output += f"- Archive files: {summary['archives']}\n\n"

    # Issues
    if result["orphaned_files"]:
        output += "## Orphaned Files\n"
        output += "*Memory files with no index entry:*\n"
        for mem_id in result["orphaned_files"]:
            output += f"- `{mem_id}`\n"
        output += "\n"

    if result["missing_files"]:
        output += "## Missing Files\n"
        output += "*Index entries with no memory file:*\n"
        for mem_id in result["missing_files"]:
            output += f"- `{mem_id}`\n"
        output += "\n"

    if result["orphaned_stats"]:
        output += "## Orphaned Stats\n"
        output += "*Stats entries with no index entry:*\n"
        for mem_id in result["orphaned_stats"]:
            output += f"- `{mem_id}`\n"
        output += "\n"

    if result["orphaned_archives"]:
        output += "## Orphaned Archives\n"
        output += "*Archive files for non-existent memories:*\n"
        for mem_id in result["orphaned_archives"]:
            output += f"- `{mem_id}`\n"
        output += "\n"

    if not result["is_healthy"]:
        output += "*Run `/ltm fix` to repair these issues.*\n"

    return [TextContent(type="text", text=output)]


async def handle_ltm_fix(args: dict) -> list[TextContent]:
    """Fix LTM integrity issues."""
    archive_orphans = args.get("archive_orphans", True)
    clean_orphaned_archives = args.get("clean_orphaned_archives", False)

    # First check what issues exist
    before = store.check_integrity()

    # Check if there's anything to fix
    has_issues = not before["is_healthy"]
    has_orphaned_archives = len(before.get("orphaned_archives", [])) > 0

    if not has_issues and not (clean_orphaned_archives and has_orphaned_archives):
        return [TextContent(
            type="text",
            text="# LTM Integrity Fix\n\n**No issues to fix.** System is healthy.",
        )]

    # Fix the issues
    result = store.fix_integrity(
        archive_orphans=archive_orphans,
        clean_orphaned_archives=clean_orphaned_archives,
    )

    output = "# LTM Integrity Fix\n\n"
    output += "**Repairs completed:**\n\n"

    if result["archived_files"] > 0:
        output += f"- Archived {result['archived_files']} orphaned file(s)\n"
    if result["removed_files"] > 0:
        output += f"- Removed {result['removed_files']} orphaned file(s)\n"
    if result["removed_index_entries"] > 0:
        output += f"- Removed {result['removed_index_entries']} missing file index entry(s)\n"
    if result["removed_stats_entries"] > 0:
        output += f"- Removed {result['removed_stats_entries']} orphaned stats entry(s)\n"
    if result.get("removed_orphaned_archives", 0) > 0:
        output += f"- Removed {result['removed_orphaned_archives']} orphaned archive(s)\n"

    # Verify fix
    after = store.check_integrity()
    output += "\n"
    if after["is_healthy"]:
        output += "**System is now healthy.**\n"
    else:
        output += "**Note:** Some issues may remain. Run `/ltm check` for details.\n"

    return [TextContent(type="text", text=output)]


def _format_result(data: dict) -> str:
    """Format a result dict as readable text."""
    lines = []
    for key, value in data.items():
        if isinstance(value, list):
            lines.append(f"{key}: {', '.join(str(v) for v in value)}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines)


# =============================================================================
# HTTP Hooks Handlers (for server mode)
# =============================================================================


async def hook_session_start(request) -> "web.Response":
    """Handle session start hook - load memories and increment session counter."""
    from aiohttp import web

    try:
        payload = await request.json() if request.can_read_body else {}
    except json.JSONDecodeError:
        payload = {}

    # Load and update state
    state = store._read_state()
    state["session_count"] = state.get("session_count", 0) + 1
    state["current_session"] = {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "tool_failures": 0,
        "tool_successes": 0,
        "compacted": False,
    }
    store._write_state(state)

    # Get configuration
    config = state.get("config", {})
    limit = config.get("memories_to_load", 10)

    # Get top memories by priority
    memories = store.list(limit=limit)

    if not memories:
        return web.json_response({"success": True, "memories_loaded": 0})

    # Build context output
    output_lines = []
    output_lines.append("## Long-Term Memory Context\n")
    output_lines.append(f"*Loaded {len(memories)} memories from previous sessions*\n")

    for mem in memories:
        output_lines.append(f"### {mem['topic']}")
        if mem.get("tags"):
            output_lines.append(f"*Tags: {', '.join(mem['tags'])}*")
        output_lines.append(f"*Priority: {mem.get('priority', 0):.2f} | Phase: {mem.get('phase', 0)}*")
        output_lines.append("")

        # Read full content for high-priority memories (phase 0)
        if mem.get("phase", 0) == 0:
            try:
                full_mem = store.read(mem["id"], update_stats=False)
                content = full_mem.get("content", "")
                if len(content) > 500:
                    content = content[:500] + "..."
                output_lines.append(content)
            except Exception:
                pass

        output_lines.append("\n---\n")

    return web.json_response({
        "success": True,
        "memories_loaded": len(memories),
        "context": "\n".join(output_lines),
    })


async def hook_track_difficulty(request) -> "web.Response":
    """Handle track difficulty hook - track tool success/failure."""
    from aiohttp import web

    try:
        payload = await request.json() if request.can_read_body else {}
    except json.JSONDecodeError:
        return web.json_response({"success": True, "tracked": False})

    if not payload:
        return web.json_response({"success": True, "tracked": False})

    # Get tool response
    tool_response = payload.get("tool_response", {})

    # Determine if this was a failure
    is_failure = False
    if "error" in tool_response:
        is_failure = True
    elif tool_response.get("success") is False:
        is_failure = True
    elif "text" in tool_response and "Error" in str(tool_response.get("text", "")):
        is_failure = True

    # Update session state
    state = store._read_state()
    session = state.get("current_session", {})

    if is_failure:
        session["tool_failures"] = session.get("tool_failures", 0) + 1
    else:
        session["tool_successes"] = session.get("tool_successes", 0) + 1

    state["current_session"] = session
    store._write_state(state)

    return web.json_response({
        "success": True,
        "tracked": True,
        "is_failure": is_failure,
    })


async def hook_pre_compact(request) -> "web.Response":
    """Handle pre-compact hook - save state before context compaction."""
    from aiohttp import web

    try:
        payload = await request.json() if request.can_read_body else {}
    except json.JSONDecodeError:
        payload = {}

    # Update state to mark compaction
    state = store._read_state()
    state["compaction_count"] = state.get("compaction_count", 0) + 1

    session = state.get("current_session", {})
    session["compacted"] = True
    state["current_session"] = session

    store._write_state(state)

    return web.json_response({
        "success": True,
        "compaction_count": state["compaction_count"],
    })


async def hook_session_end(request) -> "web.Response":
    """Handle session end hook - persist state, update priorities, run eviction."""
    from aiohttp import web

    try:
        payload = await request.json() if request.can_read_body else {}
    except json.JSONDecodeError:
        payload = {}

    # Load current state
    state = store._read_state()
    current_session_num = state.get("session_count", 1)
    session = state.get("current_session", {})

    # Calculate session difficulty
    tool_failures = session.get("tool_failures", 0)
    tool_successes = session.get("tool_successes", 0)
    compacted = session.get("compacted", False)

    session_difficulty = priority_calc.calculate_difficulty(
        tool_failures, tool_successes, compacted
    )

    # Update priorities for all memories
    stats = store._read_stats()
    index = store._read_index()

    for memory_id, mem_stats in stats.get("memories", {}).items():
        mem_meta = index.get("memories", {}).get(memory_id, {})
        if not mem_meta:
            continue

        priority = priority_calc.calculate(mem_meta, mem_stats, current_session_num)
        mem_stats["priority"] = priority

    store._write_stats(stats)

    # Check if eviction is needed
    config = state.get("config", {})
    eviction_config = EvictionConfig(
        max_memories=config.get("max_memories", 100),
        batch_size=config.get("eviction_batch_size", 10),
    )

    eviction_manager = EvictionManager(store, eviction_config)
    eviction_ran = False
    if eviction_manager.needs_eviction():
        eviction_manager.run()
        state["last_eviction"] = datetime.now(timezone.utc).isoformat()
        eviction_ran = True

    # Reset current session state
    state["current_session"] = {}
    store._write_state(state)

    return web.json_response({
        "success": True,
        "session_difficulty": session_difficulty,
        "eviction_ran": eviction_ran,
    })


async def hook_health(request) -> "web.Response":
    """Health check endpoint."""
    from aiohttp import web

    return web.json_response({
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def hook_shutdown(request) -> "web.Response":
    """Graceful shutdown endpoint."""
    from aiohttp import web

    shutdown_event.set()
    return web.json_response({
        "success": True,
        "message": "Shutdown initiated",
    })


async def run_hooks_http_server(host: str, port: int):
    """Run HTTP server for hooks endpoints."""
    from aiohttp import web

    app = web.Application()
    app.router.add_post("/hook/session_start", hook_session_start)
    app.router.add_post("/hook/track_difficulty", hook_track_difficulty)
    app.router.add_post("/hook/pre_compact", hook_pre_compact)
    app.router.add_post("/hook/session_end", hook_session_end)
    app.router.add_get("/health", hook_health)
    app.router.add_post("/shutdown", hook_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    print(f"Hooks HTTP server listening on {host}:{port}", file=sys.stderr)

    # Wait for shutdown
    await shutdown_event.wait()
    await runner.cleanup()


@asynccontextmanager
async def tcp_server_transport(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter
):
    """Bridge asyncio TCP streams to MCP memory object streams.

    Handles newline-delimited JSON-RPC framing.
    Yields (read_stream, write_stream) for use with server.run().
    """
    # Create memory object streams for MCP
    # The types are: MemoryObjectReceiveStream[SessionMessage | Exception]
    # and MemoryObjectSendStream[SessionMessage]
    read_stream_writer, read_stream = anyio.create_memory_object_stream[
        SessionMessage | Exception
    ](0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream[
        SessionMessage
    ](0)

    async def tcp_reader():
        """Read newline-delimited JSON-RPC from TCP and forward to memory stream."""
        try:
            async with read_stream_writer:
                while True:
                    line = await reader.readline()
                    if not line:
                        break  # Connection closed
                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue
                    try:
                        message = JSONRPCMessage.model_validate_json(line_str)
                        await read_stream_writer.send(SessionMessage(message=message))
                    except Exception as e:
                        await read_stream_writer.send(e)
        except anyio.ClosedResourceError:
            pass
        except Exception:
            pass

    async def tcp_writer():
        """Read from memory stream and write newline-delimited JSON-RPC to TCP."""
        try:
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    json_str = session_message.message.model_dump_json(
                        by_alias=True, exclude_none=True
                    )
                    writer.write((json_str + "\n").encode("utf-8"))
                    await writer.drain()
        except anyio.ClosedResourceError:
            pass
        except Exception:
            pass

    async with anyio.create_task_group() as tg:
        tg.start_soon(tcp_reader)
        tg.start_soon(tcp_writer)
        try:
            yield read_stream, write_stream
        finally:
            tg.cancel_scope.cancel()


async def run_mcp_tcp_server(host: str, port: int):
    """Run MCP JSON-RPC server on TCP."""

    async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle a single MCP client connection."""
        try:
            async with tcp_server_transport(reader, writer) as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )
        except Exception as e:
            print(f"MCP client error: {e}", file=sys.stderr)
        finally:
            writer.close()
            await writer.wait_closed()

    tcp_server = await asyncio.start_server(handle_client, host, port)
    addr = tcp_server.sockets[0].getsockname()
    print(f"MCP TCP server listening on {addr[0]}:{addr[1]}", file=sys.stderr)

    async with tcp_server:
        # Run until shutdown
        shutdown_task = asyncio.create_task(shutdown_event.wait())
        serve_task = asyncio.create_task(tcp_server.serve_forever())
        done, pending = await asyncio.wait(
            [shutdown_task, serve_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()


async def run_server_mode(mcp_port: int, hooks_port: int, host: str = "0.0.0.0"):
    """Run both MCP TCP server and hooks HTTP server concurrently."""
    print(f"Starting LTM server mode...", file=sys.stderr)
    print(f"  MCP port: {mcp_port}", file=sys.stderr)
    print(f"  Hooks port: {hooks_port}", file=sys.stderr)

    await asyncio.gather(
        run_mcp_tcp_server(host, mcp_port),
        run_hooks_http_server(host, hooks_port),
    )


async def main_stdio():  # pragma: no cover
    """Run the MCP server in stdio mode."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="LTM MCP Server")
    parser.add_argument(
        "--server",
        action="store_true",
        help="Run in server mode (TCP MCP + HTTP hooks)",
    )
    parser.add_argument(
        "--mcp-port",
        type=int,
        default=8765,
        help="MCP TCP port (default: 8765)",
    )
    parser.add_argument(
        "--hooks-port",
        type=int,
        default=9999,
        help="Hooks HTTP port (default: 9999)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--data-path",
        type=str,
        default=None,
        help="Path to memory data directory (default: .claude/ltm in current directory or LTM_DATA_PATH env var)",
    )
    return parser.parse_args()


if __name__ == "__main__":  # pragma: no cover
    args = parse_args()

    # Reinitialize store with custom data path if specified
    if args.data_path:
        import os
        os.environ["LTM_DATA_PATH"] = args.data_path
        # Reinitialize global store with new path
        store = MemoryStore(args.data_path)

    if args.server:
        asyncio.run(run_server_mode(args.mcp_port, args.hooks_port, args.host))
    else:
        asyncio.run(main_stdio())
