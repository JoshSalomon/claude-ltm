#!/bin/bash
# LTM Session Start Hook
# Loads memories at the start of a Claude Code session

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SERVER_JSON="${PROJECT_ROOT}/.claude/ltm/server.json"

# Check if server.json exists (container is running)
if [[ ! -f "$SERVER_JSON" ]]; then
    # No server running, silently exit
    exit 0
fi

# Read the hooks port
PORT=$(jq -r '.hooks_port // empty' "$SERVER_JSON" 2>/dev/null)

if [[ -z "$PORT" ]]; then
    exit 0
fi

# Call the session start endpoint
# Use 127.0.0.1 explicitly (not localhost) to avoid IPv6 issues
curl -s -X POST "http://127.0.0.1:${PORT}/hook/session_start" \
    -H 'Content-Type: application/json' \
    -d '{}' 2>/dev/null || true
