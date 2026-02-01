# Claude LTM - Long-Term Memory for Claude Code

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/JoshSalomon/claude-ltm/releases)
[![Container](https://img.shields.io/badge/container-quay.io-red.svg)](https://quay.io/repository/jsalomon/ltm-mcp-server)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)

A persistent memory system for [Claude Code](https://claude.ai/code) that enables Claude to remember important information across sessions. Built with a hybrid hooks + MCP server architecture.

## Features

- **Automatic Context Loading** - Top memories are loaded at session start
- **On-Demand Storage** - Store important learnings with `/remember`
- **Semantic Search** - Find memories by keyword with `/recall`
- **Smart Eviction** - Graceful degradation through phases (Full → Hint → Abstract → Removed)
- **Difficulty Tracking** - Memories from challenging tasks are prioritized
- **Git-Friendly** - Human-readable markdown files with YAML frontmatter
- **Integrity Tools** - Check and fix system health with `/ltm check` and `/ltm fix`
- **Extended Thinking Integration** - Automatically consults memory in "think harder" and "ultrathink" modes

## Quick Start

### Prerequisites

- [Claude Code CLI](https://claude.ai/code) installed
- Podman or Docker
- `curl`, `jq` (usually pre-installed on Linux/macOS)
- `socat` or `nc` (for MCP connection)

### One-Line Installation (Recommended)

Run this in your project directory:

```bash
curl -sSL https://raw.githubusercontent.com/JoshSalomon/claude-ltm/main/.claude/ltm/setup.sh | bash
```

This script automatically:
1. Creates a project-specific container with unique name and ports
2. Pulls the LTM container image from `quay.io/jsalomon/ltm-mcp-server`
3. Registers MCP with Claude Code
4. Configures hooks to use the container's HTTP endpoints
5. Downloads slash commands (`/remember`, `/recall`, `/forget`, `/ltm`)
6. Starts the container

**That's it!** Restart Claude Code and you're ready to use LTM.

**After running the setup script, start Claude Code and run `/ltm init`** to configure hooks and update CLAUDE.md.

### What Gets Created

```
.claude/
├── ltm/
│   ├── server.json         # Container config (name, ports) - git-ignored
│   ├── ltm-start.sh        # Start container + connect MCP (used by Claude Code)
│   ├── ltm-stop.sh         # Stop container (run from terminal when done)
│   ├── index.json          # Memory index - git-tracked
│   ├── memories/           # Memory files - git-tracked
│   └── archives/           # Archived content - git-tracked
├── commands/               # Slash commands
│   ├── remember.md
│   ├── recall.md
│   ├── forget.md
│   └── ltm.md
└── settings.local.json     # Hooks configuration (created by /ltm init)
```

### Container Management

Each project gets a unique container name (based on directory hash) to avoid conflicts.

**Container starts automatically** when Claude Code connects via MCP.

**To stop the container** (from terminal, when Claude Code is closed):
```bash
bash .claude/ltm/ltm-stop.sh
```

**Other commands:**
```bash
# View container config
cat .claude/ltm/server.json

# View logs
podman logs ltm-<your-hash>

# Inside Claude Code
/ltm start    # Start container
/ltm stop     # Stop container
```

### Git Configuration

The setup script adds these to `.gitignore`:
```
.claude/ltm/stats.json
.claude/ltm/state.json
.claude/ltm/server.json
```

Memories (`.claude/ltm/memories/` and `.claude/ltm/index.json`) are git-tracked for team sharing.

---

## Alternative Installation Methods

> **Important:** LTM source code should NOT be copied into your projects. Only the memory data directory (`.claude/ltm/`) and slash commands (`.claude/commands/`) are created in your project.

### Option 1: Build Container Locally

For users who want to audit the code before running, or don't trust pre-built images.

```bash
# One-time: Clone and build the container
git clone https://github.com/JoshSalomon/claude-ltm.git
cd claude-ltm
export LTM_HOME=$(pwd)
podman build -t ltm-mcp-server .claude/ltm/

# Add to shell profile for persistence
echo "export LTM_HOME=$LTM_HOME" >> ~/.bashrc  # or ~/.zshrc

# Per project: Run the local setup script
cd /path/to/your/project
bash $LTM_HOME/.claude/ltm/setup-local.sh

# In Claude Code, run: /ltm init
```

This uses your locally-built container instead of the pre-built image from quay.io.

### Option 2: Development Mode (Direct Python)

For LTM developers or users who want maximum control. Runs the MCP server directly with Python without containerization.

```bash
# One-time: Clone and set up environment
git clone https://github.com/JoshSalomon/claude-ltm.git
cd claude-ltm
export LTM_HOME=$(pwd)
echo "export LTM_HOME=$LTM_HOME" >> ~/.bashrc  # or ~/.zshrc

# Set up Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r .claude/ltm/requirements.txt

# Per project: Configure to use this LTM installation
cd /path/to/your/project
mkdir -p .claude/ltm/{memories,archives} .claude/commands

# Copy slash commands
cp $LTM_HOME/.claude/commands/*.md .claude/commands/

# Register MCP with --data-path pointing to your project
claude mcp add --transport stdio ltm -- \
  $LTM_HOME/.venv/bin/python $LTM_HOME/.claude/ltm/mcp_server.py \
  --data-path "$(pwd)/.claude/ltm"
```

**Pros:**
- Full visibility into code execution
- Easy to debug and modify
- No container overhead

**Cons:**
- Requires Python 3.11+ on host
- Must manage Python dependencies
- Hooks require separate setup (see below)

**Note:** In development mode, hooks run via Python scripts. Copy the hook scripts and configure them in `.claude/settings.local.json`, or run `/ltm init` after setting up HTTP endpoints manually.

### Trust Considerations

| Method | Trust Level | Use When |
|--------|-------------|----------|
| Pre-built container | Trust quay.io/jsalomon | Quick setup, don't need to audit code |
| Local container build | Audit before build | Want to review code, security-conscious |
| Development mode | Full control | Contributing to LTM, debugging issues |

### Hooks Configuration

The recommended installation uses HTTP hooks that communicate with the container. The setup script configures these automatically in `.claude/settings.local.json`:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:<HOOKS_PORT>/hook/session_start"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:<HOOKS_PORT>/hook/track_difficulty"}]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:<HOOKS_PORT>/hook/pre_compact"}]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:<HOOKS_PORT>/hook/session_end"}]
      }
    ]
  }
}
```

## Usage

### Slash Commands

| Command | Description |
|---------|-------------|
| `/remember` | Store a memory interactively |
| `/remember <topic>` | Store a memory with the given topic |
| `/recall <query>` | Search memories by keyword |
| `/forget <id>` | Delete a memory by ID |
| `/ltm` | Show system status |
| `/ltm help` | Show command summary |
| `/ltm init` | Add proactive memory instructions to CLAUDE.md |
| `/ltm list` | List all memories |
| `/ltm list --tag <tag>` | List memories with specific tag |
| `/ltm list --phase <n>` | List memories by eviction phase (0-2) |
| `/ltm check` | Check system integrity |
| `/ltm fix` | Fix integrity issues |
| `/ltm fix --clean-archives` | Fix issues and remove orphaned archives |
| `/ltm start` | Start persistent LTM container |
| `/ltm stop` | Stop persistent LTM container |

### Examples

```bash
# Store a debugging solution
/remember Fix for authentication timeout

