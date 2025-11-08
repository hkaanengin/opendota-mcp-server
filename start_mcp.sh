#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Change to the project directory
cd "$SCRIPT_DIR"

# Check if virtual environment exists and use it, otherwise use system python
if [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python -m opendota_mcp.server
else
    exec python3 -m opendota_mcp.server
fi
