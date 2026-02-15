#!/bin/bash
# Simple MCP server launcher for LTM plugin
# Runs the container in stdio mode for MCP communication
#
# Usage:
#   ./run-mcp.sh  # Uses LTM_MCP_IMAGE or defaults to quay.io/jsalomon/ltm-mcp-server:latest
#
# For development with local container changes:
#   LTM_MCP_IMAGE=localhost/ltm-mcp-server:latest claude --plugin-dir .

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
    # No container runtime — run MCP server directly via Python
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    SERVER_DIR="${SCRIPT_DIR}/../server"

    # Install minimal dependencies (skip transformers — token counting uses char-based fallback)
    pip install -q --disable-pip-version-check mcp aiohttp 2>/dev/null

    # Run server directly
    exec python "${SERVER_DIR}/mcp_server.py" \
        --with-hooks --data-path "${DATA_DIR}" --hooks-port "${HOOKS_PORT}"
fi

# Use LTM_MCP_IMAGE if set, otherwise default to quay.io latest
IMAGE="${LTM_MCP_IMAGE:-quay.io/jsalomon/ltm-mcp-server:latest}"

# Find an available port for HTTP hooks
# This allows multiple LTM instances to run simultaneously
find_available_port() {
    # Try to find an available port in the range 9900-9999
    for port in $(shuf -i 9900-9999 -n 100); do
        # Check if port is in use using ss (preferred) or netstat
        if command -v ss &>/dev/null; then
            ss -tln 2>/dev/null | grep -qE ":${port}[[:space:]]" && continue
        elif command -v netstat &>/dev/null; then
            netstat -tln 2>/dev/null | grep -qE ":${port}[[:space:]]" && continue
        fi
        # Port is available
        echo "$port"
        return 0
    done
    # Fallback: let the OS choose
    python3 -c "import socket; s=socket.socket(); s.bind(('',0)); print(s.getsockname()[1]); s.close()" 2>/dev/null || echo "9999"
}

HOOKS_PORT=$(find_available_port)

# Write server.json so hooks know where to connect
SERVER_JSON="${DATA_DIR}/server.json"
echo "{\"hooks_port\": ${HOOKS_PORT}, \"hooks_host\": \"127.0.0.1\"}" > "$SERVER_JSON"

# Clean up server.json on exit
cleanup() {
    rm -f "$SERVER_JSON" 2>/dev/null
}
trap cleanup EXIT

# Read installed plugins file content (for installed plugin mode)
PLUGINS_FILE="${HOME}/.claude/plugins/installed_plugins.json"
if [ -f "$PLUGINS_FILE" ]; then
    INSTALLED_PLUGINS_B64=$(cat "$PLUGINS_FILE" | base64 -w0)
else
    INSTALLED_PLUGINS_B64=""
fi

# Read plugin.json content (for development mode)
# Try CLAUDE_PLUGIN_ROOT first, then PROJECT_ROOT
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" ]; then
    PLUGIN_JSON_B64=$(cat "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json" | base64 -w0)
elif [ -f "${PROJECT_ROOT}/.claude-plugin/plugin.json" ]; then
    PLUGIN_JSON_B64=$(cat "${PROJECT_ROOT}/.claude-plugin/plugin.json" | base64 -w0)
else
    PLUGIN_JSON_B64=""
fi

# Build environment variable arguments
ENV_ARGS="-e LTM_HOST_PATH=${DATA_DIR}"
[ -n "$INSTALLED_PLUGINS_B64" ] && ENV_ARGS="$ENV_ARGS -e LTM_INSTALLED_PLUGINS_B64=${INSTALLED_PLUGINS_B64}"
[ -n "$PLUGIN_JSON_B64" ] && ENV_ARGS="$ENV_ARGS -e LTM_PLUGIN_JSON_B64=${PLUGIN_JSON_B64}"

# Build volume mount arguments
VOL_ARGS="-v ${DATA_DIR}:/data:Z"

# Run container in stdio mode with hooks server enabled
# Dynamic port mapping allows multiple instances to run simultaneously
exec $RUNTIME run -i --rm \
    --userns=keep-id \
    -p "127.0.0.1:${HOOKS_PORT}:9999" \
    $ENV_ARGS \
    $VOL_ARGS \
    "$IMAGE" --with-hooks
