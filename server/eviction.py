"""
LTM Eviction Module

Handles phased eviction of memories:
- Phase 0 (Full): Complete memory content
- Phase 1 (Hint): Summary + reduced content
- Phase 2 (Abstract): One-line summary only
- Phase 3 (Removed): Deleted from active storage (archived)

Eviction preserves content in archives before reduction.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from store import MemoryStore


@dataclass
class EvictionConfig:
    """Configuration for eviction behavior."""

    max_memories: int = 100
    batch_size: int = 10
    hint_max_chars: int = 200
    abstract_max_chars: int = 100


class EvictionManager:
    """Manages phased eviction of memories."""

    def __init__(self, store: "MemoryStore", config: EvictionConfig | None = None):
        """
        Initialize eviction manager.

        Args:
            store: The memory store to manage
            config: Eviction configuration (uses defaults if None)
        """
        self.store = store
        self.config = config or EvictionConfig()

    def needs_eviction(self) -> bool:
        """Check if eviction is needed based on memory count."""
        memories = self.store.list(limit=self.config.max_memories + 1)
        return len(memories) > self.config.max_memories

    def run(self) -> dict:
        """
        Run eviction on lowest priority memories.

        Returns:
            dict with eviction statistics:
            - processed: number of memories processed
            - phase_transitions: dict of phase transitions made
            - archived: number of memories archived
            - deleted: number of memories deleted
        """
        memories = self.store.list(limit=self.config.max_memories + self.config.batch_size)

        if len(memories) <= self.config.max_memories:
            return {"processed": 0, "phase_transitions": {}, "archived": 0, "deleted": 0}

        # Sort by priority (lowest first)
        sorted_memories = sorted(memories, key=lambda m: m.get("priority", 0))

        stats = {
            "processed": 0,
            "phase_transitions": {"0_to_1": 0, "1_to_2": 0, "2_to_3": 0},
            "archived": 0,
            "deleted": 0,
        }

        # Process batch of lowest priority memories
        for mem in sorted_memories[: self.config.batch_size]:
            memory_id = mem["id"]
            current_phase = mem.get("phase", 0)

            if current_phase >= 3:
                continue  # Already removed

            try:
                if current_phase == 0:
                    # Phase 0 -> 1: Archive and reduce to hint
                    if self._archive_memory(memory_id):
                        stats["archived"] += 1
                    self._reduce_to_hint(memory_id)
                    self.store.update(memory_id, phase=1)
                    stats["phase_transitions"]["0_to_1"] += 1

                elif current_phase == 1:
                    # Phase 1 -> 2: Reduce to abstract
                    self._reduce_to_abstract(memory_id)
                    self.store.update(memory_id, phase=2)
                    stats["phase_transitions"]["1_to_2"] += 1

                elif current_phase == 2:
                    # Phase 2 -> 3: Remove from active storage
                    self.store.delete(memory_id, archive=False)  # Already archived
                    stats["phase_transitions"]["2_to_3"] += 1
                    stats["deleted"] += 1

                stats["processed"] += 1

            except Exception:
                pass  # Skip problematic memories

        return stats

    def _archive_memory(self, memory_id: str) -> bool:
        """
        Archive full memory content before reduction.

        Args:
            memory_id: ID of memory to archive

        Returns:
            True if archived, False if already archived or failed
        """
        archive_path = self.store.archives_path / f"{memory_id}.md"
        if archive_path.exists():
            return False  # Already archived

        try:
            memory = self.store.read(memory_id, update_stats=False)
            self.store._write_memory_file(memory_id, memory, path=archive_path)
            return True
        except Exception:
            return False

    def _reduce_to_hint(self, memory_id: str) -> None:
        """
        Reduce memory content to hint (summary + truncated content).

        Args:
            memory_id: ID of memory to reduce
        """
        try:
            memory = self.store.read(memory_id, update_stats=False)
            content = memory.get("content", "")

            # Extract summary section if present
            if "## Summary" in content:
                # Keep only the summary section
                parts = content.split("## Content")
                if len(parts) > 0:
                    hint_content = parts[0].strip()
                    hint_content += "\n\n*[Content reduced - see archives for full version]*"
                    self.store.update(memory_id, content=hint_content)
                    return

            # Otherwise keep first N characters
            max_chars = self.config.hint_max_chars
            hint_content = content[:max_chars]
            if len(content) > max_chars:
                hint_content += "...\n\n*[Content reduced - see archives for full version]*"
            self.store.update(memory_id, content=hint_content)

        except Exception:
            pass

    def _reduce_to_abstract(self, memory_id: str) -> None:
        """
        Reduce memory content to abstract (one-line summary).

        Args:
            memory_id: ID of memory to reduce
        """
        try:
            memory = self.store.read(memory_id, update_stats=False)
            content = memory.get("content", "")

            # Extract first non-header line
            lines = content.split("\n")
            first_line = ""
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("## "):
                    first_line = stripped
                    break

            # Limit to N characters
            max_chars = self.config.abstract_max_chars
            if len(first_line) > max_chars:
                first_line = first_line[:max_chars] + "..."

            abstract_content = f"*Abstract: {first_line}*\n\n*[Full content archived]*"
            self.store.update(memory_id, content=abstract_content)

        except Exception:
            pass

    def restore_from_archive(self, memory_id: str) -> bool:
        """
        Restore a memory from archive to full content.

        Args:
            memory_id: ID of memory to restore

        Returns:
            True if restored, False if archive not found or failed
        """
        archive_path = self.store.archives_path / f"{memory_id}.md"
        if not archive_path.exists():
            return False

        try:
            # Read archived content
            archived = self.store._parse_memory_file(archive_path)
            if not archived:
                return False

            # Update memory with archived content
            self.store.update(
                memory_id,
                content=archived.get("content", ""),
                phase=0,
            )
            return True

        except Exception:
            return False

    def get_archived_content(self, memory_id: str) -> str | None:
        """
        Get the archived content for a memory.

        Args:
            memory_id: ID of memory

        Returns:
            Archived content string, or None if not found
        """
        archive_path = self.store.archives_path / f"{memory_id}.md"
        if not archive_path.exists():
            return None

        try:
            archived = self.store._parse_memory_file(archive_path)
            return archived.get("content") if archived else None
        except Exception:
            return None

    def list_archives(self) -> list[str]:
        """
        List all archived memory IDs.

        Returns:
            List of memory IDs that have archives
        """
        archives = []
        for path in self.store.archives_path.glob("*.md"):
            archives.append(path.stem)
        return archives
