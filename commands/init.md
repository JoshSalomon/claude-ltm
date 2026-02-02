---
description: Add LTM instructions to CLAUDE.md
---

# LTM Init

Initialize LTM integration for the current project by adding memory usage instructions to CLAUDE.md.

## Usage

- `/ltm:init` - Add LTM instructions to project's CLAUDE.md

## Instructions

This command adds proactive memory usage and extended thinking integration instructions to the project's CLAUDE.md file.

**Steps:**

1. Check if CLAUDE.md exists in the project root (`$CLAUDE_PROJECT_ROOT/CLAUDE.md`)
2. If CLAUDE.md doesn't exist, create it with the LTM section
3. If CLAUDE.md exists, check if it already contains "## LTM Integration" section
4. If the section exists, inform the user it's already configured
5. If the section doesn't exist, append the LTM integration content

**Content to append:**

```markdown

## LTM Integration

This project uses the [Claude LTM plugin](https://github.com/JoshSalomon/claude-ltm) for persistent memory across sessions.

### Proactive Memory Usage

When working on tasks, proactively search for relevant memories:

- **Before debugging**: Use `mcp__ltm__recall` to search for prior solutions to similar errors
- **Before implementing features**: Search for related patterns or past decisions
- **When encountering familiar problems**: Check if there's a stored solution

Example scenarios to trigger recall:
- Error messages or exceptions → search for the error type or message
- Working on a specific component → search for that component name
- Configuration issues → search for "config" or the specific setting

After solving a difficult problem, use `mcp__ltm__store_memory` to save the solution for future reference. Always notify the user when a memory is stored (e.g., "Stored this solution to LTM for future reference.").

### Extended Thinking Memory Consultation

**IMPORTANT**: When operating in extended thinking modes ("think harder" or "ultrathink"), you MUST consult long-term memory as part of your reasoning process:

1. **At the start of extended thinking**: Search for memories related to the current task using `mcp__ltm__recall`
2. **During analysis**: Reference any relevant memories found to inform your approach
3. **Before finalizing**: Check if similar problems were solved before and what worked

This ensures that valuable past learnings are incorporated into complex reasoning tasks.
```

**After updating CLAUDE.md, output:**

```
✓ Added LTM integration instructions to CLAUDE.md

The following sections were added:
- Proactive Memory Usage
- Extended Thinking Memory Consultation

Claude will now automatically consult long-term memory during extended thinking and proactively search for relevant memories when debugging or implementing features.
```

**If already configured, output:**

```
LTM integration is already configured in CLAUDE.md (found "## LTM Integration" section).
```
