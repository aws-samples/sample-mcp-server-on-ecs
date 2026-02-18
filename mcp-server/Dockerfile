# =============================================================================
# MCP Server Dockerfile
# Production-ready container for FastMCP server on ECS Fargate
# =============================================================================

FROM python:3.12-slim

# =============================================================================
# WORKING DIRECTORY
# =============================================================================
WORKDIR /app

# =============================================================================
# SYSTEM DEPENDENCIES
# Install minimal packages and clean up to reduce image size
# - curl: Required for health checks
# - ca-certificates: Required for HTTPS connections to AWS services (S3)
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
COPY app/ ./app/

# =============================================================================
# NON-ROOT USER (Security Best Practice)
# Create dedicated user for running the application
# =============================================================================
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

USER appuser

# =============================================================================
# NETWORK CONFIGURATION
# Expose MCP server HTTP/SSE transport port
# =============================================================================
EXPOSE 8080

# =============================================================================
# HEALTH CHECK
# ECS uses this to determine container health
# =============================================================================
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD curl -f http://localhost:8080/health || exit 1

# =============================================================================
# ENVIRONMENT VARIABLES
# Defaults for ECS Service Connect and S3 configuration
# =============================================================================
ENV AWS_REGION=us-west-2 \
    CATALOG_FILE=product-catalog.json \
    LOG_LEVEL=INFO \
    HOST=0.0.0.0 \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# =============================================================================
# STARTUP COMMAND
# Using CMD for flexibility with ECS task definition overrides
# =============================================================================
CMD ["python", "-m", "app.mcp_server"]