# Search for database-related memories
/recall database

# List all memories tagged with "api"
/ltm list --tag api

# Check system health
/ltm check

# Fix any integrity issues
/ltm fix
```

### MCP Tools

The LTM MCP server provides these tools (usable directly or via slash commands):

| Tool | Parameters | Description |
|------|------------|-------------|
| `store_memory` | `topic`, `content`, `tags?`, `auto_tag?` | Store a new memory |
| `recall` | `query`, `limit?` | Search memories |
| `list_memories` | `phase?`, `tag?`, `keyword?` | List with filters |
| `get_memory` | `id` | Get full memory content |
| `forget` | `id` | Delete a memory |
| `ltm_status` | - | Get system status |
| `ltm_check` | - | Check integrity |
| `ltm_fix` | `archive_orphans?`, `clean_orphaned_archives?` | Fix integrity issues |

## Proactive Memory Usage

By default, only the top 10 memories are loaded at session start. To enable Claude to proactively search for relevant memories when debugging or implementing features, run:

```bash
/ltm init
```

This adds instructions to your project's `CLAUDE.md` that tell Claude to:
- Search for prior solutions before debugging errors
- Check for related patterns before implementing features
- Store solutions after solving difficult problems

**What gets added to CLAUDE.md:**

```markdown
## Proactive Memory Usage

When working on tasks, proactively search for relevant memories:

- **Before debugging**: Use `mcp__ltm__recall` to search for prior solutions
- **Before implementing features**: Search for related patterns or past decisions
- **When encountering familiar problems**: Check if there's a stored solution

After solving a difficult problem, use `mcp__ltm__store_memory` to save the solution. Always notify the user when a memory is stored.

## Extended Thinking Memory Consultation

**IMPORTANT**: When operating in extended thinking modes ("think harder" or "ultrathink"),
you MUST consult long-term memory as part of your reasoning process:

