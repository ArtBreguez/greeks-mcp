# Greeks / Aetherfy — MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes the
**Greeks Analytics API** (derived options data) as tools for any MCP client —
Claude Desktop, Cursor, Claude Code, etc. Ask an assistant for GEX, Greeks, Max
Pain, unusual flow or a full dashboard on any ticker and it pulls live from the API.

Only the **commercial `/api/analytics/*`** surface is wrapped. Raw-data
`/internal/*` routes are intentionally **not** exposed — they are internal-only and
not part of the commercial offering.

## Tools

| Tool | Endpoint | Min plan | What it returns |
|---|---|---|---|
| `get_max_pain` | `/api/analytics/maxpain` | Free | Max Pain strike per expiration |
| `get_greeks` | `/api/analytics/greeks` | Trader | Δ Γ Θ V ρ, theo price, mispricing per contract |
| `get_gex` | `/api/analytics/gex` | Trader | GEX/DEX per strike, total Net GEX, Gamma Flip |
| `get_flow` | `/api/analytics/flow` | Trader | Unusual-activity signals |
| `get_overview` | `/api/analytics/overview` | Pro | Full dashboard (sentiment, GEX, max pain, expected move, IV surface, term structure, top flow) |
| `get_snapshot` | `/api/analytics/snapshot` | — | Compact analytics snapshot |
| `get_levels` | `/api/analytics/levels` | — | Options-derived support/resistance levels |
| `screener` | `/api/public/screener` | public | Watchlist screener — discover interesting symbols |
| `gex_heatmap` | `/api/public/gex-heatmap` | public | GEX-by-strike heatmap for a watchlist symbol |
| `track_record` | `/api/public/track-record` | public | Aggregated signal accuracy (~last 35 days) |
| `list_plans` | `/api/billing/plans` | public | Plans, prices, limits, routes |
| `health` | `/health` | public | Service health |

All analytics tools take `symbol` (required) and optional `expiration` (a Unix
timestamp, or `"all"` for every expiration; omit for the nearest expiry).
`get_greeks` also accepts `range="atm"`, `moneyness="low,high"` and `limit`.

## Quickstart (users)

You don't host anything. This server runs **on your machine**, spawned by your AI
client (Claude Desktop, Cursor, …), and talks to the Greeks API using your key.

**1. Get an API key.** Sign up, then create a key — it looks like `grk_<48 hex>`.
(Register `POST /api/auth/register` → login `POST /api/auth/login` → create key
`POST /api/auth/keys`, or grab it from your account dashboard.)

**2. Add one block to your client config** and restart the client. Pick the
snippet matching what you have installed:

**With [uv](https://docs.astral.sh/uv/) (recommended — no manual install):**
```json
{
  "mcpServers": {
    "greeks-analytics": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/ArtBreguez/ws_aetherfy.git#subdirectory=mcp", "greeks-mcp"],
      "env": { "GREEKS_API_KEY": "grk_your_key_here" }
    }
  }
}
```

**With pipx:**
```bash
pipx install "git+https://github.com/ArtBreguez/ws_aetherfy.git#subdirectory=mcp"
```
```json
{
  "mcpServers": {
    "greeks-analytics": {
      "command": "greeks-mcp",
      "env": { "GREEKS_API_KEY": "grk_your_key_here" }
    }
  }
}
```

That's it — the assistant now has all 12 tools. `uvx` downloads, builds and runs
the server on demand in an isolated environment, so there's nothing to install or
keep updated by hand.

> Claude Desktop's config lives at `~/Library/Application Support/Claude/claude_desktop_config.json`
> (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows). Cursor and
> other clients have an equivalent `mcpServers` block.

## Configuration

| Env var | Required | Default | Description |
|---|---|---|---|
| `GREEKS_API_KEY` | for `/api/analytics/*` | — | Your `grk_...` key. Public tools (screener, health, plans, gex_heatmap, track_record) work without it. |
| `GREEKS_BASE_URL` | no | `https://api.greeks.pro` | API base URL; use `http://localhost:8080` for local dev |
| `GREEKS_TIMEOUT` | no | `30` | Per-request timeout (s) |
| `MCP_TRANSPORT` | no | `stdio` | `stdio` (for clients) or `http` |

## Run manually / from source

```bash
cd mcp
python -m venv .venv && source .venv/bin/activate
pip install -e .            # or: pip install -r requirements.txt

# stdio (what MCP clients spawn)
GREEKS_API_KEY=grk_... greeks-mcp        # or: python server.py

# or over HTTP
GREEKS_API_KEY=grk_... MCP_TRANSPORT=http greeks-mcp
```

To point at a locally running backend (`go run main.go` from the repo root), set
`GREEKS_BASE_URL=http://localhost:8080` in the `env` block or your shell.

## Development

```bash
# Inspect the tools interactively without a full client:
pip install "mcp[cli]"
mcp dev server.py

# Smoke-test the tool wiring (no network needed):
python test_server.py
```

## Notes

- **Plans & errors:** a `402`/`403` means your plan doesn't include that route (or
  you hit the symbol/rate limit). Call `list_plans` to see what each tier unlocks.
- **`expiration="all"`** returns every expiration — richer but slower. For heavy
  names prefer a specific expiration timestamp, or raise `GREEKS_TIMEOUT`.
- **Derived data only.** No raw market data (quotes, bid/ask, OI, contract prices)
  is redistributed — everything here is computed analytics.
