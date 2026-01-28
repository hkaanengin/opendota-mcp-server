# Use Python 3.11 slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy pyproject.toml first (for dependency caching)
COPY pyproject.toml .

# Copy source code before install
COPY opendota_mcp/ ./opendota_mcp/

# Install the package (non-editable for production)
RUN pip install --no-cache-dir .


ENV PYTHONUNBUFFERED=1 \
    MCP_TRANSPORT=http \
    PORT=8080

# Expose port
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=15s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

# Run the server using the installed entry point
CMD ["python", "-m", "opendota_mcp.server"]