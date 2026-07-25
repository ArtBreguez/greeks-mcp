"""
Greeks / Aetherfy Analytics — MCP server.

Exposes the commercial (derived-data) endpoints of the Greeks Analytics API as
Model Context Protocol tools so any MCP client (Claude Desktop, Cursor, etc.) can
pull real-time options analytics — Greeks, GEX/DEX, Max Pain, Flow, IV surface,
Expected Move, Sentiment — straight into a conversation.

Only the commercial /api/analytics/* surface is wrapped. Raw-data /internal/*
routes are intentionally NOT exposed: they are internal-only and not part of the
commercial offering.

Auth: set GREEKS_API_KEY (the grk_<48hex> key from POST /api/auth/keys). The base
URL defaults to the public API and can be overridden with GREEKS_BASE_URL for
local dev (http://localhost:8080).

Run:
    GREEKS_API_KEY=grk_... python server.py

Transport is stdio by default (what MCP clients spawn). Set MCP_TRANSPORT=http to
serve over streamable HTTP instead.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx
from mcp.server.fastmcp import FastMCP

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_BASE_URL = "https://api.greeks.pro"

BASE_URL = os.environ.get("GREEKS_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
API_KEY = os.environ.get("GREEKS_API_KEY", "").strip()
# Seconds. Analytics with expiration=all can be slow (full chain), so keep this
# generous but bounded.
TIMEOUT = float(os.environ.get("GREEKS_TIMEOUT", "30"))

mcp = FastMCP("greeks-analytics")


# ─────────────────────────────────────────────────────────────────────────────
# HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

class GreeksAPIError(RuntimeError):
    """Raised with a human-readable message when the API returns a non-2xx."""


def _headers() -> dict[str, str]:
    if not API_KEY:
        raise GreeksAPIError(
            "GREEKS_API_KEY is not set. Create a key at POST /api/auth/keys and "
            "export it as GREEKS_API_KEY (format grk_<48 hex>)."
        )
    return {"X-API-Key": API_KEY, "Accept": "application/json"}


def _explain_status(status: int, body: str) -> str:
    """Map the API's status codes to actionable guidance."""
    hints = {
        400: "Bad request — check the symbol / expiration parameters.",
        401: "Unauthorized — GREEKS_API_KEY is missing or invalid.",
        402: "Payment required — this endpoint needs a higher plan.",
        403: "Forbidden — your plan does not include this route, or the symbol "
             "count / rate limit for your plan was exceeded.",
        404: "Not found — no options chain available for that symbol/expiration.",
        429: "Rate limited — you exceeded your plan's requests-per-minute.",
        500: "Server error — try again shortly.",
    }
    hint = hints.get(status, "")
    body = (body or "").strip()
    if len(body) > 500:
        body = body[:500] + "…"
    parts = [f"HTTP {status}"]
    if hint:
        parts.append(hint)
    if body:
        parts.append(f"Response: {body}")
    return " ".join(parts)


def _get(path: str, params: dict[str, Any]) -> Any:
    """GET {BASE_URL}{path} with the API key, returning parsed JSON.

    Drops params whose value is None/empty so we never send blank query args.
    """
    clean = {k: v for k, v in params.items() if v not in (None, "")}
    url = f"{BASE_URL}{path}"
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.get(url, params=clean, headers=_headers())
    except httpx.TimeoutException as exc:
        raise GreeksAPIError(
            f"Request to {path} timed out after {TIMEOUT}s. For heavy symbols try "
            f"a specific expiration instead of 'all'."
        ) from exc
    except httpx.HTTPError as exc:
        raise GreeksAPIError(f"Network error calling {path}: {exc}") from exc

    if resp.status_code // 100 != 2:
        raise GreeksAPIError(_explain_status(resp.status_code, resp.text))

    try:
        return resp.json()
    except ValueError as exc:
        raise GreeksAPIError(
            f"API returned non-JSON body from {path}: {resp.text[:200]}"
        ) from exc


def _analytics(path: str, symbol: str, expiration: Optional[str] = None,
               **extra: Any) -> Any:
    sym = (symbol or "").strip().upper()
    if not sym:
        raise GreeksAPIError("A non-empty 'symbol' is required (e.g. AAPL, SPY).")
    params: dict[str, Any] = {"symbol": sym, "expiration": expiration}
    params.update(extra)
    return _get(path, params)


# ─────────────────────────────────────────────────────────────────────────────
# Tools — commercial analytics (derived data only)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def get_max_pain(symbol: str, expiration: Optional[str] = None) -> Any:
    """Max Pain per expiration — the strike that minimizes total option value
    (where most options expire worthless), a magnet the price tends to converge
    toward at expiration.

    Plan: Free (1 symbol, 15-min delay) and up.

    Args:
        symbol: Underlying ticker, e.g. "AAPL", "SPY", "NDAQ".
        expiration: Unix expiration timestamp for a single expiry, or "all" for
            every expiration (slower, complete). Omit for the nearest expiry.

    Returns the raw MaxPainResponse JSON: symbol, spotPrice, timestamp, and
    results[] with maxPainStrike, totalPainAtMax, spotDistance, spotDistancePct.
    """
    return _analytics("/api/analytics/maxpain", symbol, expiration)


