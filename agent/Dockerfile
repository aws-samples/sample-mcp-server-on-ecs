# =============================================================================
# Agent Service Dockerfile
# Production-ready container for MCP Agent REST API on ECS Fargate
# =============================================================================

FROM python:3.12-slim

# =============================================================================
# METADATA
# =============================================================================
LABEL maintainer="smanubol@amazon.com" \
      description="Agent Service for MCP Product Catalog Search" \
      version="1.0"

# =============================================================================
# WORKING DIRECTORY
# =============================================================================
WORKDIR /app

# =============================================================================
# SYSTEM DEPENDENCIES
# Install minimal packages and clean up to reduce image size
# - curl: Required for health checks
# - ca-certificates: Required for HTTPS connections
# =============================================================================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# =============================================================================
# PYTHON DEPENDENCIES
# Copy requirements first for Docker layer caching optimization
# =============================================================================
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# APPLICATION CODE
# =============================================================================
COPY app/ /app/

# =============================================================================
# NON-ROOT USER (Security Best Practice)
# Create dedicated user for running the application
# =============================================================================
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# =============================================================================
# NETWORK CONFIGURATION
# Expose Agent REST API port
# =============================================================================
EXPOSE 3000

# =============================================================================
# HEALTH CHECK
# ECS uses this to determine container health
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD curl -f http://localhost:3000/health || exit 1

# =============================================================================
# ENVIRONMENT VARIABLES
# Defaults for ECS Service Connect configuration
# =============================================================================
ENV MCP_SERVER_ENDPOINT=http://mcp-server:8080 \
    LOG_LEVEL=INFO \
    PORT=3000

# =============================================================================
# STARTUP COMMAND
# Using CMD for flexibility with ECS task definition overrides
# =============================================================================
CMD ["python", "agent.py"]
