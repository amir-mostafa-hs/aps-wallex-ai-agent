"""FastAPI Status Dashboard and Control Interface."""
from __future__ import annotations
import time
from typing import Any, Mapping
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse

from wallex_agent.harness import SystemTradingHarness


HTML_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wallex Opportunity Agent - Status Dashboard</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 24px; background: #0f172a; color: #f8fafc; }
        .card { background: #1e293b; border-radius: 8px; padding: 20px; margin-bottom: 20px; border: 1px solid #334155; }
        h1, h2 { margin-top: 0; color: #38bdf8; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }
        .metric-box { background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #334155; }
        .metric-label { font-size: 0.85rem; color: #94a3b8; }
        .metric-val { font-size: 1.4rem; font-weight: bold; margin-top: 4px; color: #e2e8f0; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 9999px; font-weight: bold; font-size: 0.85rem; }
        .badge-running { background: #065f46; color: #34d399; }
        .badge-paused { background: #854d0e; color: #fde047; }
        .badge-safestop { background: #991b1b; color: #f87171; }
        .btn-group { display: flex; gap: 12px; margin-top: 10px; }
        button { cursor: pointer; padding: 10px 18px; border-radius: 6px; border: none; font-weight: bold; font-size: 0.95rem; }
        .btn-pause { background: #eab308; color: #000; }
        .btn-resume { background: #10b981; color: #fff; }
        .btn-flatten { background: #ef4444; color: #fff; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { text-align: left; padding: 10px; border-bottom: 1px solid #334155; font-size: 0.9rem; }
        th { color: #94a3b8; }
    </style>
</head>
<body>
    <h1>Wallex Opportunity Agent - Status Dashboard</h1>
    <div class="card">
        <h2>System Controls & Status</h2>
        <p>Execution Mode: <strong>{{MODE}}</strong> | State: <span class="badge badge-{{STATE_CLASS}}">{{STATE}}</span> | Uptime: <strong>{{UPTIME}}s</strong></p>
        <div class="btn-group">
            <button class="btn-pause" onclick="controlAction('pause')">Pause Entries</button>
            <button class="btn-resume" onclick="controlAction('resume')">Resume Entries</button>
            <button class="btn-flatten" onclick="controlAction('flatten')">Emergency Flatten</button>
        </div>
    </div>
    <div class="card">
        <h2>Financial Metrics</h2>
        <div class="grid">
            <div class="metric-box"><div class="metric-label">Initial Cash</div><div class="metric-val">{{INITIAL_CASH}} TMN</div></div>
            <div class="metric-box"><div class="metric-label">Available Cash</div><div class="metric-val">{{AVAILABLE_CASH}} TMN</div></div>
            <div class="metric-box"><div class="metric-label">Total Equity</div><div class="metric-val">{{TOTAL_EQUITY}} TMN</div></div>
            <div class="metric-box"><div class="metric-label">Cumulative Fees</div><div class="metric-val">{{FEES}} TMN</div></div>
        </div>
    </div>
    <div class="card">
        <h2>Active Positions ({{POSITIONS_COUNT}})</h2>
        <div id="positions-container">{{POSITIONS_TABLE}}</div>
    </div>
    <script>
        async function controlAction(action) {
            const token = prompt("Enter Auth Token:", localStorage.getItem("wallex_token") || "");
            if (!token) return;
            localStorage.setItem("wallex_token", token);
            try {
                const res = await fetch(`/api/control/${action}`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const data = await res.json();
                alert(JSON.stringify(data));
                window.location.reload();
            } catch(e) {
                alert("Error: " + e.message);
            }
        }
    </script>
</body>
</html>
"""


def create_dashboard_app(harness: SystemTradingHarness, auth_token: str = "secret-token") -> FastAPI:
    """Creates a FastAPI dashboard application bound to a SystemTradingHarness instance."""
    app = FastAPI(title="Wallex Opportunity Agent Dashboard")

    def verify_auth(
        authorization: str | None = Header(default=None),
        x_api_key: str | None = Header(default=None),
        token: str | None = Query(default=None),
    ) -> bool:
        provided = None
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                provided = parts[1]
            else:
                provided = authorization
        elif x_api_key:
            provided = x_api_key
        elif token:
            provided = token

        if provided != auth_token:
            raise HTTPException(status_code=401, detail="Unauthorized")
        return True

    @app.get("/", response_class=HTMLResponse)
    def index():
        state = harness.state
        state_class = "running" if state == "RUNNING" else ("paused" if state == "PAUSED" else "safestop")
        uptime = round(time.time() - harness.started_at, 1)

        positions = list(harness.portfolio["open_positions"].values())
        if positions:
            rows = "".join(
                f"<tr><td>{p['symbol']}</td><td>{p['quantity']}</td><td>{p['entry_price']}</td><td>{p['stop_price']}</td></tr>"
                for p in positions
            )
            table_html = f"<table><thead><tr><th>Symbol</th><th>Qty</th><th>Entry Price</th><th>Stop Price</th></tr></thead><tbody>{rows}</tbody></table>"
        else:
            table_html = "<p style='color: #94a3b8;'>No open positions.</p>"

        html = (
            HTML_DASHBOARD_TEMPLATE.replace("{{MODE}}", harness.mode.upper())
            .replace("{{STATE}}", state)
            .replace("{{STATE_CLASS}}", state_class)
            .replace("{{UPTIME}}", str(uptime))
            .replace("{{INITIAL_CASH}}", f"{harness.initial_cash_tmn:,.0f}")
            .replace("{{AVAILABLE_CASH}}", f"{harness.portfolio['available_cash_tmn']:,.0f}")
            .replace("{{TOTAL_EQUITY}}", f"{harness.portfolio['total_equity_tmn']:,.0f}")
            .replace("{{FEES}}", f"{harness.cumulative_fees_tmn:,.0f}")
            .replace("{{POSITIONS_COUNT}}", str(len(positions)))
            .replace("{{POSITIONS_TABLE}}", table_html)
        )
        return HTMLResponse(content=html)

    @app.get("/api/status")
    def get_status(_auth: bool = Depends(verify_auth)):
        uptime = round(time.time() - harness.started_at, 2)
        realized_net_pnl = harness.portfolio["total_equity_tmn"] - harness.initial_cash_tmn

        return {
            "mode": harness.mode,
            "state": harness.state,
            "uptime_seconds": uptime,
            "financials": {
                "starting_balance_tmn": harness.initial_cash_tmn,
                "cash_tmn": harness.portfolio["available_cash_tmn"],
                "equity_tmn": harness.portfolio["total_equity_tmn"],
                "realized_net_pnl_tmn": realized_net_pnl,
                "fees_tmn": harness.cumulative_fees_tmn,
                "max_drawdown_pct": 0.0,
            },
            "portfolio": {
                "open_positions": list(harness.portfolio["open_positions"].values()),
                "open_orders": list(harness.portfolio["open_orders"].values()),
            },
            "recent_telemetry": {
                "candidates": harness.recent_candidates,
                "decisions": harness.recent_decisions,
                "risk_rejections": harness.recent_rejections,
            },
        }

    @app.post("/api/control/pause")
    def pause_entries(_auth: bool = Depends(verify_auth)):
        harness.pause()
        return {"status": "success", "state": harness.state}

    @app.post("/api/control/resume")
    def resume_entries(_auth: bool = Depends(verify_auth)):
        harness.resume()
        return {"status": "success", "state": harness.state}

    @app.post("/api/control/flatten")
    def flatten_positions(_auth: bool = Depends(verify_auth)):
        orders = harness.flatten()
        return {
            "status": "success",
            "state": harness.state,
            "flattened_count": len(orders),
        }

    return app
