# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/), and this project adheres to
[Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-07-25

Initial release.

### Added
- MCP server exposing the Greeks options-analytics API as 12 tools:
  - Analytics: `get_max_pain`, `get_greeks`, `get_gex`, `get_flow`,
    `get_overview`, `get_snapshot`, `get_levels`.
  - Public data: `screener`, `gex_heatmap`, `track_record`.
  - Utility: `list_plans`, `health`.
- API-key auth via `GREEKS_API_KEY` (only required for `/api/analytics/*`;
  public tools work without a key).
- Configurable base URL (`GREEKS_BASE_URL`), timeout (`GREEKS_TIMEOUT`), and
  transport (`MCP_TRANSPORT`: stdio or http).
- Actionable error mapping for 401/402/403/404/429/timeouts.
- `greeks-mcp` console script and `python -m greeks_mcp` entry points.
- Ready-to-copy client configs for Claude Desktop and Cursor.
- Smoke test (tool wiring) and end-to-end test (spawns the server over stdio and
  exercises all 12 tools through the MCP protocol).