1. At the start of extended thinking: Search for memories related to the current task
2. During analysis: Reference any relevant memories found to inform your approach
3. Before finalizing: Check if similar problems were solved before and what worked
```

## Architecture

### Hybrid Approach

- **Hooks** (Python scripts): Handle automatic operations during session lifecycle
  - `SessionStart`: Load top memories into context
  - `PostToolUse`: Track task difficulty based on tool success/failure
  - `PreCompact`: Save state before context compaction
  - `SessionEnd`: Persist changes and run eviction

- **MCP Server** (Python): Exposes tools for on-demand memory operations

### Storage Structure

```
.claude/ltm/
├── index.json           # Lightweight index for fast lookup (git-tracked)
├── stats.json           # Access statistics (git-ignored)
├── state.json           # Session state (git-ignored)
├── memories/            # Individual memory files (git-tracked)
│   └── mem_abc123.md    # Markdown with YAML frontmatter
└── archives/            # Evicted detailed content (git-tracked)
```

### Memory File Format

Memories are stored as markdown files with YAML frontmatter:

```yaml
---
id: "mem_abc123"
topic: "Fix database connection timeout"
tags:
  - database
  - debugging
phase: 0
difficulty: 0.8
created_at: "2026-01-15T10:30:00Z"
---
## Problem
The database connection was timing out after 30 seconds...

