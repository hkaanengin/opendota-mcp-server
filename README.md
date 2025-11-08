# OpenDota MCP Server

A [Model Context Protocol (MCP)](https://modelcontextprotocol.io) server that provides seamless access to the [OpenDota API](https://docs.opendota.com) for querying Dota 2 player statistics, match data, and hero information through AI assistants like Claude.

## Features

- **20+ Tools** across 5 categories for comprehensive Dota 2 data access
- **Natural Language Support** - Fuzzy matching for hero names, lane positions, and stat fields
- **Dual Transport** - Supports both stdio (local) and HTTP (remote) modes
- **Rate Limiting** - Built-in protection respecting OpenDota API limits
- **Reference Data Caching** - Fast lookups with local hero/item data

## Available Tools

### Player Tools (6 tools)
Query player statistics, win/loss records, hero preferences, and performance metrics:
- `get_player_info` - Get player profile, win rate, and favorite heroes
- `get_player_win_loss` - Win/loss stats with advanced filtering
- `get_heroes_played` - Detailed statistics for all heroes played
- `get_player_peers` - Find frequent teammates
- `get_player_totals` - Aggregated player statistics
- `get_player_histograms` - Distribution of matches across statistical fields

### Hero Tools (4 tools)
Access hero information, matchups, and item builds:
- `get_heroes` - List all heroes with attributes
- `get_hero_matchups` - Matchup data and win rates
- `get_hero_item_popularity` - Popular item builds by game phase
- `get_hero_stats` - Aggregated hero statistics and pick rates

### Match Tools (3 tools)
Retrieve detailed match information and parsed data:
- `get_match_details` - Comprehensive match information
- `get_parsed_match_details` - Parsed match data with advanced analytics
- `get_player_recent_matches` - Recent matches for a player

### Lookup Tools (4 tools)
Convert names to IDs with fuzzy matching:
- `get_hero_id_by_name` - Hero name → ID (handles typos)
- `get_hero_by_id` - Get hero details by ID
- `convert_lane_name_to_id` - Lane/position → lane_role ID
- `resolve_time_name` - Time period names → OpenDota filter parameters

### Misc Tools (3 tools)
Search and utility functions:
- `search_players` - Search for players by name
- `get_constants` - Get OpenDota constants and reference data
- `get_player_counts` - Get player count by rank tier

## Installation

### Prerequisites
- Python 3.10 or higher
- pip package manager

### Install from Source

```bash
# Clone the repository
git clone https://github.com/hkaanengin/opendota-mcp-server.git
cd opendota-mcp-server

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"

# Or install runtime only
pip install -e .
```

## Usage

### Option 1: Local Server (stdio mode)

Best for Claude Desktop integration on your local machine.

#### Using Claude Desktop

**Config file location:**
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

**Recommended: Using the installed command**

After running `pip install -e .`, add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opendota": {
      "command": "/path/to/your/opendota-mcp-server/.venv/bin/opendota-mcp"
    }
  }
}
```

> **Note:** Replace `/path/to/your/opendota-mcp-server` with the actual path where you cloned this repository. On macOS/Linux, run `pwd` in the project directory to find this path. On Windows, run `cd` to see the full path.

**Alternative: Using Python module directly**

```json
{
  "mcpServers": {
    "opendota": {
      "command": "/path/to/your/opendota-mcp-server/.venv/bin/python",
      "args": ["-m", "opendota_mcp.server"]
    }
  }
}
```

**Alternative: Using the shell script**

```json
{
  "mcpServers": {
    "opendota": {
      "command": "/path/to/your/opendota-mcp-server/start_mcp.sh"
    }
  }
}
```

**Using Docker:**

```json
{
  "mcpServers": {
    "opendota": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e", "MCP_TRANSPORT=stdio",
        "yourusername/opendota-mcp-server:latest"
      ]
    }
  }
}
```

After updating the config:
1. Save the file
2. Restart Claude Desktop completely
3. Start a new conversation
4. Your OpenDota tools should now be available!

#### Manual Testing

```bash
# Run the server directly
opendota-mcp

# Or using Python module
python -m opendota_mcp.server

# Or using the shell script
./start_mcp.sh
```

### Option 2: Remote Server (HTTP mode)

Access a deployed server from anywhere.

#### Public Server

Use the publicly deployed server at:
```
https://opendota-mcp-server-jylza6gata-ew.a.run.app/mcp
```

#### Claude Desktop (Remote Connection)

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "opendota": {
      "command": "npx",
      "args": [
        "-y",
        "@modelcontextprotocol/server-remote-http",
        "https://opendota-mcp-server-jylza6gata-ew.a.run.app/mcp"
      ]
    }
  }
}
```

#### Claude.ai Web Interface

1. Go to Claude.ai → Settings → MCP Servers
2. Click "Add Server"
3. Enter Server URL: `https://opendota-mcp-server-jylza6gata-ew.a.run.app/mcp`
4. Save and start chatting!

### Option 3: Deploy Your Own

Deploy to Google Cloud Run or any container platform:

```bash
# Build Docker image
docker build -t opendota-mcp-server .

# Run in HTTP mode
docker run -p 8080:8080 \
  -e MCP_TRANSPORT=http \
  -e PORT=8080 \
  opendota-mcp-server
```

## Configuration

### Environment Variables

Create a `.env` file:

```env
# Logging level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# Transport mode (stdio or http)
MCP_TRANSPORT=stdio

# HTTP server port (for HTTP mode)
PORT=8080
```

## API Rate Limits

OpenDota API limits:
- **Anonymous**: 60 requests/minute
- **Registered**: Higher limits with API key (not required)

This server defaults to 50 req/min with automatic rate limiting and wait handling.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Acknowledgments

- [OpenDota](https://www.opendota.com/) for providing the excellent Dota 2 API
- [FastMCP](https://github.com/jlowin/fastmcp) for the MCP framework
- The Model Context Protocol team at Anthropic
- The Dota 2 community

## Support

For issues, questions, or contributions:
- Open an issue on [GitHub](https://github.com/yourusername/opendota-mcp-server/issues)
- Check existing issues for solutions
- Review the [OpenDota API documentation](https://docs.opendota.com)

---

**Made with ❤️ for the Dota 2 community**
