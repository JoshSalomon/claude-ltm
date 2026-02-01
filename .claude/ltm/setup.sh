#!/bin/bash
#
# LTM Setup Script - Sets up Long-Term Memory for Claude Code
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/JoshSalomon/claude-ltm/main/.claude/ltm/setup.sh | bash
#
# Or if you have the repo:
#   bash .claude/ltm/setup.sh
#
# This script:
#   1. Creates project-specific container name and ports
#   2. Pulls/creates the LTM container from quay.io
#   3. Registers MCP with Claude Code
#   4. Downloads slash commands (/remember, /recall, /forget, /ltm)
#   5. Creates server.json for container management
#
# After running, start Claude Code and run: /ltm init
# This configures hooks and updates CLAUDE.md
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     LTM - Long-Term Memory for Claude      ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
echo

# Check prerequisites
check_prerequisites() {
    local missing=0

    if ! command -v podman &> /dev/null && ! command -v docker &> /dev/null; then
        echo -e "${RED}✗ podman or docker not found${NC}"
        missing=1
    else
        if command -v podman &> /dev/null; then
            CONTAINER_CMD="podman"
        else
            CONTAINER_CMD="docker"
        fi
        echo -e "${GREEN}✓ Container runtime: $CONTAINER_CMD${NC}"
    fi

    if ! command -v claude &> /dev/null; then
        echo -e "${RED}✗ claude CLI not found${NC}"
        missing=1
    else
        echo -e "${GREEN}✓ Claude Code CLI found${NC}"
    fi

    if ! command -v curl &> /dev/null; then
        echo -e "${RED}✗ curl not found${NC}"
        missing=1
    else
        echo -e "${GREEN}✓ curl found${NC}"
    fi

    if ! command -v jq &> /dev/null; then
        echo -e "${YELLOW}⚠ jq not found (optional, for /ltm start/stop)${NC}"
    else
        echo -e "${GREEN}✓ jq found${NC}"
    fi

    if [ $missing -eq 1 ]; then
        echo
        echo -e "${RED}Please install missing prerequisites and try again.${NC}"
        exit 1
    fi
    echo
}

# Generate project-specific identifiers
generate_project_ids() {
    # Get hash of current directory for unique naming
    PROJECT_HASH=$(echo "$(pwd)" | cksum | cut -d' ' -f1)
    SHORT_HASH=$(printf '%08x' $PROJECT_HASH | cut -c1-8)

    # Container name
    CONTAINER_NAME="ltm-${SHORT_HASH}"

    # Ports derived from hash (avoid common ports)
    MCP_PORT=$((10000 + (PROJECT_HASH % 10000)))
    HOOKS_PORT=$((20000 + (PROJECT_HASH % 10000)))

    echo -e "${BLUE}Project Configuration:${NC}"
    echo "  Directory:      $(pwd)"
    echo "  Container:      $CONTAINER_NAME"
    echo "  MCP Port:       $MCP_PORT"
    echo "  Hooks Port:     $HOOKS_PORT"
    echo
}

# Create directory structure
create_directories() {
    echo -e "${BLUE}Creating directories...${NC}"
    mkdir -p .claude/ltm/memories
    mkdir -p .claude/ltm/archives
    mkdir -p .claude/commands
    echo -e "${GREEN}✓ Directories created${NC}"
}

# Download slash commands only (hooks are handled by container via HTTP)
download_commands() {
    echo -e "${BLUE}Downloading slash commands...${NC}"

    BASE_URL="https://raw.githubusercontent.com/JoshSalomon/claude-ltm/main"

    # Slash commands only - hooks run in container via HTTP
    for cmd in remember.md recall.md forget.md ltm.md; do
        curl -sSL "$BASE_URL/.claude/commands/$cmd" -o ".claude/commands/$cmd"
    done
    echo -e "${GREEN}✓ Slash commands downloaded${NC}"
}

