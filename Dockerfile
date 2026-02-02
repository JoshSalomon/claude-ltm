# LTM MCP Server Container
#
# Pre-built image available at: quay.io/jsalomon/ltm-mcp-server
#
# Pull:
#   podman pull quay.io/jsalomon/ltm-mcp-server:latest
#
# Build locally:
#   podman build -t ltm-mcp-server .
#
# Run modes:
#
# 1. stdio mode (default, for MCP registration):
#   podman run -i --rm --userns=keep-id -v "$(pwd)/.claude/ltm:/data:Z" ltm-mcp-server
#
# 2. server mode (persistent container with TCP MCP + HTTP hooks):
#   podman run -d --name ltm-server --userns=keep-id \
#     -v "$(pwd)/.claude/ltm:/data:Z" \
#     -p 8765:8765 -p 9999:9999 \
#     ltm-mcp-server --server

FROM python:3.12-slim

# Set labels
LABEL org.opencontainers.image.title="LTM MCP Server"
LABEL org.opencontainers.image.description="Long-Term Memory MCP Server for Claude Code"
LABEL org.opencontainers.image.version="0.1.0"

# Set working directory
WORKDIR /app

# Fix OpenSSL vulnerability - install patched versions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libssl3t64=3.5.4-1~deb13u2 \
        openssl=3.5.4-1~deb13u2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip to fix CVE in pip 25.0.1 (fixed in 25.3+)
RUN pip install --no-cache-dir --upgrade pip>=25.3

# Install dependencies first (for better caching)
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code from server/ directory
COPY server/priority.py .
COPY server/store.py .
COPY server/eviction.py .
COPY server/mcp_server.py .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash ltm && \
    chown -R ltm:ltm /app

# Switch to non-root user
USER ltm

# Data volume mount point
# The container expects data to be mounted at /data
ENV LTM_DATA_PATH=/data

# Set Python to run unbuffered for proper stdio handling
ENV PYTHONUNBUFFERED=1

# Expose ports for server mode
# 8765 - MCP JSON-RPC over TCP
# 9999 - HTTP hooks server
EXPOSE 8765 9999

# Health check - verify Python and mcp are available
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mcp; import store; import priority; print('OK')" || exit 1

# Default command runs the MCP server in stdio mode
# Use --server for persistent server mode
ENTRYPOINT ["python", "mcp_server.py"]
