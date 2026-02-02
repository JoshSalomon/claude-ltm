#!/bin/bash
# Simple MCP server launcher for LTM plugin
# Runs the container in stdio mode for MCP communication

set -e

# Use CLAUDE_PROJECT_ROOT if set, otherwise use current directory
PROJECT_ROOT="${CLAUDE_PROJECT_ROOT:-$(pwd)}"
DATA_DIR="${PROJECT_ROOT}/.claude/ltm"

# Ensure data directory exists
mkdir -p "${DATA_DIR}/memories" "${DATA_DIR}/archives"

# Detect container runtime
if command -v podman &>/dev/null; then
    RUNTIME="podman"
elif command -v docker &>/dev/null; then
    RUNTIME="docker"
else
    echo "Error: Neither podman nor docker found" >&2
    exit 1
fi

# Run container in stdio mode
# Pass LTM_HOST_PATH so the server can display the actual host path
exec $RUNTIME run -i --rm \
    --userns=keep-id \
    -e "LTM_HOST_PATH=${DATA_DIR}" \
    -v "${DATA_DIR}:/data:Z" \
    quay.io/jsalomon/ltm-mcp-server:latest
