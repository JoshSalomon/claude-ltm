---
id: "mem_2aeb9280"
topic: "Claude Code plugin persistent installation via marketplace"
tags:
  - claude-code
  - plugin
  - marketplace
  - installation
phase: 0
difficulty: 0.7
created_at: "2026-02-02T10:14:04.088843+00:00"
created_session: 18
---
## Problem
Plugins installed with `--plugin-dir` are only available for that session. Users want persistent installation.

## Solution

### Creating a Marketplace for Your Plugin

1. Create `.claude-plugin/marketplace.json`:
```json
{
  "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
  "name": "your-plugin-name",
  "description": "Plugin marketplace description",
  "owner": {
    "name": "Your Name",
    "email": "email@example.com"
  },
  "plugins": [
    {
      "name": "plugin-name",
      "description": "Plugin description",
      "version": "0.1.0",
      "author": {
        "name": "Your Name"
      },
      "source": "./",
      "category": "productivity"
    }
  ]
}
```

2. In `plugin.json`, do NOT include `hooks` field if using standard `hooks/hooks.json` - it's auto-loaded

### Installation Commands

```bash
# Add marketplace from GitHub
claude plugin marketplace add https://github.com/user/repo.git

# Install plugin
claude plugin install pluginname@marketplacename

# Update
claude plugin update pluginname@marketplacename

# Uninstall
claude plugin uninstall pluginname@marketplacename
claude plugin marketplace remove marketplacename
```

### Key Learnings
- Marketplace needs `owner` object with `name` and `email`
- Plugin `source` must be `"./"` not `"."` 
- Don't reference `hooks/hooks.json` in plugin.json - it's auto-loaded
- Can install directly from GitHub URL
