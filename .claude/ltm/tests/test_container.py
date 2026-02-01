"""Container deployment tests for LTM MCP Server.

These tests verify the container build and functionality.
Requires podman to be installed and the container image to be built.

To run these tests:
    1. Build the container: podman build -t ltm-mcp-server .claude/ltm/
    2. Run the tests: pytest .claude/ltm/tests/test_container.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest


def podman_available() -> bool:
    """Check if podman is available."""
    try:
        result = subprocess.run(
            ["podman", "--version"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def image_exists() -> bool:
    """Check if the ltm-mcp-server image exists."""
    try:
        result = subprocess.run(
            ["podman", "images", "ltm-mcp-server", "--format", "{{.Repository}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return "ltm-mcp-server" in result.stdout
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


# Skip all tests if podman is not available
pytestmark = pytest.mark.skipif(
    not podman_available(),
    reason="podman not available"
)


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for container tests."""
    temp_dir = tempfile.mkdtemp(prefix="ltm_container_test_")
    temp_path = Path(temp_dir)

    # Create required subdirectories
    (temp_path / "memories").mkdir()
    (temp_path / "archives").mkdir()

    yield temp_path

    # Cleanup
    shutil.rmtree(temp_dir)


class TestContainerBuild:
    """Tests for container build."""

    def test_image_exists(self):
        """Verify the container image exists."""
        assert image_exists(), (
            "ltm-mcp-server image not found. "
            "Build it with: podman build -t ltm-mcp-server .claude/ltm/"
        )

    @pytest.mark.skipif(not image_exists(), reason="Image not built")
    def test_image_size(self):
        """Verify image is reasonably sized (< 200MB)."""
        result = subprocess.run(
            ["podman", "images", "ltm-mcp-server:latest", "--format", "{{.Size}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Get just the first line in case of multiple results
        size_str = result.stdout.strip().split("\n")[0].strip()
        # Parse size (e.g., "169 MB")
        if "MB" in size_str:
            size_mb = float(size_str.replace("MB", "").strip())
            assert size_mb < 200, f"Image too large: {size_mb} MB"
        elif "GB" in size_str:
            pytest.fail(f"Image too large: {size_str}")


@pytest.mark.skipif(not image_exists(), reason="Image not built")
class TestContainerModules:
    """Tests for module loading in container."""

    def test_modules_load(self):
        """Verify all Python modules load correctly."""
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--entrypoint", "python",
                "ltm-mcp-server",
                "-c", "import mcp; import store; import priority; print('OK')"
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "OK" in result.stdout

    def test_env_variable_set(self):
        """Verify LTM_DATA_PATH environment variable is set."""
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--entrypoint", "python",
                "ltm-mcp-server",
                "-c", "import os; print(os.environ.get('LTM_DATA_PATH', 'NOT_SET'))"
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "/data" in result.stdout


@pytest.mark.skipif(not image_exists(), reason="Image not built")
class TestContainerVolume:
    """Tests for volume mount functionality."""

    def test_volume_mount_writable(self, temp_data_dir):
        """Verify container can write to mounted volume."""
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
mem_id = store.create(topic='Test', content='Content')
print(f'Created: {mem_id}')
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert "Created: mem_" in result.stdout

        # Verify file was created on host
        memory_files = list(temp_data_dir.glob("memories/*.md"))
        assert len(memory_files) == 1

    def test_volume_persistence(self, temp_data_dir):
        """Verify data persists after container restart."""
        # Create memory in first container run
        result1 = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
mem_id = store.create(topic='Persistent', content='Data')
print(mem_id)
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result1.returncode == 0
        mem_id = result1.stdout.strip()

        # Read memory in second container run
        result2 = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", f"""
from store import MemoryStore
store = MemoryStore()
mem = store.read('{mem_id}')
print(mem['topic'])
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result2.returncode == 0
        assert "Persistent" in result2.stdout


@pytest.mark.skipif(not image_exists(), reason="Image not built")
class TestContainerFunctionalParity:
    """Tests for functional parity between local and containerized server."""

    def test_store_memory(self, temp_data_dir):
        """store_memory works in container."""
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
mem_id = store.create(
    topic='Container Store Test',
    content='Testing store in container',
    tags=['test', 'container'],
    difficulty=0.7
)
print(f'success:{mem_id}')
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "success:mem_" in result.stdout

    def test_list_memories(self, temp_data_dir):
        """list_memories works in container."""
        # First create a memory
        subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
store.create(topic='List Test', content='Content', tags=['listtest'])
"""
            ],
            capture_output=True,
            timeout=30,
        )

        # Then list with filter
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
memories = store.list(tag='listtest')
print(f'found:{len(memories)}')
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "found:1" in result.stdout

    def test_search_memories(self, temp_data_dir):
        """search (recall) works in container."""
        # Create memory
        subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
store.create(topic='Searchable Topic', content='Unique content here')
"""
            ],
            capture_output=True,
            timeout=30,
        )

        # Search
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
results = store.search('searchable')
print(f'found:{len(results)}')
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "found:1" in result.stdout

    def test_forget_memory(self, temp_data_dir):
        """forget (delete) works in container."""
        # Create and then delete
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
mem_id = store.create(topic='To Delete', content='Content')
store.delete(mem_id)
memories = store.list()
print(f'remaining:{len(memories)}')
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "remaining:0" in result.stdout

        # Verify archive was created
        archive_files = list(temp_data_dir.glob("archives/*.md"))
        assert len(archive_files) == 1

    def test_ltm_status(self, temp_data_dir):
        """ltm_status works in container."""
        # Create some memories first
        subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
store.create(topic='Status Test 1', content='Content')
store.create(topic='Status Test 2', content='Content')
"""
            ],
            capture_output=True,
            timeout=30,
        )

        # Check status
        result = subprocess.run(
            [
                "podman", "run", "--rm", "--userns=keep-id",
                "--entrypoint", "python",
                "-v", f"{temp_data_dir}:/data:Z",
                "ltm-mcp-server",
                "-c", """
from store import MemoryStore
store = MemoryStore()
memories = store.list()
state = store._read_state()
print(f'total:{len(memories)}')
print(f'session:{state.get(\"session_count\", 0)}')
"""
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert result.returncode == 0
        assert "total:2" in result.stdout
