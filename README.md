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

## Setup

Requires Python ≥ 3.10.

```bash
cd mcp
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # or: pip install -e .

cp .env.example .env                      # then edit GREEKS_API_KEY
```

Get an API key by registering (`POST /api/auth/register`), logging in
(`POST /api/auth/login`), then creating a key (`POST /api/auth/keys`). The key
looks like `grk_<48 hex>` and goes in the `X-API-Key` header — this server handles
that for you once `GREEKS_API_KEY` is set.

## Configuration

| Env var | Required | Default | Description |
|---|---|---|---|
| `GREEKS_API_KEY` | yes | — | Your `grk_...` key |
| `GREEKS_BASE_URL` | no | `https://api.greeks.pro` | API base URL; use `http://localhost:8080` for local dev |
| `GREEKS_TIMEOUT` | no | `30` | Per-request timeout (s) |
| `MCP_TRANSPORT` | no | `stdio` | `stdio` (for clients) or `http` |

## Run

```bash
# stdio (what MCP clients spawn)
GREEKS_API_KEY=grk_... python server.py

# or over HTTP
GREEKS_API_KEY=grk_... MCP_TRANSPORT=http python server.py
```

### Claude Desktop / Claude Code

Add to your MCP config (`claude_desktop_config.json` or the client's
`mcpServers` block):

```json
{
  "mcpServers": {
    "greeks-analytics": {
      "command": "python",
      "args": ["/absolute/path/to/ws_aetherfy/mcp/server.py"],
      "env": {
        "GREEKS_API_KEY": "grk_your_key_here"
      }
    }
  }
}
```

Point `GREEKS_BASE_URL` at `http://localhost:8080` in the `env` block to develop
against a locally running server (`go run main.go` from the repo root).

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
