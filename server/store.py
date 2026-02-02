"""
Core storage operations for LTM memories.

This module provides CRUD operations for memories stored as markdown files
with YAML frontmatter. It manages three data files:

- index.json: Lightweight index for fast lookups (git-tracked)
- stats.json: Volatile access statistics (git-ignored)
- state.json: Session state and configuration (git-ignored)

Memory files are stored in memories/ as {id}.md with YAML frontmatter.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from priority import PriorityCalculator


class MemoryNotFoundError(Exception):
    """Raised when a memory ID is not found."""

    pass


class MemoryStore:
    """Core storage operations for memories."""

    def __init__(self, base_path: str | Path | None = None):
        """
        Initialize the memory store.

        Args:
            base_path: Path to .claude/ltm directory. Defaults to LTM_DATA_PATH
                       environment variable, or .claude/ltm relative to cwd.
        """
        if base_path is None:
            # Check for container environment variable first
            env_path = os.environ.get("LTM_DATA_PATH")
            if env_path:
                base_path = Path(env_path)
            else:
                base_path = Path.cwd() / ".claude" / "ltm"
        self.base_path = Path(base_path)

        self.memories_path = self.base_path / "memories"
        self.archives_path = self.base_path / "archives"
        self.index_path = self.base_path / "index.json"
        self.stats_path = self.base_path / "stats.json"
        self.state_path = self.base_path / "state.json"

        # Ensure directories exist
        self.memories_path.mkdir(parents=True, exist_ok=True)
        self.archives_path.mkdir(parents=True, exist_ok=True)

        # Priority calculator
        self._priority_calc = PriorityCalculator()

        # Cached data (invalidated on writes)
        self._index_cache: dict | None = None
        self._stats_cache: dict | None = None
        self._state_cache: dict | None = None

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def create(
        self,
        topic: str,
        content: str,
        tags: list[str] | None = None,
        difficulty: float = 0.5,
    ) -> str:
        """
        Create a new memory.

        Args:
            topic: Brief description/title for the memory
            content: Full content to store (markdown)
            tags: Optional list of categorization tags
            difficulty: Initial difficulty score (0.0-1.0)

        Returns:
            Generated memory ID (mem_<hash>)
        """
        memory_id = self._generate_id()
        now = datetime.now(timezone.utc).isoformat()

        # Get current session number
        state = self._read_state()
        current_session = state.get("session_count", 1)

        # Build memory data
        memory_data = {
            "id": memory_id,
            "topic": topic,
            "tags": tags or [],
            "phase": 0,
            "difficulty": max(0.0, min(1.0, difficulty)),
            "created_at": now,
            "created_session": current_session,
            "content": content,
        }

        # Write memory file
        self._write_memory_file(memory_id, memory_data)

        # Update index
        index = self._read_index()
        index["memories"][memory_id] = {
            "topic": topic,
            "tags": tags or [],
            "phase": 0,
            "difficulty": memory_data["difficulty"],
            "created_at": now,
        }
        self._write_index(index)

        # Initialize stats
        stats = self._read_stats()
        stats["memories"][memory_id] = {
            "access_count": 0,
            "accessed_at": now,
            "last_session": current_session,
            "priority": self._priority_calc.calculate(
                memory_data,
                {"access_count": 0, "last_session": current_session},
                current_session,
            ),
        }
        self._write_stats(stats)

        return memory_id

    def read(self, memory_id: str, update_stats: bool = True) -> dict:
        """
        Read a memory by ID.

        Args:
            memory_id: The memory ID to retrieve
            update_stats: Whether to update access statistics

        Returns:
            Full memory data including content

        Raises:
            MemoryNotFoundError: If memory ID not found
        """
        memory_path = self.memories_path / f"{memory_id}.md"

        if not memory_path.exists():
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")

        memory_data = self._parse_memory_file(memory_path)

        if update_stats:
            # Update access statistics
            stats = self._read_stats()
            state = self._read_state()
            current_session = state.get("session_count", 1)

            mem_stats = stats["memories"].get(memory_id, {})
            mem_stats["access_count"] = mem_stats.get("access_count", 0) + 1
            mem_stats["accessed_at"] = datetime.now(timezone.utc).isoformat()
            mem_stats["last_session"] = current_session

            # Recalculate priority
            mem_stats["priority"] = self._priority_calc.calculate(
                memory_data, mem_stats, current_session
            )

            stats["memories"][memory_id] = mem_stats
            self._write_stats(stats)

        return memory_data

    def update(self, memory_id: str, **fields: Any) -> bool:
        """
        Update memory fields.

        Args:
            memory_id: The memory ID to update
            **fields: Fields to update (content, tags, phase, difficulty, etc.)

        Returns:
            True if update successful

        Raises:
            MemoryNotFoundError: If memory ID not found
        """
        # Read current memory (without updating stats)
        memory_data = self.read(memory_id, update_stats=False)

        # Update allowed fields
        allowed_fields = {"content", "tags", "phase", "difficulty", "topic"}
        for key, value in fields.items():
            if key in allowed_fields:
                memory_data[key] = value

        # Write updated memory file
        self._write_memory_file(memory_id, memory_data)

        # Update index if relevant fields changed
        index = self._read_index()
        if memory_id in index["memories"]:
            index_entry = index["memories"][memory_id]

            # Update simple fields
            for key in ["topic", "phase", "difficulty"]:
                if key in fields:
                    index_entry[key] = fields[key]

            # Handle tag changes
            if "tags" in fields:
                index_entry["tags"] = fields["tags"]

            self._write_index(index)

        return True

    def delete(self, memory_id: str, archive: bool = True) -> bool:
        """
        Delete a memory.

        Args:
            memory_id: The memory ID to delete
            archive: Whether to archive before deletion

        Returns:
            True if deletion successful

        Raises:
            MemoryNotFoundError: If memory ID not found
        """
        memory_path = self.memories_path / f"{memory_id}.md"

        if not memory_path.exists():
            raise MemoryNotFoundError(f"Memory not found: {memory_id}")

        # Archive if requested and not already archived
        if archive:
            archive_path = self.archives_path / f"{memory_id}.md"
            if not archive_path.exists():
                # Copy to archive
                memory_data = self._parse_memory_file(memory_path)
                self._write_memory_file(
                    memory_id, memory_data, path=archive_path
                )

        # Remove memory file
        memory_path.unlink()

        # Remove from index
        index = self._read_index()
        if memory_id in index["memories"]:
            del index["memories"][memory_id]
            self._write_index(index)

        # Remove from stats
        stats = self._read_stats()
        if memory_id in stats["memories"]:
            del stats["memories"][memory_id]
            self._write_stats(stats)

        return True

    def list(
        self,
        phase: int | None = None,
        tag: str | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """
        List memories with optional filtering.

        Args:
            phase: Filter by eviction phase (0-3)
            tag: Filter by tag
            keyword: Filter by keyword in topic (case-insensitive)
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            List of memory metadata dicts, sorted by priority (highest first)
        """
        index = self._read_index()
        stats = self._read_stats()
        state = self._read_state()
        current_session = state.get("session_count", 1)

        results = []

        for memory_id, memory_meta in index["memories"].items():
            # Apply phase filter
            if phase is not None and memory_meta.get("phase", 0) != phase:
                continue

            # Apply tag filter
            if tag is not None and tag not in memory_meta.get("tags", []):
                continue

            # Apply keyword filter (case-insensitive)
            if keyword is not None:
                topic = memory_meta.get("topic", "").lower()
                if keyword.lower() not in topic:
                    continue

            # Get or calculate priority
            mem_stats = stats["memories"].get(memory_id, {})
            priority = mem_stats.get("priority")
            if priority is None:
                priority = self._priority_calc.calculate(
                    memory_meta, mem_stats, current_session
                )

            results.append(
                {
                    "id": memory_id,
                    "topic": memory_meta.get("topic", ""),
                    "tags": memory_meta.get("tags", []),
                    "phase": memory_meta.get("phase", 0),
                    "difficulty": memory_meta.get("difficulty", 0.5),
                    "priority": priority,
                    "created_at": memory_meta.get("created_at", ""),
                    "access_count": mem_stats.get("access_count", 0),
                    "accessed_at": mem_stats.get("accessed_at", ""),
                }
            )

        # Sort by priority (highest first)
        results.sort(key=lambda x: x.get("priority", 0), reverse=True)

        # Apply pagination
        return results[offset : offset + limit]

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """
        Search memories by keyword in topic and content.

        Args:
            query: Search query (case-insensitive)
            limit: Maximum number of results

        Returns:
            List of matching memories, sorted by priority
        """
        index = self._read_index()
        stats = self._read_stats()
        state = self._read_state()
        current_session = state.get("session_count", 1)

        query_lower = query.lower()
        results = []

        for memory_id, memory_meta in index["memories"].items():
            # Check topic
            topic_match = query_lower in memory_meta.get("topic", "").lower()

            # Check tags
            tag_match = any(
                query_lower in tag.lower()
                for tag in memory_meta.get("tags", [])
            )

            # Check content (need to read file)
            content_match = False
            if not topic_match and not tag_match:
                memory_path = self.memories_path / f"{memory_id}.md"
                if memory_path.exists():
                    memory_data = self._parse_memory_file(memory_path)
                    content_match = query_lower in memory_data.get(
                        "content", ""
                    ).lower()

            if topic_match or tag_match or content_match:
                mem_stats = stats["memories"].get(memory_id, {})
                priority = mem_stats.get("priority")
                if priority is None:
                    priority = self._priority_calc.calculate(
                        memory_meta, mem_stats, current_session
                    )

                # Get summary (first 200 chars of content)
                memory_path = self.memories_path / f"{memory_id}.md"
                if memory_path.exists():
                    memory_data = self._parse_memory_file(memory_path)
                    content = memory_data.get("content", "")
                    summary = content[:200] + "..." if len(content) > 200 else content
                else:
                    summary = ""

                results.append(
                    {
                        "id": memory_id,
                        "topic": memory_meta.get("topic", ""),
                        "summary": summary,
                        "tags": memory_meta.get("tags", []),
                        "phase": memory_meta.get("phase", 0),
                        "priority": priority,
                    }
                )

        # Sort by priority (highest first)
        results.sort(key=lambda x: x.get("priority", 0), reverse=True)

        return results[:limit]

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _generate_id(self) -> str:
        """Generate unique memory ID (mem_<8-char-hash>)."""
        unique = f"{uuid.uuid4()}{datetime.now().isoformat()}"
        hash_val = hashlib.sha256(unique.encode()).hexdigest()[:8]
        return f"mem_{hash_val}"

    def _read_index(self) -> dict:
        """Load index.json, creating if missing."""
        if self._index_cache is not None:
            return self._index_cache

        if self.index_path.exists():
            with open(self.index_path, "r", encoding="utf-8") as f:
                self._index_cache = json.load(f)
        else:
            self._index_cache = {
                "version": 1,
                "memories": {},
            }

        return self._index_cache

    def _write_index(self, data: dict) -> None:
        """Atomic write to index.json."""
        self._atomic_write_json(self.index_path, data)
        self._index_cache = data

    def _read_stats(self) -> dict:
        """Load stats.json, creating if missing."""
        if self._stats_cache is not None:
            return self._stats_cache

        if self.stats_path.exists():
            with open(self.stats_path, "r", encoding="utf-8") as f:
                self._stats_cache = json.load(f)
        else:
            self._stats_cache = {
                "version": 1,
                "memories": {},
            }

        return self._stats_cache

    def _write_stats(self, data: dict) -> None:
        """Atomic write to stats.json."""
        self._atomic_write_json(self.stats_path, data)
        self._stats_cache = data

    def _read_state(self) -> dict:
        """Load state.json, creating if missing."""
        if self._state_cache is not None:
            return self._state_cache

        if self.state_path.exists():
            with open(self.state_path, "r", encoding="utf-8") as f:
                self._state_cache = json.load(f)
        else:
            self._state_cache = {
                "version": 1,
                "session_count": 1,
                "current_session": {},
                "compaction_count": 0,
                "config": {
                    "max_memories": 100,
                    "memories_to_load": 10,
                    "eviction_batch_size": 10,
                },
            }

        return self._state_cache

    def _write_state(self, data: dict) -> None:
        """Atomic write to state.json."""
        self._atomic_write_json(self.state_path, data)
        self._state_cache = data

    def _atomic_write_json(self, path: Path, data: dict) -> None:
        """Write JSON atomically using temp file + rename."""
        dir_path = path.parent
        fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".json")

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

            os.rename(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def _parse_memory_file(self, path: Path) -> dict:
        """Parse markdown file with YAML frontmatter."""
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Parse YAML frontmatter
        frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
        match = re.match(frontmatter_pattern, content, re.DOTALL)

        if not match:
            # No frontmatter, treat entire file as content
            return {"content": content}

        frontmatter_text = match.group(1)
        body = match.group(2)

        # Parse YAML manually (simple key: value pairs)
        data = self._parse_simple_yaml(frontmatter_text)
        data["content"] = body.strip()

        return data

    def _parse_simple_yaml(self, text: str) -> dict:
        """Parse simple YAML (no nested structures except lists)."""
        data = {}
        current_key = None
        current_list = None

        for line in text.split("\n"):
            line = line.rstrip()

            if not line or line.startswith("#"):
                continue

            # Check for list item
            if line.startswith("  - "):
                if current_list is not None:
                    value = line[4:].strip()
                    # Remove quotes if present
                    if value.startswith('"') and value.endswith('"'):
                        value = value[1:-1]
                    current_list.append(value)
                continue

            # Check for key: value
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]

                if not value:
                    # Start of a list
                    current_key = key
                    current_list = []
                    data[key] = current_list
                else:
                    # Simple value
                    current_key = key
                    current_list = None

                    # Type conversion
                    if value.lower() in ("true", "false"):
                        value = value.lower() == "true"
                    elif value.replace(".", "").replace("-", "").isdigit():
                        try:
                            value = float(value) if "." in value else int(value)
                        except ValueError:
                            pass

                    data[key] = value

        return data

    def _write_memory_file(
        self,
        memory_id: str,
        data: dict,
        path: Path | None = None,
    ) -> None:
        """Write memory as markdown with YAML frontmatter."""
        if path is None:
            path = self.memories_path / f"{memory_id}.md"

        # Build frontmatter
        frontmatter_lines = ["---"]

        # Add fields in specific order
        field_order = [
            "id",
            "topic",
            "tags",
            "phase",
            "difficulty",
            "created_at",
            "created_session",
        ]

        for field in field_order:
            if field in data:
                value = data[field]
                if isinstance(value, list):
                    frontmatter_lines.append(f"{field}:")
                    for item in value:
                        frontmatter_lines.append(f"  - {item}")
                elif isinstance(value, str):
                    frontmatter_lines.append(f'{field}: "{value}"')
                else:
                    frontmatter_lines.append(f"{field}: {value}")

        frontmatter_lines.append("---")
        frontmatter_lines.append("")

        # Build content
        content = data.get("content", "")

        full_content = "\n".join(frontmatter_lines) + content + "\n"

        # Atomic write
        dir_path = path.parent
        fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".md")

        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(full_content)

            os.rename(temp_path, path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    def invalidate_cache(self) -> None:
        """Clear all cached data."""
        self._index_cache = None
        self._stats_cache = None
        self._state_cache = None

    def check_integrity(self) -> dict:
        """
        Check LTM integrity between index, stats, and memory files.

        Returns:
            dict with:
            - orphaned_files: memory files with no index entry
            - missing_files: index entries with no memory file
            - orphaned_stats: stats entries with no index entry
            - orphaned_archives: archive files for non-existent memories
            - is_healthy: True if no issues found
        """
        index = self._read_index()
        stats = self._read_stats()

        indexed_ids = set(index.get("memories", {}).keys())
        stats_ids = set(stats.get("memories", {}).keys())

        # Find memory files on disk
        file_ids = set()
        for path in self.memories_path.glob("*.md"):
            file_ids.add(path.stem)

        # Find archive files on disk
        archive_ids = set()
        for path in self.archives_path.glob("*.md"):
            archive_ids.add(path.stem)

        # Detect issues
        orphaned_files = list(file_ids - indexed_ids)
        missing_files = list(indexed_ids - file_ids)
        orphaned_stats = list(stats_ids - indexed_ids)
        # Archives for memories that no longer exist (not in index and not in files)
        orphaned_archives = list(archive_ids - indexed_ids - file_ids)

        return {
            "orphaned_files": orphaned_files,
            "missing_files": missing_files,
            "orphaned_stats": orphaned_stats,
            "orphaned_archives": orphaned_archives,
            "is_healthy": (
                len(orphaned_files) == 0
                and len(missing_files) == 0
                and len(orphaned_stats) == 0
            ),
            "summary": {
                "indexed": len(indexed_ids),
                "files": len(file_ids),
                "stats": len(stats_ids),
                "archives": len(archive_ids),
            },
        }

    def fix_integrity(
        self, archive_orphans: bool = True, clean_orphaned_archives: bool = False
    ) -> dict:
        """
        Fix LTM integrity issues.

        Args:
            archive_orphans: Archive orphaned memory files before deletion
            clean_orphaned_archives: Remove archive files for non-existent memories

        Returns:
            dict with counts of actions taken:
            - archived_files: orphaned files that were archived
            - removed_files: orphaned files that were removed
            - removed_index_entries: index entries with no file that were removed
            - removed_stats_entries: orphaned stats entries that were removed
            - removed_orphaned_archives: orphaned archive files that were removed
        """
        issues = self.check_integrity()

        result = {
            "archived_files": 0,
            "removed_files": 0,
            "removed_index_entries": 0,
            "removed_stats_entries": 0,
            "removed_orphaned_archives": 0,
        }

        index = self._read_index()
        stats = self._read_stats()
        index_modified = False
        stats_modified = False

        # Handle orphaned memory files (files with no index entry)
        for memory_id in issues["orphaned_files"]:
            memory_path = self.memories_path / f"{memory_id}.md"

            if archive_orphans:
                # Archive the file before removal
                archive_path = self.archives_path / f"{memory_id}.md"
                if not archive_path.exists() and memory_path.exists():
                    try:
                        import shutil

                        shutil.copy2(memory_path, archive_path)
                        result["archived_files"] += 1
                    except Exception:
                        pass  # Skip if can't archive

            # Remove the orphaned file
            if memory_path.exists():
                try:
                    memory_path.unlink()
                    result["removed_files"] += 1
                except Exception:
                    pass  # Skip if can't remove

        # Handle missing files (index entries with no file)
        for memory_id in issues["missing_files"]:
            if memory_id in index.get("memories", {}):
                del index["memories"][memory_id]
                result["removed_index_entries"] += 1
                index_modified = True

        # Handle orphaned stats (stats entries with no index entry)
        for memory_id in issues["orphaned_stats"]:
            if memory_id in stats.get("memories", {}):
                del stats["memories"][memory_id]
                result["removed_stats_entries"] += 1
                stats_modified = True

        # Handle orphaned archives (archive files for non-existent memories)
        if clean_orphaned_archives:
            for memory_id in issues["orphaned_archives"]:
                archive_path = self.archives_path / f"{memory_id}.md"
                if archive_path.exists():
                    try:
                        archive_path.unlink()
                        result["removed_orphaned_archives"] += 1
                    except Exception:
                        pass  # Skip if can't remove

        # Write modified data
        if index_modified:
            self._write_index(index)

        if stats_modified:
            self._write_stats(stats)

        return result
