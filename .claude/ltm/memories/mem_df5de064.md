---
id: "mem_df5de064"
topic: "Claude Code Plugin Deployment Challenges and Solutions"
tags:
  - claude-code
  - plugin
  - mcp
  - deployment
  - debugging
  - configuration
phase: 0
difficulty: 0.85
created_at: "2026-02-05T15:02:51.456237+00:00"
created_session: 22
---
# Claude Code Plugin Deployment Challenges

## Problem 1: Plugin MCP Connection Failing

**Symptom:** `claude mcp list` showed `plugin:ltm:ltm: bash scripts/run-mcp.sh - ✗ Failed to connect`

**Root Cause:** The `.mcp.json` used `${CLAUDE_PLUGIN_ROOT:-.}` (bash fallback syntax), but Claude Code does NOT properly expand variables with the `:-` fallback syntax - it treats the variable as unset and uses the literal fallback `.`

**Solution:** Use `${CLAUDE_PLUGIN_ROOT}` without the fallback:
```json
{
  "mcpServers": {
    "ltm": {
      "command": "bash",
      "args": ["${CLAUDE_PLUGIN_ROOT}/scripts/run-mcp.sh"]
    }
  }
}
```

**Key insight:** `${CLAUDE_PLUGIN_ROOT}` expands correctly, but `${CLAUDE_PLUGIN_ROOT:-.}` does NOT.

---

## Problem 2: Data Directory Location

**Concern:** When running as a plugin, where does `pwd` point?

**Discovery:** Claude Code sets `pwd` to the USER'S PROJECT directory, not the plugin cache directory. This means `run-mcp.sh` can use `$(pwd)` to correctly locate the user's project for data storage.

**Environment variables available to plugin MCP:**
- `CLAUDE_PLUGIN_ROOT` = plugin cache path (e.g., `~/.claude/plugins/cache/claude-ltm/ltm/0.2.3`)
- `pwd` = user's current project directory
- `CLAUDE_PROJECT_ROOT` = NOT SET by Claude Code

---

## Problem 3: cwd Field in .mcp.json

**Finding:** Using `cwd` field with variable expansion is unreliable. Better to put the full path directly in `args`.

**What works:**
```json
{"args": ["${CLAUDE_PLUGIN_ROOT}/scripts/run-mcp.sh"]}
```

**What doesn't work reliably:**
```json
{"args": ["scripts/run-mcp.sh"], "cwd": "${CLAUDE_PLUGIN_ROOT:-.}"}
```

---

## Problem 4: Dual MCP Entries in Plugin Source Directory

When working in the plugin source directory (claude-ltm), `claude mcp list` shows:
1. `plugin:ltm:ltm` - Works (from installed plugin)
2. `ltm` - Fails (from local `.mcp.json`)

The local `.mcp.json` uses `${CLAUDE_PLUGIN_ROOT}` which is only set for installed plugins, not for project-level `.mcp.json` files.

**Resolution:** This is expected behavior. The installed plugin works; the failing local entry is cosmetic noise.

---

## Problem 5: Plugin Install from Wrong Branch

`claude plugin install` pulls from the default branch (main), not the current feature branch.

**Workaround:** Either merge to main first, or manually update the installed plugin cache after installation.

---

## Key Learnings

1. **Variable expansion:** Claude Code supports `${VAR}` but NOT `${VAR:-default}` syntax
2. **Working directory:** Plugin MCPs run with `pwd` = user's project (good for data storage)
3. **Path in args:** Put full path with variable in `args`, don't rely on `cwd`
4. **Plugin installation:** Always installs from default branch
5. **Testing:** Use `claude mcp list` to verify connection status
