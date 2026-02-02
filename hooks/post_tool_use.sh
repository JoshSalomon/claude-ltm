#!/bin/bash
# LTM Post Tool Use Hook
# Tracks tool success/failure for difficulty calculation

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

# Read tool response from stdin if available
if [[ -t 0 ]]; then
    PAYLOAD='{}'
else
    PAYLOAD=$(cat)
fi

# Call the track difficulty endpoint
curl -s -X POST "http://127.0.0.1:${PORT}/hook/track_difficulty" \
    -H 'Content-Type: application/json' \
    -d "$PAYLOAD" 2>/dev/null || true
