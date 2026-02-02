#!/bin/bash
# LTM Session End Hook
# Persists state, updates priorities, runs eviction

set -e

PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
SERVER_JSON="${PROJECT_ROOT}/.claude/ltm/server.json"

# Check if server.json exists (container is running)
if [[ ! -f "$SERVER_JSON" ]]; then
    exit 0
fi

# Read the hooks port
PORT=$(jq -r '.hooks_port // empty' "$SERVER_JSON" 2>/dev/null)

if [[ -z "$PORT" ]]; then
    exit 0
fi

# Call the session end endpoint
curl -s -X POST "http://127.0.0.1:${PORT}/hook/session_end" \
    -H 'Content-Type: application/json' \
    -d '{}' 2>/dev/null || true
