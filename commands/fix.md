---
description: Fix LTM integrity issues
---

# Fix Integrity Issues

Fix integrity issues in the Long-Term Memory system.

## Usage

- `/ltm:fix` - Fix integrity issues
- `/ltm:fix --clean-archives` - Fix issues and remove orphaned archives

## Instructions

Arguments: $ARGUMENTS

Call `mcp__ltm__ltm_fix` with `archive_orphans=true`.

If `--clean-archives` is provided in the arguments, also pass `clean_orphaned_archives=true`.

Display the result directly without any additional formatting or commentary. The MCP tool returns pre-formatted markdown output - show it as-is.

Do not add introductory text or summary text. Just show the raw result.
