# =============================================================================
# MCP Server Dockerfile
# Production-ready container for Amazon ECS Fargate deployment
# =============================================================================

FROM python:3.12-slim

# -----------------------------------------------------------------------------
# Image Metadata
# -----------------------------------------------------------------------------
LABEL maintainer="smanubol@amazon.com" \
      description="MCP Server for Product Catalog Search - Runs on ECS Fargate" \
      version="1.0" \
      org.opencontainers.image.source="https://github.com/aws-samples/mcp-ecs-blog"

# -----------------------------------------------------------------------------
# Set Working Directory
# -----------------------------------------------------------------------------
WORKDIR /app

# -----------------------------------------------------------------------------
# Install System Dependencies
# - curl: Required for health checks
# - ca-certificates: Required for HTTPS connections to AWS services (S3)
# - Clean up apt cache to minimize image size
# -----------------------------------------------------------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# -----------------------------------------------------------------------------
# Install Python Dependencies
# - Copy requirements.txt first for Docker layer caching
# - Upgrade pip to latest version
# - Install packages without cache to reduce image size
# -----------------------------------------------------------------------------
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# -----------------------------------------------------------------------------
# Copy Application Code
# - Copy app directory containing mcp_server.py
# -----------------------------------------------------------------------------
COPY app/ ./app/

# -----------------------------------------------------------------------------
# Create Non-Root User (Security Best Practice)
# - ECS Fargate runs containers as root by default
# - Running as non-root user reduces attack surface
# - UID 1000 is standard for application users
# -----------------------------------------------------------------------------
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# -----------------------------------------------------------------------------
# Network Configuration
# - Expose port 8080 for MCP server HTTP/SSE transport
# -----------------------------------------------------------------------------
EXPOSE 8080

# -----------------------------------------------------------------------------
# Health Check Configuration
# - ECS uses this to determine container health
# - Interval: Check every 30 seconds
# - Timeout: Fail if no response within 10 seconds
# - Retries: Mark unhealthy after 3 consecutive failures
# - Start Period: Allow 40 seconds for initial S3 catalog load
# -----------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=40s \
    CMD curl -f http://localhost:8080/health || exit 1

# -----------------------------------------------------------------------------
# Environment Variables
# - S3_BUCKET: Set by ECS task definition (no default)
# - AWS_REGION: Default to us-west-2
# - CATALOG_FILE: S3 object key for product catalog
# - LOG_LEVEL: Python logging level
# - PYTHONUNBUFFERED: Ensure logs are sent to CloudWatch immediately
# - PYTHONDONTWRITEBYTECODE: Don't create .pyc files in container
# -----------------------------------------------------------------------------
ENV AWS_REGION=us-west-2 \
    CATALOG_FILE=product-catalog.json \
    LOG_LEVEL=INFO \
    HOST=0.0.0.0 \
    PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# -----------------------------------------------------------------------------
# Startup Command
# - Use CMD for flexibility (can be overridden in ECS task definition)
# - Run as Python module to ensure proper imports
# -----------------------------------------------------------------------------
CMD ["python", "-m", "app.mcp_server"]