# Create server.json configuration
create_server_config() {
    echo -e "${BLUE}Creating server configuration...${NC}"

    cat > .claude/ltm/server.json << EOF
{
  "container_name": "$CONTAINER_NAME",
  "mcp_port": $MCP_PORT,
  "hooks_port": $HOOKS_PORT,
  "image": "quay.io/jsalomon/ltm-mcp-server:latest",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF
    echo -e "${GREEN}✓ server.json created${NC}"
}

# Pull container image
pull_image() {
    echo -e "${BLUE}Pulling container image...${NC}"
    $CONTAINER_CMD pull quay.io/jsalomon/ltm-mcp-server:latest
    echo -e "${GREEN}✓ Image pulled${NC}"
}

# Create the container
create_container() {
    echo -e "${BLUE}Creating container...${NC}"

    # Remove existing container if it exists
    $CONTAINER_CMD rm -f "$CONTAINER_NAME" 2>/dev/null || true

    # Create the container
    $CONTAINER_CMD create \
        --name "$CONTAINER_NAME" \
        --userns=keep-id \
        -v "$(pwd)/.claude/ltm:/data:Z" \
        -p "$MCP_PORT:8765" \
        -p "$HOOKS_PORT:9999" \
        quay.io/jsalomon/ltm-mcp-server:latest \
        --server

    echo -e "${GREEN}✓ Container created: $CONTAINER_NAME${NC}"
}

# Create helper scripts and register MCP
register_mcp() {
    echo -e "${BLUE}Creating helper scripts...${NC}"

    # ltm-start.sh - starts container and connects MCP
    cat > .claude/ltm/ltm-start.sh << 'EOF'
#!/bin/bash
# LTM Start - starts container if needed and connects MCP via socat

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$SCRIPT_DIR/server.json"

if [ ! -f "$CFG" ]; then
    echo "Error: server.json not found. Run setup.sh first." >&2
    exit 1
fi

CONTAINER=$(jq -r .container_name "$CFG")
PORT=$(jq -r .mcp_port "$CFG")
HOOKS_PORT=$(jq -r .hooks_port "$CFG")
IMAGE=$(jq -r .image "$CFG")

# Determine container runtime
if command -v podman &> /dev/null; then
    RUNTIME=podman
else
    RUNTIME=docker
fi

# Check if container exists, create if not
if ! $RUNTIME container exists "$CONTAINER" 2>/dev/null; then
    # Container doesn't exist, create it
    $RUNTIME create --name "$CONTAINER" \
        --userns=keep-id \
        -v "$SCRIPT_DIR:/data:Z" \
        -p "$PORT:8765" -p "$HOOKS_PORT:9999" \
        "$IMAGE" --server >/dev/null 2>&1
fi

# Start container if not running
$RUNTIME start "$CONTAINER" 2>/dev/null || true

# Wait for container to be ready
sleep 1

# Connect via socat (or nc as fallback) - use 127.0.0.1 to avoid IPv6 issues
if command -v socat &> /dev/null; then
    exec socat - TCP:127.0.0.1:$PORT
elif command -v nc &> /dev/null; then
    exec nc 127.0.0.1 $PORT
else
    echo "Error: socat or nc required" >&2
    exit 1
fi
EOF
    chmod +x .claude/ltm/ltm-start.sh

    # ltm-stop.sh - stops the container (for use outside Claude Code)
    cat > .claude/ltm/ltm-stop.sh << 'EOF'
#!/bin/bash
# LTM Stop - stops the LTM container
# Use this when Claude Code is not running to stop the container

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="$SCRIPT_DIR/server.json"

if [ ! -f "$CFG" ]; then
    echo "Error: server.json not found" >&2
    exit 1
fi

CONTAINER=$(jq -r .container_name "$CFG")

if command -v podman &> /dev/null; then
    podman stop "$CONTAINER" 2>/dev/null
    echo "Container $CONTAINER stopped"
else
    docker stop "$CONTAINER" 2>/dev/null
    echo "Container $CONTAINER stopped"
fi
EOF
    chmod +x .claude/ltm/ltm-stop.sh

    echo -e "${GREEN}✓ Helper scripts created (ltm-start.sh, ltm-stop.sh)${NC}"

    # Register MCP with Claude Code
    echo -e "${BLUE}Registering MCP with Claude Code...${NC}"
    claude mcp remove ltm 2>/dev/null || true
    claude mcp add --transport stdio ltm -- bash "$(pwd)/.claude/ltm/ltm-start.sh"

    echo -e "${GREEN}✓ MCP registered${NC}"
}


# Update .gitignore
update_gitignore() {
    echo -e "${BLUE}Updating .gitignore...${NC}"

    if [ -f .gitignore ]; then
        if ! grep -q ".claude/ltm/stats.json" .gitignore; then
            echo "" >> .gitignore
            echo "# LTM volatile files" >> .gitignore
            echo ".claude/ltm/stats.json" >> .gitignore
            echo ".claude/ltm/state.json" >> .gitignore
            echo ".claude/ltm/server.json" >> .gitignore
        fi
    else
        cat > .gitignore << EOF
# LTM volatile files
.claude/ltm/stats.json
.claude/ltm/state.json
.claude/ltm/server.json
EOF
    fi
    echo -e "${GREEN}✓ .gitignore updated${NC}"
}

# Start the container
start_container() {
    echo -e "${BLUE}Starting container...${NC}"
    $CONTAINER_CMD start "$CONTAINER_NAME"
    sleep 2

    # Verify it's running
    if $CONTAINER_CMD ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
        echo -e "${GREEN}✓ Container running${NC}"
    else
        echo -e "${YELLOW}⚠ Container may not have started correctly${NC}"
    fi
}

# Print summary
print_summary() {
    echo
    echo -e "${GREEN}╔════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║          LTM Setup Complete!               ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════╝${NC}"
    echo
    echo -e "${BLUE}Container:${NC}"
    echo "  Name:   $CONTAINER_NAME"
    echo "  MCP:    localhost:$MCP_PORT"
    echo "  Hooks:  localhost:$HOOKS_PORT"
    echo
    echo -e "${BLUE}Scripts:${NC}"
    echo "  .claude/ltm/ltm-start.sh  - Start container (called by Claude Code)"
    echo "  .claude/ltm/ltm-stop.sh   - Stop container (run from terminal)"
    echo
    echo -e "${BLUE}Container Management:${NC}"
    echo "  Stop:   bash .claude/ltm/ltm-stop.sh"
    echo "  Logs:   $CONTAINER_CMD logs $CONTAINER_NAME"
    echo
    echo -e "${YELLOW}Next Step:${NC}"
    echo "  1. Start Claude Code in this directory"
    echo "  2. Run: /ltm init"
    echo "     This configures hooks and updates CLAUDE.md"
    echo
}

# Main
main() {
    check_prerequisites
    generate_project_ids
    create_directories
    download_commands
    create_server_config
    pull_image
    create_container
    register_mcp
    update_gitignore
    start_container
    print_summary
}

main "$@"
