# LTM System Management

Manage the Long-Term Memory system.

## Usage

- `/ltm` - Show system status
- `/ltm help` - Show command summary
- `/ltm init` - Initialize LTM (hooks + CLAUDE.md)
- `/ltm list` - List all memories
- `/ltm list --tag <tag>` - List memories with specific tag
- `/ltm check` - Check system integrity
- `/ltm fix` - Fix integrity issues
- `/ltm fix --clean-archives` - Fix issues and remove orphaned archives
- `/ltm start` - Start persistent LTM container
- `/ltm stop` - Stop persistent LTM container

## Instructions

Parse the arguments: $ARGUMENTS

**No arguments or "status"**: Call `mcp__ltm__ltm_status` and display the results in a readable format.

**"help"**: Display this help message:
```
LTM Commands:
  /ltm                     Show system status
  /ltm help                Show this help
  /ltm init                Initialize LTM (hooks + CLAUDE.md)
  /ltm list                List all memories
  /ltm list --tag X        List memories with tag
  /ltm check               Check system integrity
  /ltm fix                 Fix integrity issues
  /ltm fix --clean-archives  Also remove orphaned archives
  /ltm start               Start persistent container
  /ltm stop                Stop persistent container

  /remember [topic]  Store a new memory
  /recall <query>    Search memories
  /forget <id>       Delete a memory
```

**"list"**: Call `mcp__ltm__list_memories`. If `--tag <tag>` is provided, pass the tag parameter. Display results in a table format with ID, topic, phase, and tags.

**"check"**: Call `mcp__ltm__ltm_check` and display the integrity report.

**"fix"**: Call `mcp__ltm__ltm_fix` with `archive_orphans=true`. If `--clean-archives` is provided, also pass `clean_orphaned_archives=true`. Report what was fixed.

**"start"**: Start the persistent LTM container.

1. Check if `server.json` exists in `.claude/ltm/`
2. If not, tell the user to run the setup script first:
   ```
   curl -sSL https://raw.githubusercontent.com/JoshSalomon/claude-ltm/main/.claude/ltm/setup.sh | bash
   ```
3. Read the container name from `server.json` using: `jq -r .container_name .claude/ltm/server.json`
4. Run: `podman start <container_name>` (or `docker start` if podman not available)
5. Verify the container is running with `podman ps --filter name=<container_name>`
6. Report the status including the ports from server.json

**"stop"**: Stop the persistent LTM container.

1. Read the container name from `.claude/ltm/server.json` using: `jq -r .container_name .claude/ltm/server.json`
2. Run: `podman stop <container_name>` (or `docker stop`)
3. Report the container has been stopped

**"init"**: Initialize LTM hooks and CLAUDE.md.

### Step 1: Check prerequisites

1. Read `.claude/ltm/server.json`
2. If it doesn't exist, tell the user to run the setup script first:
   ```bash
   curl -sSL https://raw.githubusercontent.com/JoshSalomon/claude-ltm/main/.claude/ltm/setup.sh | bash
   ```
   Then exit.
3. Extract `hooks_port` from server.json (it's a JSON file with `hooks_port` field)

### Step 2: Configure hooks in .claude/settings.local.json

1. Read `.claude/settings.local.json` (create with `{}` if it doesn't exist)
2. Check if hooks are already configured (has "hooks" key with LTM curl commands)
3. If not configured, add the hooks section using the port from server.json:

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:PORT/hook/session_start"}]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:PORT/hook/track_difficulty"}]
      }
    ],
    "PreCompact": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:PORT/hook/pre_compact"}]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [{"type": "command", "command": "curl -s -X POST http://127.0.0.1:PORT/hook/session_end"}]
      }
    ]
  }
}
```

Replace `PORT` with the actual hooks_port value from server.json. Preserve any existing settings when merging.

### Step 3: Add proactive memory instructions to CLAUDE.md

1. Read the current CLAUDE.md file in the project root (create if it doesn't exist)
2. Check if it already contains "## Proactive Memory Usage" section
3. If not present, append the following section to CLAUDE.md:

```markdown
## Proactive Memory Usage

When working on tasks, proactively search for relevant memories:

- **Before debugging**: Use `mcp__ltm__recall` to search for prior solutions to similar errors
- **Before implementing features**: Search for related patterns or past decisions
- **When encountering familiar problems**: Check if there's a stored solution

Example scenarios to trigger recall:
- Error messages or exceptions → search for the error type or message
- Working on a specific component → search for that component name
- Configuration issues → search for "config" or the specific setting

After solving a difficult problem, use `mcp__ltm__store_memory` to save the solution for future reference. Always notify the user when a memory is stored (e.g., "Stored this solution to LTM for future reference.").

## Extended Thinking Memory Consultation

**IMPORTANT**: When operating in extended thinking modes ("think harder" or "ultrathink"), you MUST consult long-term memory as part of your reasoning process:

1. **At the start of extended thinking**: Search for memories related to the current task using `mcp__ltm__recall`
2. **During analysis**: Reference any relevant memories found to inform your approach
3. **Before finalizing**: Check if similar problems were solved before and what worked

This ensures that valuable past learnings are incorporated into complex reasoning tasks.
```

### Step 4: Report results

Report what was configured:
- Container: name and ports from server.json
- Hooks: configured / already configured
- CLAUDE.md: updated / already configured
- Remind user to restart Claude Code session for hooks to take effect
