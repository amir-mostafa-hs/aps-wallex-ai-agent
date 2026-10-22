"""FastAPI Status Dashboard and Interactive Control Interface."""
from __future__ import annotations
import time
from typing import Any, Mapping
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse

from wallex_agent.harness import SystemTradingHarness, run_simulation_backtest
from wallex_agent.preflight import PreflightGate
from wallex_agent.config import load_config
from wallex_agent.universe import MarketUniverse
from wallex_agent.decision_agent import DecisionAgent
from wallex_agent.risk_engine import RiskEngine
from wallex_agent.telemetry import TelemetryStore


HTML_DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wallex Opportunity Agent - پنل مدیریت و مانیتورینگ</title>
    <style>
        :root {
            --bg: #0b1120;
            --card-bg: #1e293b;
            --card-border: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #38bdf8;
            --accent-green: #10b981;
            --accent-yellow: #f59e0b;
            --accent-red: #ef4444;
        }
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Vazirmatn", "Segoe UI", Roboto, sans-serif;
            margin: 0; padding: 20px; background: var(--bg); color: var(--text-main); line-height: 1.5;
        }
        .header {
            display: flex; justify-content: space-between; align-items: center;
            border-bottom: 1px solid var(--card-border); padding-bottom: 16px; margin-bottom: 20px;
        }
        .header h1 { margin: 0; font-size: 1.5rem; color: var(--primary); }
        .token-input-group { display: flex; align-items: center; gap: 8px; }
        .token-input-group input {
            background: #0f172a; border: 1px solid var(--card-border); color: #fff;
            padding: 8px 12px; border-radius: 6px; font-size: 0.9rem; width: 180px; direction: ltr;
        }
        .nav-tabs { display: flex; gap: 8px; margin-bottom: 20px; border-bottom: 1px solid var(--card-border); padding-bottom: 8px; }
        .tab-btn {
            background: transparent; border: 1px solid transparent; color: var(--text-muted);
            padding: 10px 20px; border-radius: 8px; font-weight: bold; cursor: pointer; font-size: 1rem;
            transition: all 0.2s;
        }
        .tab-btn:hover { background: #1e293b; color: var(--text-main); }
        .tab-btn.active { background: #0284c7; color: #fff; border-color: #38bdf8; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .card {
            background: var(--card-bg); border-radius: 10px; padding: 20px; margin-bottom: 20px;
            border: 1px solid var(--card-border); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.3);
        }
        .card h2 { margin-top: 0; font-size: 1.2rem; color: var(--primary); margin-bottom: 14px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
        .metric-box { background: #0f172a; padding: 14px; border-radius: 8px; border: 1px solid var(--card-border); }
        .metric-label { font-size: 0.85rem; color: var(--text-muted); }
        .metric-val { font-size: 1.4rem; font-weight: bold; margin-top: 6px; direction: ltr; text-align: right; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 9999px; font-weight: bold; font-size: 0.85rem; }
        .badge-running { background: #065f46; color: #34d399; }
        .badge-paused { background: #854d0e; color: #fde047; }
        .badge-safestop { background: #991b1b; color: #f87171; }
        .btn-group { display: flex; gap: 12px; margin-top: 15px; flex-wrap: wrap; }
        button.action-btn {
            cursor: pointer; padding: 10px 18px; border-radius: 6px; border: none;
            font-weight: bold; font-size: 0.95rem; transition: opacity 0.2s;
        }
        button.action-btn:hover { opacity: 0.9; }
        .btn-pause { background: var(--accent-yellow); color: #000; }
        .btn-resume { background: var(--accent-green); color: #fff; }
        .btn-flatten { background: var(--accent-red); color: #fff; }
        .btn-primary { background: #0284c7; color: #fff; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; direction: ltr; }
        th, td { text-align: left; padding: 10px; border-bottom: 1px solid var(--card-border); font-size: 0.9rem; }
        th { color: var(--text-muted); background: #0f172a; }
        .status-pill { font-size: 0.8rem; padding: 2px 8px; border-radius: 4px; }
        .pill-pass { background: #065f46; color: #34d399; }
        .pill-fail { background: #991b1b; color: #f87171; }
        .pill-warn { background: #854d0e; color: #fde047; }
        .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid #fff; border-top-color: transparent; border-radius: 50%; animation: spin 1s linear infinite; vertical-align: middle; margin-left: 6px; }
        @keyframes spin { to { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>Wallex Opportunity Agent | پنل گرافیکی معاملات و مانیتورینگ</h1>
            <p style="margin: 4px 0 0 0; color: var(--text-muted); font-size: 0.9rem;">پایش زنده موقعیت‌ها، اجرای بک‌تست، بررسی امنیت Preflight و گزارش‌های حسابرسی</p>
        </div>
        <div class="token-input-group">
            <label style="font-size: 0.85rem; color: var(--text-muted);">توکن امنیتی:</label>
            <input type="password" id="authTokenInput" placeholder="DASHBOARD_ACCESS_TOKEN" onchange="saveToken(this.value)">
        </div>
    </div>

    <div class="nav-tabs">
        <button class="tab-btn active" onclick="switchTab('monitor')">مانیتورینگ و معاملات زنده</button>
        <button class="tab-btn" onclick="switchTab('backtest')">آزمایشگاه بک‌تست (Backtest Lab)</button>
        <button class="tab-btn" onclick="switchTab('reports')">گزارش حسابرسی و زیان (Audit Report)</button>
        <button class="tab-btn" onclick="switchTab('preflight')">تست ایمنی (Preflight Gate)</button>
    </div>

    <!-- TAB 1: LIVE / SHADOW MONITOR -->
    <div id="tab-monitor" class="tab-content active">
        <div class="card">
            <h2>کنترل وضعیت عملیاتی سیستم</h2>
            <p>حالت فعلی: <strong id="lblMode">{{MODE}}</strong> | وضعیت موتور: <span id="lblState" class="badge badge-{{STATE_CLASS}}">{{STATE}}</span> | آپ‌تایم: <strong id="lblUptime">{{UPTIME}}s</strong></p>
            <div class="btn-group">
                <button class="action-btn btn-pause" onclick="controlAction('pause')">توقف ورود به معاملات (Pause)</button>
                <button class="action-btn btn-resume" onclick="controlAction('resume')">ازسرگیری معاملات (Resume)</button>
                <button class="action-btn btn-flatten" onclick="controlAction('flatten')">بستن اضطراری تمام موقعیت‌ها (Emergency Flatten)</button>
                <button class="action-btn btn-primary" onclick="refreshStatus()">بروزرسانی زنده اطلاعات</button>
            </div>
        </div>

        <div class="card">
            <h2>شاخص‌های مالی سبد اعتباری (TMN)</h2>
            <div class="grid">
                <div class="metric-box"><div class="metric-label">اعتبار اولیه (Initial Cash)</div><div id="mInitial" class="metric-val">{{INITIAL_CASH}} TMN</div></div>
                <div class="metric-box"><div class="metric-label">نقدینگی آزاد (Available Cash)</div><div id="mCash" class="metric-val">{{AVAILABLE_CASH}} TMN</div></div>
                <div class="metric-box"><div class="metric-label">ارزش کل دارایی (Total Equity)</div><div id="mEquity" class="metric-val">{{TOTAL_EQUITY}} TMN</div></div>
                <div class="metric-box"><div class="metric-label">کارمزد تجمیعی پرداخت‌شده</div><div id="mFees" class="metric-val">{{FEES}} TMN</div></div>
            </div>
        </div>

        <div class="card">
            <h2>موقعیت‌های باز لحظه‌ای (Active Positions)</h2>
            <div id="positionsContainer">{{POSITIONS_TABLE}}</div>
        </div>
    </div>

    <!-- TAB 2: BACKTEST LAB -->
    <div id="tab-backtest" class="tab-content">
        <div class="card">
            <h2>اجرای بک‌تست تاریخی و شبیه‌سازی بازار</h2>
            <p style="color: var(--text-muted); font-size: 0.9rem;">شبیه‌سازی کامل چرخه تصمیم‌گیری هوش مصنوعی، فیلتر دن‌لیست، محدودیت‌های نقدینگی و اسلیپیج بدون نیاز به اتصال به صرافی</p>
            <div style="display: flex; gap: 12px; align-items: center; margin-top: 15px;">
                <label>تعداد چرخه‌های شبیه‌سازی:</label>
                <input type="number" id="btCycles" value="50" min="10" max="500" style="background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 8px 12px; border-radius: 6px; width: 100px;">
                <button id="btnRunBt" class="action-btn btn-primary" onclick="runBacktest()">شروع بک‌تست گرافیکی</button>
            </div>
        </div>

        <div id="btResultsCard" class="card" style="display: none;">
            <h2>نتیجه عملکرد بک‌تست</h2>
            <div class="grid">
                <div class="metric-box"><div class="metric-label">سود / زیان خالص محقق‌شده</div><div id="btNetPnl" class="metric-val">0 TMN</div></div>
                <div class="metric-box"><div class="metric-label">نرخ برد (Win Rate)</div><div id="btWinRate" class="metric-val">0%</div></div>
                <div class="metric-box"><div class="metric-label">کل معاملات بسته‌شده</div><div id="btTradesCount" class="metric-val">0</div></div>
                <div class="metric-box"><div class="metric-label">حداکثر افت سرمایه (Max DD)</div><div id="btMaxDd" class="metric-val">0%</div></div>
            </div>

            <h3 style="margin-top: 20px; color: var(--primary);">ریز معاملات انجام‌شده در بک‌تست</h3>
            <div id="btTradesTableContainer"></div>
        </div>
    </div>

    <!-- TAB 3: AUDIT & LOSS CAUSE REPORTS -->
    <div id="tab-reports" class="tab-content">
        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h2>گزارش حسابرسی تله‌متری پایگاه داده SQLite</h2>
                <button class="action-btn btn-primary" onclick="loadAuditReport()">بارگذاری مجدد گزارش</button>
            </div>
            <div id="auditSummaryContainer" class="grid" style="margin-top: 15px;"></div>
            <h3 style="margin-top: 24px; color: var(--primary);">تحلیل علت زیان معاملات (Loss Cause Post-Mortem)</h3>
            <div id="auditTradesContainer" style="overflow-x: auto;"></div>
        </div>
    </div>

    <!-- TAB 4: PREFLIGHT SAFETY GATE -->
    <div id="tab-preflight" class="tab-content">
        <div class="card">
            <h2>آزمون ایمنی و مجوزهای پیش از اجرای زنده (Preflight Gate)</h2>
            <p style="color: var(--text-muted); font-size: 0.9rem;">اعتبارسنجی خودکار مجوز TRADE ساب‌اکانت اعتباری، دن‌لیست Fail-Closed، محدودیت حداقل ارزش سفارش، واچ‌داگ و انقضای پکیج</p>
            <button id="btnRunPreflight" class="action-btn btn-primary" onclick="runPreflightCheck()">اجرای تست جامع Preflight</button>
            <div id="preflightResultContainer" style="margin-top: 20px;"></div>
        </div>
    </div>

    <script>
        function getToken() {
            return localStorage.getItem("wallex_token") || "super-secret-token";
        }
        function saveToken(val) {
            localStorage.setItem("wallex_token", val.trim());
        }
        document.getElementById("authTokenInput").value = getToken();

        function switchTab(tabId) {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('tab-' + tabId).classList.add('active');
            if (tabId === 'reports') loadAuditReport();
        }

        async function controlAction(action) {
            const token = getToken();
            try {
                const res = await fetch(`/api/control/${action}`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (!res.ok) throw new Error("خطای دسترسی یا عدم احراز هویت (401)");
                const data = await res.json();
                alert("دستور با موفقیت انجام شد: " + JSON.stringify(data));
                refreshStatus();
            } catch(e) {
                alert("خطا: " + e.message);
            }
        }

        async function refreshStatus() {
            const token = getToken();
            try {
                const res = await fetch('/api/status', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (!res.ok) return;
                const data = await res.json();
                document.getElementById('lblMode').innerText = data.mode.toUpperCase();
                document.getElementById('lblState').innerText = data.state;
                document.getElementById('lblState').className = 'badge badge-' + (data.state === 'RUNNING' ? 'running' : (data.state === 'PAUSED' ? 'paused' : 'safestop'));
                document.getElementById('lblUptime').innerText = data.uptime_seconds + 's';
                document.getElementById('mInitial').innerText = Number(data.financials.starting_balance_tmn).toLocaleString() + ' TMN';
                document.getElementById('mCash').innerText = Number(data.financials.cash_tmn).toLocaleString() + ' TMN';
                document.getElementById('mEquity').innerText = Number(data.financials.equity_tmn).toLocaleString() + ' TMN';
                document.getElementById('mFees').innerText = Number(data.financials.fees_tmn).toLocaleString() + ' TMN';

                const posList = data.portfolio.open_positions || [];
                if (posList.length > 0) {
                    let rows = posList.map(p => `<tr><td>${p.symbol}</td><td>${p.quantity}</td><td>${Number(p.entry_price).toLocaleString()}</td><td>${Number(p.stop_price).toLocaleString()}</td><td>${Number(p.unrealized_pnl_tmn).toLocaleString()}</td></tr>`).join('');
                    document.getElementById('positionsContainer').innerHTML = `<table><thead><tr><th>نماد</th><th>حجم</th><th>قیمت ورود</th><th>حد ضرر واچ‌داگ</th><th>سود/زیان باز (TMN)</th></tr></thead><tbody>${rows}</tbody></table>`;
                } else {
                    document.getElementById('positionsContainer').innerHTML = '<p style="color: var(--text-muted);">هیچ موقعیت بازی وجود ندارد.</p>';
                }
            } catch(e) {}
        }

        async function runBacktest() {
            const btn = document.getElementById('btnRunBt');
            const cycles = document.getElementById('btCycles').value || 50;
            const token = getToken();
            btn.innerHTML = 'در حال شبیه‌سازی... <span class="spinner"></span>';
            btn.disabled = true;

            try {
                const res = await fetch('/api/backtest/run', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cycles: parseInt(cycles) })
                });
                if (!res.ok) throw new Error("شکست در اجرای بک‌تست");
                const data = await res.json();
                document.getElementById('btResultsCard').style.display = 'block';
                document.getElementById('btNetPnl').innerText = Number(data.net_pnl_tmn).toLocaleString() + ' TMN';
                document.getElementById('btNetPnl').style.color = data.net_pnl_tmn >= 0 ? '#34d399' : '#f87171';
                document.getElementById('btWinRate').innerText = data.summary.win_rate_pct.toFixed(1) + '%';
                document.getElementById('btTradesCount').innerText = data.summary.total_trades;
                document.getElementById('btMaxDd').innerText = data.summary.max_drawdown_pct.toFixed(2) + '%';

                const trades = data.trades || [];
                if (trades.length > 0) {
                    let rows = trades.map(t => `<tr><td>${t.symbol}</td><td>${t.quantity}</td><td>${Number(t.entry_price).toLocaleString()}</td><td>${Number(t.exit_price).toLocaleString()}</td><td style="color:${t.net_realized_pnl_tmn>=0?'#34d399':'#f87171'}">${Number(t.net_realized_pnl_tmn).toLocaleString()}</td><td>${Number(t.total_fee_tmn).toLocaleString()}</td><td>${t.exit_reason}</td></tr>`).join('');
                    document.getElementById('btTradesTableContainer').innerHTML = `<table><thead><tr><th>نماد</th><th>حجم</th><th>قیمت ورود</th><th>قیمت خروج</th><th>سود/زیان خالص</th><th>کارمزد</th><th>دلیل خروج</th></tr></thead><tbody>${rows}</tbody></table>`;
                } else {
                    document.getElementById('btTradesTableContainer').innerHTML = '<p style="color: var(--text-muted);">معامله بسته‌شده‌ای در این بازه ثبت نشد.</p>';
                }
            } catch(e) {
                alert("خطا در بک‌تست: " + e.message);
            } finally {
                btn.innerHTML = 'شروع بک‌تست گرافیکی';
                btn.disabled = false;
            }
        }

        async function loadAuditReport() {
            const token = getToken();
            try {
                const res = await fetch('/api/reports/audit', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (!res.ok) return;
                const data = await res.json();
                const s = data.summary;
                document.getElementById('auditSummaryContainer').innerHTML = `
                    <div class="metric-box"><div class="metric-label">کل معاملات گذشته</div><div class="metric-val">${s.total_trades}</div></div>
                    <div class="metric-box"><div class="metric-label">معاملات برنده / بازنده</div><div class="metric-val">${s.winning_trades} / ${s.losing_trades}</div></div>
                    <div class="metric-box"><div class="metric-label">سود خالص محقق‌شده</div><div class="metric-val" style="color:${s.net_realized_pnl_tmn>=0?'#34d399':'#f87171'}">${Number(s.net_realized_pnl_tmn).toLocaleString()} TMN</div></div>
                    <div class="metric-box"><div class="metric-label">مجموع کارمزدهای پرداختی</div><div class="metric-val">${Number(s.total_fees_tmn).toLocaleString()} TMN</div></div>
                `;

                const trades = data.trades || [];
                if (trades.length > 0) {
                    let rows = trades.map(t => {
                        let lossBadge = t.loss_cause === 'confirmed' ? '<span class="status-pill pill-fail">تأییدشده (تیک مارکت)</span>' : (t.loss_cause === 'likely' ? '<span class="status-pill pill-warn">محتمل</span>' : (t.loss_cause === 'unknown' ? '<span class="status-pill pill-warn">دریفت عادی</span>' : '<span class="status-pill pill-pass">برنده</span>'));
                        return `<tr><td>${t.symbol}</td><td style="color:${t.net_realized_pnl_tmn>=0?'#34d399':'#f87171'}">${Number(t.net_realized_pnl_tmn).toLocaleString()} TMN</td><td>${Number(t.total_fee_tmn).toLocaleString()} TMN</td><td>${t.exit_reason}</td><td>${lossBadge}</td></tr>`;
                    }).join('');
                    document.getElementById('auditTradesContainer').innerHTML = `<table><thead><tr><th>نماد</th><th>سود/زیان خالص</th><th>کارمزد</th><th>دلیل خروج</th><th>ریشه‌یابی علت زیان</th></tr></thead><tbody>${rows}</tbody></table>`;
                } else {
                    document.getElementById('auditTradesContainer').innerHTML = '<p style="color: var(--text-muted); padding: 10px 0;">تراکنشی در پایگاه داده ثبت نشده است.</p>';
                }
            } catch(e) {}
        }

        async function runPreflightCheck() {
            const btn = document.getElementById('btnRunPreflight');
            const token = getToken();
            btn.innerHTML = 'در حال اعتبارسنجی... <span class="spinner"></span>';
            btn.disabled = true;

            try {
                const res = await fetch('/api/preflight/run', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                const report = await res.json();
                let rows = report.checks.map(c => `<tr><td>${c.name}</td><td><span class="status-pill ${c.passed ? 'pill-pass' : 'pill-fail'}">${c.passed ? 'تأیید شد' : 'ناموفق'}</span></td><td>${c.details}</td></tr>`).join('');
                let summaryBox = report.all_passed ? '<div style="background:#065f46; color:#34d399; padding:12px; border-radius:6px; margin-bottom:12px; font-weight:bold;">✔ تمام گیت‌های ایمنی Preflight با موفقیت پاس شدند.</div>' : '<div style="background:#991b1b; color:#f87171; padding:12px; border-radius:6px; margin-bottom:12px; font-weight:bold;">✖ برخی شروط ایمنی برقرار نیستند؛ حالت زنده قفل است.</div>';
                document.getElementById('preflightResultContainer').innerHTML = summaryBox + `<table><thead><tr><th>مورد بررسی</th><th>وضعیت</th><th>توضیحات و جزئیات</th></tr></thead><tbody>${rows}</tbody></table>`;
            } catch(e) {
                alert("خطا در بررسی Preflight: " + e.message);
            } finally {
                btn.innerHTML = 'اجرای تست جامع Preflight';
                btn.disabled = false;
            }
        }

        // Auto-refresh every 10 seconds for live monitor
        setInterval(() => {
            if (document.getElementById('tab-monitor').classList.contains('active')) {
                refreshStatus();
            }
        }, 10000);
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
                f"<tr><td>{p['symbol']}</td><td>{p['quantity']}</td><td>{p['entry_price']:,.0f}</td><td>{p['stop_price']:,.0f}</td><td>{p['unrealized_pnl_tmn']:,.0f}</td></tr>"
                for p in positions
            )
            table_html = f"<table><thead><tr><th>Symbol</th><th>Qty</th><th>Entry Price</th><th>Stop Price</th><th>Unrealized P&L</th></tr></thead><tbody>{rows}</tbody></table>"
        else:
            table_html = "<p style='color: #94a3b8;'>هیچ موقعیت بازی وجود ندارد.</p>"

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

    @app.post("/api/backtest/run")
    def run_backtest_endpoint(payload: dict[str, Any] = Body(default={"cycles": 50}), _auth: bool = Depends(verify_auth)):
        """Executes a backtest simulation and returns performance statistics."""
        cycles = int(payload.get("cycles", 50))
        result = run_simulation_backtest(cycles=cycles)
        return {
            "initial_capital_tmn": result["initial_capital_tmn"],
            "final_equity_tmn": result["final_equity_tmn"],
            "net_pnl_tmn": result["net_pnl_tmn"],
            "summary": result["summary"],
            "trades": result["trades"],
        }

    @app.get("/api/reports/audit")
    def get_audit_report(_auth: bool = Depends(verify_auth)):
        """Returns trade history and loss cause audit from telemetry store."""
        summary = harness.telemetry.get_performance_summary()
        trades = harness.telemetry.get_recent_trades(limit=50)
        return {
            "summary": summary,
            "trades": trades,
        }

    @app.get("/api/preflight/run")
    def run_preflight_endpoint(_auth: bool = Depends(verify_auth)):
        """Runs preflight verification checks and returns detailed checklist."""
        cfg = load_config()
        gate = PreflightGate(cfg)
        report = gate.run_all_checks()
        return report

    return app
