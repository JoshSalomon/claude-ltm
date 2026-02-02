---
description: Show LTM command help
---

# LTM Help

Show available LTM commands.

## Usage

- `/ltm:help` - Show command summary

## Instructions

Output the following text EXACTLY as shown, preserving the formatting. Do not use tables or alternative formats:

```
LTM Commands:
  /ltm:init                  Add LTM instructions to CLAUDE.md
  /ltm:status                Show system status
  /ltm:help                  Show this help
  /ltm:list                  List all memories
  /ltm:list --tag <tag>      List memories with tag
  /ltm:check                 Check system integrity
  /ltm:fix                   Fix integrity issues
  /ltm:fix --clean-archives  Also remove orphaned archives

  /ltm:remember [topic]      Store a new memory
  /ltm:recall <query>        Search memories
  /ltm:forget <id>           Delete a memory
```