## Solution
Increased the connection pool size from 5 to 20...
```

### Priority Algorithm

Memories are prioritized using:

```
priority = (difficulty * 0.4) + (recency * 0.3) + (frequency * 0.3)
```

- **Difficulty**: Based on tool failures and context compaction
- **Recency**: Sessions since last access (session-based, not time-based)
- **Frequency**: How often the memory is accessed

### Eviction Phases

When storage exceeds the threshold, low-priority memories are progressively reduced:

| Phase | Name | Content | Description |
|-------|------|---------|-------------|
| 0 | Full | Complete content | Original memory |
| 1 | Hint | Summary only | Detailed content archived |
| 2 | Abstract | One-line summary | Further reduced |
| 3 | Removed | Archived only | Deleted from active storage |

Archived content is preserved in `.claude/ltm/archives/` and can be restored.

### GitOps & Multi-User Support

The LTM system is designed for GitOps workflows and multi-user collaboration:

**Git-Tracked Files (shared across users/branches):**
- `index.json` - Lightweight index with memory metadata
- `memories/*.md` - Memory content files (human-readable markdown)
- `archives/*.md` - Archived content from evicted memories

**Git-Ignored Files (local to each user/machine):**
- `stats.json` - Access statistics (access count, last accessed, priority scores)
- `state.json` - Session state (session counter, configuration)

**Why This Separation?**

| Concern | Git-Tracked | Git-Ignored |
|---------|-------------|-------------|
| Memory content | Yes | - |
| Tags and metadata | Yes | - |
| Access patterns | - | Yes |
| Priority scores | - | Yes |
| Session counter | - | Yes |

**Benefits:**

1. **No Merge Conflicts on Volatile Data** - Access counts and priorities are local, so different users won't conflict on these frequently-changing values.

2. **Shared Knowledge Base** - Memory content and tags are versioned, so team members can share learnings across branches and pull requests.

3. **Fresh Start on Clone** - When you clone or switch branches, `stats.json` starts empty. Priority scores are recalculated from difficulty (stored in memory files) combined with local access patterns.

4. **Human-Readable Conflicts** - When memory content conflicts occur, they're in markdown format and easy to resolve manually.

**Multi-User Workflow:**

```bash
# User A stores a memory
/remember Fix for database timeout

# User A commits and pushes
git add .claude/ltm/memories/ .claude/ltm/index.json
git commit -m "Add database timeout fix memory"
git push

# User B pulls and gets the memory
git pull
# Memory is now available, with fresh local access stats
```

**Branch Merging:**

Memories are typically additive - new memories get new IDs. When merging branches:
- New memories from both branches are preserved
- `index.json` changes are usually auto-mergeable
- Memory file conflicts (rare) are human-readable markdown

### Resolving index.json Merge Conflicts

If you get a merge conflict in `index.json`, here's how to resolve it:

**Structure of index.json:**
```json
{
  "version": 1,
  "memories": {
    "mem_abc123": { "topic": "...", "tags": [...], "phase": 0 },
    "mem_def456": { "topic": "...", "tags": [...], "phase": 0 }
  },
  "tags": {
    "database": ["mem_abc123"],
    "api": ["mem_def456"]
  }
}
```

**Resolution steps:**

1. **Keep all memories from both sides** - Each memory has a unique ID (`mem_XXXXXXXX`). Include all memory entries from both versions.

2. **Merge the tags index** - For each tag, combine the memory ID arrays from both sides. Remove duplicates.

3. **Verify memory files exist** - Each memory ID in `index.json` should have a corresponding `.claude/ltm/memories/mem_XXXXXXXX.md` file.

**Example conflict resolution:**
```json
// CONFLICT - both sides added different memories
<<<<<<< HEAD
  "memories": {
    "mem_abc123": { "topic": "Fix timeout", "tags": ["database"], "phase": 0 }
  }
=======
  "memories": {
    "mem_def456": { "topic": "API auth", "tags": ["api"], "phase": 0 }
  }
>>>>>>> feature-branch

// RESOLVED - keep both memories
  "memories": {
    "mem_abc123": { "topic": "Fix timeout", "tags": ["database"], "phase": 0 },
    "mem_def456": { "topic": "API auth", "tags": ["api"], "phase": 0 }
  }
```

**After resolving:** Run `/ltm check` in Claude Code to verify integrity, and `/ltm fix` if needed.

## Configuration

Configuration is stored in `.claude/ltm/state.json`:

```json
{
  "config": {
    "max_memories": 100,
    "memories_to_load": 10,
    "eviction_batch_size": 10
  }
}
```

| Setting | Default | Description |
|---------|---------|-------------|
| `max_memories` | 100 | Maximum memories before eviction |
| `memories_to_load` | 10 | Memories loaded at session start |
| `eviction_batch_size` | 10 | Memories processed per eviction cycle |

## Development

### Building the Container

To build the container image locally:

```bash
# Build the container image
podman build -t ltm-mcp-server .claude/ltm/

# Register with Claude Code
claude mcp add --transport stdio ltm -- podman run -i --rm --userns=keep-id -v "$(pwd)/.claude/ltm:/data:Z" ltm-mcp-server
```

### Running Tests

```bash
# Activate virtual environment
source .claude/ltm/venv/bin/activate

# Run all tests
pytest .claude/ltm/tests/

# Run with coverage
pytest .claude/ltm/tests/ --cov=.claude/ltm --cov-report=term-missing

# Run specific test file
pytest .claude/ltm/tests/test_store.py -v
```

### Project Structure

```
.claude/
├── ltm/                      # LTM source code (for developers)
│   ├── docs/
│   │   ├── PRD.md           # Product Requirements
│   │   ├── TESTING.md       # Testing Strategy
│   │   └── ARCHITECTURE.md  # Technical Design
│   ├── tests/
│   │   ├── test_store.py
│   │   ├── test_mcp_server.py
│   │   ├── test_eviction.py
│   │   ├── test_hooks.py
│   │   └── test_priority.py
│   ├── store.py             # Core storage operations
│   ├── priority.py          # Priority calculation
│   ├── eviction.py          # Phased eviction
│   ├── mcp_server.py        # MCP tool definitions
│   ├── requirements.txt
│   └── Dockerfile
├── ltm_hooks/                # Hook scripts (for users)
│   ├── session_start.py
│   ├── track_difficulty.py
│   ├── pre_compact.py
│   └── session_end.py
├── commands/
│   ├── remember.md
│   ├── recall.md
│   ├── forget.md
│   └── ltm.md
└── settings.local.json      # Hooks configuration
```

## Troubleshooting

### MCP Server Not Responding

```bash
# Check if MCP server is registered
claude mcp list

# Re-register the server
claude mcp remove ltm
claude mcp add --transport stdio ltm -- python .claude/ltm/mcp_server.py
```

### Integrity Issues

```bash
# In Claude Code, check for issues
/ltm check

# Fix any issues found
/ltm fix
```

### Container Permission Errors

If using podman and encountering permission errors:

```bash
# Use --userns=keep-id flag
podman run -i --rm --userns=keep-id -v "$(pwd)/.claude/ltm:/data:Z" ltm-mcp-server
```

### Reset LTM Data

To completely reset the LTM system:

```bash
# Remove all memories and state (keeps configuration)
rm -rf .claude/ltm/memories/*
rm -rf .claude/ltm/archives/*
rm -f .claude/ltm/index.json
rm -f .claude/ltm/stats.json
rm -f .claude/ltm/state.json
```

## Contributing

Contributions are welcome! Please read the documentation in `.claude/ltm/docs/` before contributing.

## License

This project is open source. See LICENSE file for details.

## Links

- [Claude Code Documentation](https://docs.anthropic.com/en/docs/claude-code)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- Container Image: [quay.io/jsalomon/ltm-mcp-server](https://quay.io/repository/jsalomon/ltm-mcp-server)