@mcp.tool()
def get_greeks(
    symbol: str,
    expiration: Optional[str] = None,
    range: Optional[str] = None,
    moneyness: Optional[str] = None,
    limit: Optional[int] = None,
) -> Any:
    """Black-Scholes Greeks (Delta, Gamma, Theta, Vega, Rho) plus theoretical
    price and mispricing for every contract in the chain.

    Plan: Trader and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.
        range: Pass "atm" to restrict the chain to at-the-money contracts.
        moneyness: A "low,high" pair (e.g. "0.9,1.1") to filter contracts by
            strike/spot ratio.
        limit: Cap the number of contracts returned (per side).

    Returns GreeksResponse JSON: symbol, spotPrice, timestamp, and contracts[]
    each with delta/gamma/theta/vega/rho, iv, theoreticalPrice, mispricing,
    inTheMoney.
    """
    return _analytics(
        "/api/analytics/greeks", symbol, expiration,
        range=range, moneyness=moneyness, limit=limit,
    )


@mcp.tool()
def get_gex(symbol: str, expiration: Optional[str] = None,
            symbols: Optional[str] = None) -> Any:
    """Gamma & Delta Exposure (GEX/DEX) per strike, plus total Net GEX and the
    Gamma Flip level (strike where Net GEX crosses zero — a regime transition).
    Positive Net GEX = dealers long gamma (price pins); negative = moves amplified.

    Plan: Trader and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.
        symbols: Optional comma-separated list for a multi-symbol GEX request
            (e.g. "SPY,QQQ,IWM"); when set it takes precedence over `symbol`.

    Returns GEXResponse JSON: symbol, spotPrice, timestamp, totalNetGEX,
    gammaFlip, and strikes[] with callGEX/putGEX/netGEX and callDEX/putDEX/netDEX.
    """
    extra = {"symbols": symbols} if symbols else {}
    return _analytics("/api/analytics/gex", symbol, expiration, **extra)


@mcp.tool()
def get_flow(symbol: str, expiration: Optional[str] = None) -> Any:
    """Unusual options activity detection — contracts with abnormally high
    volume relative to open interest, typically signalling institutional/"smart
    money" positioning.

    Signals: unusual_volume (high: Vol/OI ≥ 3.0, medium: ≥ 1.5) and
    opening_position (Vol ≥ 50 with OI = 0). Contracts with volume < 10 are noise.

    Plan: Trader and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns FlowResponse JSON: symbol, spotPrice, timestamp, and signals[] each
    with contractSymbol, type, strike, expiration, dte, volumeOIRatio, iv,
    signal, severity.
    """
    return _analytics("/api/analytics/flow", symbol, expiration)


@mcp.tool()
def get_overview(symbol: str, expiration: Optional[str] = None) -> Any:
    """Full analytics dashboard for a symbol in one call: sentiment, GEX summary,
    max pain, expected moves, IV surface, term structure and top unusual flow.
    The cheapest way to get everything for a symbol at once.

    Plan: Pro and up.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all" (recommended
            for the full dashboard). Omit for the nearest expiry.

    Returns OverviewResponse JSON: symbol, spotPrice, timestamp, riskFreeRate,
    dividendYield, sentiment, gexSummary, maxPain[], expectedMoves[],
    termStructure[], ivSurface[], topFlow[].
    """
    return _analytics("/api/analytics/overview", symbol, expiration)


@mcp.tool()
def get_snapshot(symbol: str, expiration: Optional[str] = None) -> Any:
    """Compact analytics snapshot for a symbol — a lighter-weight summary than
    the full overview, suitable for quick checks and cards.

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns the SnapshotResponse JSON as computed by the analytics engine.
    """
    return _analytics("/api/analytics/snapshot", symbol, expiration)


@mcp.tool()
def get_levels(symbol: str, expiration: Optional[str] = None) -> Any:
    """Key options-derived price levels for a symbol (support/resistance style
    levels from gamma and open-interest structure).

    Args:
        symbol: Underlying ticker.
        expiration: Unix timestamp of a specific expiry, or "all". Omit for the
            nearest expiry.

    Returns the LevelsResponse JSON as computed by the analytics engine.
    """
    return _analytics("/api/analytics/levels", symbol, expiration)


# ─────────────────────────────────────────────────────────────────────────────
# Tools — account / metadata (help the model use the API correctly)
# ─────────────────────────────────────────────────────────────────────────────

@mcp.tool()
def list_plans() -> Any:
    """List the available commercial plans with prices, limits and included
    routes (Free / Trader / Pro / Institutional). Public — no key needed.

    Use this to explain to the user which analytics their plan unlocks, or why a
    call returned 402/403.
    """
    return _get("/api/billing/plans", {})


@mcp.tool()
def health() -> Any:
    """Service health check: returns {status, supabase, stripe}. Public — no key
    needed. Use to verify GREEKS_BASE_URL is reachable before other calls.
    """
    return _get("/health", {})


def main() -> None:
    """Entry point for the `greeks-mcp` console script and `python server.py`."""
    transport = os.environ.get("MCP_TRANSPORT", "stdio").strip().lower()
    if transport in ("http", "streamable-http"):
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
