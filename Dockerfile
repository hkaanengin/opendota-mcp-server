# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml and install dependencies
COPY pyproject.toml .

# Install the package and its dependencies
RUN pip install --no-cache-dir -e .

# Copy application code (including tools folder)
COPY opendota_mcp/ ./opendota_mcp/

# Environment variables with sensible defaults
ENV PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=auto \
    PORT=8080 \
    HOST=0.0.0.0 \
    LOG_LEVEL=INFO

# Expose port
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=15s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the server using the installed entry point
CMD ["python", "-m", "opendota_mcp.server"]