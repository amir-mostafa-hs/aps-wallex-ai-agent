"""FastAPI Status Dashboard and Interactive Control Interface."""
from __future__ import annotations
import time
from typing import Any, Mapping
from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, Body
from fastapi.responses import HTMLResponse, JSONResponse

from wallex_agent.harness import SystemTradingHarness, run_simulation_backtest
from wallex_agent.backtest_engine import HistoricalBacktestEngine, fetch_or_generate_historical_candles
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
        @font-face {
            font-family: 'Vazirmatn';
            src: url('/static/fonts/Vazirmatn-Regular.woff2') format('woff2');
            font-weight: 400;
            font-style: normal;
            font-display: swap;
        }
        @font-face {
            font-family: 'Vazirmatn';
            src: url('/static/fonts/Vazirmatn-Bold.woff2') format('woff2');
            font-weight: 700;
            font-style: normal;
            font-display: swap;
        }
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
            font-family: 'Vazirmatn', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
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
        .chart-box {
            background: #0f172a; border: 1px solid var(--card-border); border-radius: 8px;
            padding: 16px; margin-top: 15px; position: relative;
        }
        .modal-overlay {
            display: none; position: fixed; inset: 0; background: rgba(0, 0, 0, 0.75);
            z-index: 1000; align-items: center; justify-content: center; backdrop-filter: blur(4px);
        }
        .modal-overlay.active { display: flex; }
        .modal-card {
            background: var(--card-bg); border: 1px solid var(--card-border); border-radius: 12px;
            width: 90%; max-width: 650px; padding: 24px; box-shadow: 0 10px 25px rgba(0, 0, 0, 0.5);
            position: relative; max-height: 85vh; overflow-y: auto; text-align: right;
        }
        .modal-close {
            position: absolute; top: 16px; left: 16px; background: transparent; border: none;
            color: #94a3b8; font-size: 1.4rem; cursor: pointer;
        }
        .modal-close:hover { color: #fff; }

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
            <h2>آزمایشگاه بک‌تست تاریخی و شبیه‌سازی پارامتریک</h2>
            <p style="color: var(--text-muted); font-size: 0.9rem;">شبیه‌سازی کامل چرخه تصمیم‌گیری هوش مصنوعی، تنظیم استراتژی، بررسی برتری آماری (Net Edge) و سنجش هزینه اصطکاک و کارمزد</p>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-top: 15px; background: rgba(15,23,42,0.6); padding: 16px; border-radius: 8px; border: 1px solid var(--card-border);">
                <div>
                    <label style="display: block; margin-bottom: 6px; font-size: 0.85rem; color: #94a3b8;">استراتژی معاملاتی:</label>
                    <select id="btStrategy" style="background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 8px 12px; border-radius: 6px; width: 100%;">
                        <option value="trend_filtered_pullback" selected>استراتژی اصلی مسابقه: پولبک با فیلتر روند (Trend Filtered Pullback)</option>
                        <option value="momentum">ممانتوم پرسرعت (Momentum)</option>
                        <option value="trend_following">تعقیب روند صعودی (Trend Following)</option>
                        <option value="mean_reversion">بازگشت به میانگین (Mean Reversion)</option>
                    </select>
                </div>
                <div>
                    <label style="display: block; margin-bottom: 6px; font-size: 0.85rem; color: #94a3b8;">حد ضرر اسمی (% SL):</label>
                    <input type="number" id="btStopPct" value="1.0" min="0.5" max="5.0" step="0.1" style="background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 8px 12px; border-radius: 6px; width: 100%;">
                </div>
                <div>
                    <label style="display: block; margin-bottom: 6px; font-size: 0.85rem; color: #94a3b8;">حد سود هدفی (% TP):</label>
                    <input type="number" id="btTakeProfitPct" value="2.0" min="1.0" max="10.0" step="0.1" style="background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 8px 12px; border-radius: 6px; width: 100%;">
                </div>
                <div>
                    <label style="display: block; margin-bottom: 6px; font-size: 0.85rem; color: #94a3b8;">سقف زمان نگهداری (دقیقه):</label>
                    <input type="number" id="btMaxHolding" value="5" min="1" max="60" step="1" style="background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 8px 12px; border-radius: 6px; width: 100%;">
                </div>
                <div>
                    <label style="display: block; margin-bottom: 6px; font-size: 0.85rem; color: #94a3b8;">تعداد چرخه‌های شبیه‌سازی:</label>
                    <input type="number" id="btCycles" value="50" min="10" max="500" step="10" style="background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 8px 12px; border-radius: 6px; width: 100%;">
                </div>
            </div>
            <div style="margin-top: 15px;">
                <button id="btnRunBt" class="action-btn btn-primary" onclick="runBacktest()">شروع بک‌تست پارامتریک</button>
            </div>
        </div>

        <div id="btResultsCard" class="card" style="display: none;">
            <h2>نتیجه عملکرد بک‌تست پارامتریک</h2>
            <div class="grid">
                <div class="metric-box"><div class="metric-label">سود / زیان خالص محقق‌شده</div><div id="btNetPnl" class="metric-val">0 TMN</div></div>
                <div class="metric-box"><div class="metric-label">سود ناخالص (Gross P&L)</div><div id="btGrossPnl" class="metric-val">0 TMN</div></div>
                <div class="metric-box"><div class="metric-label">مجموع کارمزد صرافی (Friction)</div><div id="btTotalFees" class="metric-val">0 TMN</div></div>
                <div class="metric-box"><div class="metric-label">بازدهی سرمایه (ROI)</div><div id="btRoi" class="metric-val">0%</div></div>
                <div class="metric-box"><div class="metric-label">نرخ برد (Win Rate)</div><div id="btWinRate" class="metric-val">0%</div></div>
                <div class="metric-box"><div class="metric-label">کل معاملات بسته‌شده</div><div id="btTradesCount" class="metric-val">0</div></div>
                <div class="metric-box"><div class="metric-label">حداکثر افت سرمایه (Max DD)</div><div id="btMaxDd" class="metric-val">0%</div></div>
            </div>

            <div class="chart-box">
                <h3 style="margin:0 0 10px 0; color:var(--primary);">منحنی رشد دارایی در شبیه‌سازی (Simulation Equity Curve)</h3>
                <div id="btEquityChart"></div>
            </div>

            <h3 style="margin-top: 20px; color: var(--primary);">ریز معاملات انجام‌شده در شبیه‌سازی</h3>
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
            
            <div class="chart-box">
                <h3 style="margin:0 0 10px 0; color:var(--primary);">منحنی رشد دارایی معاملات گذشته (Historical Equity Curve)</h3>
                <div id="auditEquityChart"></div>
            </div>

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

    <!-- Post-Mortem Modal -->
    <div id="postMortemModal" class="modal-overlay" onclick="closePostMortemModal(event)">
        <div class="modal-card" onclick="event.stopPropagation()">
            <button class="modal-close" onclick="closePostMortemModal()">&times;</button>
            <h2 id="pmTitle" style="color:var(--primary); margin-top:0;">کارت تفصیلی تحلیل پس از معامله (Post-Mortem)</h2>
            <div id="pmContent"></div>
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
            document.querySelectorAll('.tab-btn').forEach(b => {
                b.classList.remove('active');
                if (b.getAttribute('onclick') && b.getAttribute('onclick').includes(tabId)) {
                    b.classList.add('active');
                }
            });
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const targetContent = document.getElementById('tab-' + tabId);
            if (targetContent) targetContent.classList.add('active');
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
            const strategy = document.getElementById('btStrategy').value || 'momentum';
            const stopPct = document.getElementById('btStopPct').value || 1.0;
            const tpPct = document.getElementById('btTakeProfitPct').value || 2.0;
            const maxHolding = document.getElementById('btMaxHolding').value || 5;
            const token = getToken();
            btn.innerHTML = 'در حال شبیه‌سازی... <span class="spinner"></span>';
            btn.disabled = true;

            try {
                const res = await fetch('/api/backtest/run', {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        cycles: parseInt(cycles),
                        strategy_id: strategy,
                        stop_distance_pct: parseFloat(stopPct),
                        take_profit_distance_pct: parseFloat(tpPct),
                        max_holding_minutes: parseInt(maxHolding)
                    })
                });
                if (!res.ok) throw new Error("شکست در اجرای بک‌تست");
                const data = await res.json();
                document.getElementById('btResultsCard').style.display = 'block';
                document.getElementById('btNetPnl').innerText = Number(data.net_pnl_tmn).toLocaleString() + ' TMN';
                document.getElementById('btNetPnl').style.color = data.net_pnl_tmn >= 0 ? '#34d399' : '#f87171';
                document.getElementById('btGrossPnl').innerText = Number(data.gross_pnl_tmn).toLocaleString() + ' TMN';
                document.getElementById('btGrossPnl').style.color = data.gross_pnl_tmn >= 0 ? '#34d399' : '#f87171';
                document.getElementById('btTotalFees').innerText = Number(data.total_fees_tmn).toLocaleString() + ' TMN';
                document.getElementById('btRoi').innerText = (data.roi_pct >= 0 ? '+' : '') + data.roi_pct.toFixed(2) + '%';
                document.getElementById('btRoi').style.color = data.roi_pct >= 0 ? '#34d399' : '#f87171';
                document.getElementById('btWinRate').innerText = data.summary.win_rate_pct.toFixed(1) + '%';
                document.getElementById('btTradesCount').innerText = data.summary.total_trades;
                document.getElementById('btMaxDd').innerText = data.summary.max_drawdown_pct.toFixed(2) + '%';

                if (data.equity_curve && data.equity_curve.length > 0) {
                    renderEquityChart('btEquityChart', data.equity_curve, data.initial_capital_tmn);
                }

                const trades = data.trades || [];
                if (trades.length > 0) {
                    let rows = trades.map(t => `<tr><td>${t.symbol}</td><td><span class="badge badge-running">${t.strategy_id || 'momentum'}</span></td><td>${t.quantity}</td><td>${Number(t.entry_price).toLocaleString()}</td><td>${Number(t.exit_price).toLocaleString()}</td><td style="color:${t.gross_realized_pnl_tmn>=0?'#34d399':'#f87171'}">${Number(t.gross_realized_pnl_tmn).toLocaleString()}</td><td>${Number(t.total_fee_tmn).toLocaleString()}</td><td style="font-weight:bold;color:${t.net_realized_pnl_tmn>=0?'#34d399':'#f87171'}">${Number(t.net_realized_pnl_tmn).toLocaleString()}</td><td>${t.exit_reason}</td></tr>`).join('');
                    document.getElementById('btTradesTableContainer').innerHTML = `<table><thead><tr><th>نماد</th><th>استراتژی</th><th>حجم</th><th>قیمت ورود</th><th>قیمت خروج</th><th>سود ناخالص</th><th>کارمزد</th><th>سود خالص</th><th>دلیل خروج</th></tr></thead><tbody>${rows}</tbody></table>`;
                } else {
                    document.getElementById('btTradesTableContainer').innerHTML = '<p style="color: var(--text-muted);">معامله بسته‌شده‌ای در این بازه ثبت نشد.</p>';
                }
            } catch(e) {
                alert("خطا در بک‌تست: " + e.message);
            } finally {
                btn.innerHTML = 'شروع بک‌تست پارامتریک';
                btn.disabled = false;
            }
        }

        let currentAuditTrades = [];

        async function loadAuditReport() {
            const token = getToken();
            try {
                const res = await fetch('/api/reports/audit', {
                    headers: { 'Authorization': `Bearer ${token}` }
                });
                if (!res.ok) return;
                const data = await res.json();
                const s = data.summary;
                const feeLossPct = s.fee_loss_ratio_pct ? s.fee_loss_ratio_pct.toFixed(1) : '0.0';
                const totalLoss = s.total_loss_tmn ? Number(s.total_loss_tmn).toLocaleString() : '0';

                document.getElementById('auditSummaryContainer').innerHTML = `
                    <div class="metric-box"><div class="metric-label">کل معاملات گذشته</div><div class="metric-val">${s.total_trades}</div></div>
                    <div class="metric-box"><div class="metric-label">معاملات برنده / بازنده</div><div class="metric-val">${s.winning_trades} / ${s.losing_trades}</div></div>
                    <div class="metric-box"><div class="metric-label">سود خالص محقق‌شده</div><div class="metric-val" style="color:${s.net_realized_pnl_tmn>=0?'#34d399':'#f87171'}">${Number(s.net_realized_pnl_tmn).toLocaleString()} TMN</div></div>
                    <div class="metric-box"><div class="metric-label">مجموع کارمزدهای پرداختی</div><div class="metric-val">${Number(s.total_fees_tmn).toLocaleString()} TMN</div></div>
                    <div class="metric-box">
                        <div class="metric-label">سهم کارمزد از کل زیان‌ها (Fee Impact)</div>
                        <div class="metric-val" style="color:${s.fee_loss_ratio_pct > 25 ? '#f87171' : '#fbbf24'}">${feeLossPct}%</div>
                        <div style="font-size:0.75rem; color:#94a3b8; margin-top:4px;">کل زیان ناخالص: ${totalLoss} TMN</div>
                    </div>
                `;

                if (data.equity_curve && data.equity_curve.length > 0) {
                    renderEquityChart('auditEquityChart', data.equity_curve, 5000000.0);
                } else {
                    document.getElementById('auditEquityChart').innerHTML = '<p style="color:var(--text-muted); text-align:center; padding:20px;">نقطه ثبت‌شده‌ای در این بازه برای رسم منحنی دارایی وجود ندارد.</p>';
                }

                currentAuditTrades = data.trades || [];
                if (currentAuditTrades.length > 0) {
                    let rows = currentAuditTrades.map((t, idx) => {
                        let lossBadge = t.loss_cause === 'confirmed' ? '<span class="status-pill pill-fail">تأییدشده (تیک مارکت)</span>' : (t.loss_cause === 'likely' ? '<span class="status-pill pill-warn">محتمل (اسلیپیج)</span>' : (t.loss_cause === 'unknown' ? '<span class="status-pill pill-warn">دریفت عادی</span>' : '<span class="status-pill pill-pass">برنده</span>'));
                        return `<tr><td>${t.symbol}</td><td style="color:${t.net_realized_pnl_tmn>=0?'#34d399':'#f87171'}">${Number(t.net_realized_pnl_tmn).toLocaleString()} TMN</td><td>${Number(t.total_fee_tmn).toLocaleString()} TMN</td><td>${t.exit_reason}</td><td>${lossBadge}</td><td><button class="action-btn" style="padding:4px 10px; font-size:0.8rem; background:#334155; color:#fff;" onclick="openPostMortem(${idx})">مشاهده Post-Mortem</button></td></tr>`;
                    }).join('');
                    document.getElementById('auditTradesContainer').innerHTML = `<table><thead><tr><th>نماد</th><th>سود/زیان خالص</th><th>کارمزد</th><th>دلیل خروج</th><th>ریشه‌یابی علت زیان</th><th>اقدام / تحلیل تفصیلی</th></tr></thead><tbody>${rows}</tbody></table>`;
                } else {
                    document.getElementById('auditTradesContainer').innerHTML = '<p style="color: var(--text-muted); padding: 10px 0;">تراکنشی در پایگاه داده ثبت نشده است.</p>';
                }
            } catch(e) {}
        }

        function renderEquityChart(containerId, points, initialCapital) {
            const el = document.getElementById(containerId);
            if (!el) return;
            if (!points || points.length === 0) {
                el.innerHTML = '<p style="color:var(--text-muted); padding:20px 0; text-align:center;">داده‌ای برای رسم نمودار در دسترس نیست.</p>';
                return;
            }

            const w = 760;
            const h = 200;
            const padX = 50;
            const padY = 30;

            const initialCap = (Number.isFinite(Number(initialCapital)) && Number(initialCapital) > 0) ? Number(initialCapital) : 5000000;

            // Safe extraction: supports total_equity, equity_tmn, or fallback to initialCap
            let equities = points.map(p => {
                const raw = (p && (p.total_equity ?? p.equity_tmn ?? p.equity)) ?? initialCap;
                const num = Number(raw);
                return Number.isFinite(num) ? num : initialCap;
            });

            if (equities.length === 0) {
                equities = [initialCap];
            }

            let minEq = Math.min(...equities, initialCap);
            let maxEq = Math.max(...equities, initialCap);

            if (!Number.isFinite(minEq) || !Number.isFinite(maxEq)) {
                minEq = initialCap * 0.95;
                maxEq = initialCap * 1.05;
            }

            let diff = maxEq - minEq;
            if (diff <= 0 || !Number.isFinite(diff)) {
                diff = Math.max(initialCap * 0.02, 1000.0);
                minEq = Math.max(0, initialCap - diff);
                maxEq = initialCap + diff;
            } else {
                minEq = Math.max(0, minEq - diff * 0.05);
                maxEq = maxEq + diff * 0.05;
            }
            const range = (maxEq - minEq) || 1.0;

            const getX = (i) => padX + (i / Math.max(1, equities.length - 1)) * (w - 2 * padX);
            const getY = (val) => {
                const v = Number.isFinite(Number(val)) ? Number(val) : initialCap;
                const clamped = Math.max(minEq, Math.min(maxEq, v));
                return (h - padY) - ((clamped - minEq) / range) * (h - 2 * padY);
            };

            const pathD = equities.map((eq, i) => `${i === 0 ? 'M' : 'L'} ${getX(i).toFixed(1)} ${getY(eq).toFixed(1)}`).join(' ');
            const baseLineY = getY(initialCap);
            const lastEq = equities[equities.length - 1];
            const isProfitable = lastEq >= initialCap;
            const strokeColor = isProfitable ? '#10b981' : '#ef4444';
            const fillGradientId = 'grad-' + containerId;

            let svg = `<svg viewBox="0 0 ${w} ${h}" style="width:100%; height:auto; overflow:visible;">
                <defs>
                    <linearGradient id="${fillGradientId}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="${strokeColor}" stop-opacity="0.3"/>
                        <stop offset="100%" stop-color="${strokeColor}" stop-opacity="0.0"/>
                    </linearGradient>
                </defs>
                <line x1="${padX}" y1="${getY(maxEq).toFixed(1)}" x2="${w - padX}" y2="${getY(maxEq).toFixed(1)}" stroke="#334155" stroke-dasharray="3,3"/>
                <line x1="${padX}" y1="${getY(minEq).toFixed(1)}" x2="${w - padX}" y2="${getY(minEq).toFixed(1)}" stroke="#334155" stroke-dasharray="3,3"/>
                <line x1="${padX}" y1="${baseLineY.toFixed(1)}" x2="${w - padX}" y2="${baseLineY.toFixed(1)}" stroke="#64748b" stroke-dasharray="4,4"/>
                <text x="${w - padX}" y="${(baseLineY - 6).toFixed(1)}" fill="#94a3b8" font-size="11" text-anchor="end">سرمایه مبنا: ${Number(initialCap).toLocaleString()} TMN</text>
                <text x="${padX}" y="${padY - 8}" fill="#94a3b8" font-size="10">${Number(maxEq.toFixed(0)).toLocaleString()}</text>
                <text x="${padX}" y="${h - padY + 16}" fill="#94a3b8" font-size="10">${Number(minEq.toFixed(0)).toLocaleString()}</text>
                <path d="${pathD} L ${getX(equities.length - 1).toFixed(1)} ${h - padY} L ${padX} ${h - padY} Z" fill="url(#${fillGradientId})"/>
                <path d="${pathD}" fill="none" stroke="${strokeColor}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
                <circle cx="${getX(0).toFixed(1)}" cy="${getY(equities[0]).toFixed(1)}" r="4" fill="#38bdf8"/>
                <circle cx="${getX(equities.length - 1).toFixed(1)}" cy="${getY(lastEq).toFixed(1)}" r="5" fill="${strokeColor}"/>
            </svg>`;

            el.innerHTML = svg;
        }

        function openPostMortem(idx) {
            const t = currentAuditTrades[idx];
            if (!t) return;
            const isLoss = t.net_realized_pnl_tmn < 0;
            const statusText = isLoss ? 'زیان‌ده (Loss)' : 'سودآور (Profit)';
            const statusColor = isLoss ? '#f87171' : '#34d399';
            let notes = t.post_mortem_notes || 'اطلاعات بیشتری در تله‌متری ثبت نشده است.';

            document.getElementById('pmTitle').innerText = `تحلیل پس از معامله (Post-Mortem): ${t.symbol} (${t.trade_id})`;
            document.getElementById('pmContent').innerHTML = `
                <div style="background:#0f172a; padding:16px; border-radius:8px; border:1px solid var(--card-border); margin-bottom:14px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span>نماد معاملاتی: <strong>${t.symbol}</strong></span>
                        <span>استراتژی: <strong style="color:var(--primary);">${t.strategy_id || 'momentum'}</strong></span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span>وضعیت نهایی معامله: <strong style="color:${statusColor};">${statusText}</strong></span>
                        <span>علت زیان صرافی: <strong>${t.loss_cause || 'سودآور / نرمال'}</strong></span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span>قیمت ورود: ${Number(t.entry_price).toLocaleString()} TMN</span>
                        <span>قیمت خروج: ${Number(t.exit_price).toLocaleString()} TMN</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; margin-bottom:8px;">
                        <span>سود ناخالص (Gross PnL): ${Number(t.gross_realized_pnl_tmn).toLocaleString()} TMN</span>
                        <span>کل کارمزد پرداخت‌شده: <strong style="color:#fbbf24;">${Number(t.total_fee_tmn).toLocaleString()} TMN</strong></span>
                    </div>
                    <div style="display:flex; justify-content:space-between; border-top:1px solid var(--card-border); padding-top:8px;">
                        <span>سود/زیان خالص محقق‌شده:</span>
                        <span style="font-weight:bold; font-size:1.15rem; color:${statusColor};">${Number(t.net_realized_pnl_tmn).toLocaleString()} TMN</span>
                    </div>
                </div>
                <div style="background:#0f172a; padding:16px; border-radius:8px; border:1px solid var(--card-border);">
                    <h4 style="margin:0 0 8px 0; color:var(--primary);">علت توقف، شواهد و منطق ارزیابی هوش مصنوعی (AI Rationale & Evidence):</h4>
                    <p style="margin:0; font-size:0.9rem; line-height:1.6; color:#cbd5e1; direction:ltr; text-align:left; background:#1e293b; padding:10px; border-radius:6px; font-family:monospace; word-break:break-all;">${notes}</p>
                </div>
            `;
            document.getElementById('postMortemModal').classList.add('active');
        }

        function closePostMortemModal(e) {
            if (!e || e.target.id === 'postMortemModal' || e.target.classList.contains('modal-close')) {
                document.getElementById('postMortemModal').classList.remove('active');
            }
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


def create_dashboard_app(harness: SystemTradingHarness, auth_token: str = "super-secret-token") -> FastAPI:
    """Creates a FastAPI dashboard application bound to a SystemTradingHarness instance."""
    app = FastAPI(title="Wallex Opportunity Agent Dashboard")

    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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
    def run_backtest_endpoint(payload: dict[str, Any] = Body(default={}), _auth: bool = Depends(verify_auth)):
        """Executes a backtest simulation and returns performance statistics."""
        strategy_id = str(payload.get("strategy_id", "trend_filtered_pullback")).strip()
        from wallex_agent.domain.validation import VALID_STRATEGIES
        if strategy_id not in VALID_STRATEGIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid strategy '{strategy_id}'. Must be one of: {sorted(list(VALID_STRATEGIES))}",
            )

        cycles = max(10, min(500, int(payload.get("cycles", 50))))
        stop_distance_pct = max(0.1, min(10.0, float(payload.get("stop_distance_pct", 1.0))))
        take_profit_distance_pct = max(0.1, min(20.0, float(payload.get("take_profit_distance_pct", 2.0))))
        max_holding_minutes = max(1, min(1440, int(payload.get("max_holding_minutes", 10))))
        symbol = str(payload.get("symbol", "BTCTMN")).strip().upper()

        candles = fetch_or_generate_historical_candles(symbol=symbol, count=max(cycles * 3, 120))
        engine = HistoricalBacktestEngine(initial_capital_tmn=harness.initial_cash_tmn)
        res = engine.run(
            symbol=symbol,
            candles_1m=candles,
            strategy_id=strategy_id,
            stop_distance_pct=stop_distance_pct,
            take_profit_distance_pct=take_profit_distance_pct,
            max_holding_minutes=max_holding_minutes,
        )
        return {
            "run_id": res["run_id"],
            "initial_capital_tmn": res["initial_capital_tmn"],
            "final_equity_tmn": res["final_equity_tmn"],
            "gross_pnl_tmn": res["gross_pnl_tmn"],
            "total_fees_tmn": res["total_fees_tmn"],
            "net_pnl_tmn": res["net_pnl_tmn"],
            "roi_pct": res["roi_pct"],
            "strategy_id": res["strategy_id"],
            "stop_distance_pct": res["stop_distance_pct"],
            "take_profit_distance_pct": res["take_profit_distance_pct"],
            "max_holding_minutes": res["max_holding_minutes"],
            "summary": res["summary"],
            "trades": res["trades"],
            "equity_curve": res["equity_curve"],
        }


    @app.get("/api/reports/audit")
    def get_audit_report(_auth: bool = Depends(verify_auth)):
        """Returns trade history and loss cause audit from telemetry store."""
        summary = harness.telemetry.get_performance_summary()
        trades = harness.telemetry.get_recent_trades(limit=50)
        equity_curve = harness.telemetry.get_equity_curve(limit=500)
        return {
            "summary": summary,
            "trades": trades,
            "equity_curve": equity_curve,
        }


    @app.get("/api/preflight/run")
    def run_preflight_endpoint(_auth: bool = Depends(verify_auth)):
        """Runs preflight verification checks and returns detailed checklist."""
        cfg = load_config()
        gate = PreflightGate(cfg)
        report = gate.run_all_checks()
        return report

    @app.get("/api/config/settings")
    def get_config_settings(_auth: bool = Depends(verify_auth)):
        """Returns unified strategy and risk configuration settings."""
        cfg = load_config()
        from wallex_agent.config import DEFAULT_STRATEGY_SETTINGS
        settings = dict(DEFAULT_STRATEGY_SETTINGS)
        settings.update({
            "mode": cfg["mode"],
            "risk_per_trade_equity_pct": cfg["risk_per_trade_equity_pct"],
            "max_position_notional_equity_pct": cfg["max_position_notional_equity_pct"],
            "max_total_exposure_equity_pct": cfg["max_total_exposure_equity_pct"],
            "min_cash_reserve_equity_pct": cfg["min_cash_reserve_equity_pct"],
            "max_open_positions": cfg["max_open_positions"],
            "default_min_notional_tmn": cfg["default_min_notional_tmn"],
            "liquidation_floor_tmn": cfg["liquidation_floor_tmn"],
        })
        return settings

    return app


def render_equity_svg(points: Sequence[Mapping[str, Any]], initial_capital: float = 5000000.0) -> str:
    """Renders a standalone SVG equity curve string guaranteeing no NaN coordinates."""
    import math
    w, h = 760, 200
    pad_x, pad_y = 50, 30

    init_cap = float(initial_capital) if (initial_capital and initial_capital > 0) else 5000000.0
    equities: list[float] = []
    for p in points:
        val = p.get("total_equity")
        if val is None:
            val = p.get("equity_tmn")
        if val is None:
            val = p.get("equity")
        try:
            f = float(val)
            if math.isfinite(f) and f > 0:
                equities.append(f)
            else:
                equities.append(init_cap)
        except (ValueError, TypeError):
            equities.append(init_cap)

    if not equities:
        equities = [init_cap]

    min_eq = min(min(equities), init_cap)
    max_eq = max(max(equities), init_cap)

    diff = max_eq - min_eq
    if diff <= 0:
        diff = max(init_cap * 0.02, 1000.0)
        min_eq = max(0.0, init_cap - diff)
        max_eq = init_cap + diff
    else:
        min_eq = max(0.0, min_eq - diff * 0.05)
        max_eq = max_eq + diff * 0.05

    range_eq = (max_eq - min_eq) or 1.0

    def get_x(i: int) -> float:
        denom = max(1, len(equities) - 1)
        return pad_x + (i / denom) * (w - 2 * pad_x)

    def get_y(val: float) -> float:
        clamped = max(min_eq, min(max_eq, val))
        return (h - pad_y) - ((clamped - min_eq) / range_eq) * (h - 2 * pad_y)

    path_d_parts = []
    for i, eq in enumerate(equities):
        cmd = "M" if i == 0 else "L"
        path_d_parts.append(f"{cmd} {get_x(i):.1f} {get_y(eq):.1f}")
    path_d = " ".join(path_d_parts)

    baseline_y = get_y(init_cap)
    last_eq = equities[-1]
    is_profitable = last_eq >= init_cap
    stroke_color = "#10b981" if is_profitable else "#ef4444"

    svg = f"""<svg viewBox="0 0 {w} {h}" style="width:100%; height:auto; overflow:visible;">
    <defs>
        <linearGradient id="grad-equity" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stop-color="{stroke_color}" stop-opacity="0.3"/>
            <stop offset="100%" stop-color="{stroke_color}" stop-opacity="0.0"/>
        </linearGradient>
    </defs>
    <line x1="{pad_x}" y1="{get_y(max_eq):.1f}" x2="{w - pad_x}" y2="{get_y(max_eq):.1f}" stroke="#334155" stroke-dasharray="3,3"/>
    <line x1="{pad_x}" y1="{get_y(min_eq):.1f}" x2="{w - pad_x}" y2="{get_y(min_eq):.1f}" stroke="#334155" stroke-dasharray="3,3"/>
    <line x1="{pad_x}" y1="{baseline_y:.1f}" x2="{w - pad_x}" y2="{baseline_y:.1f}" stroke="#64748b" stroke-dasharray="4,4"/>
    <text x="{w - pad_x}" y="{baseline_y - 6:.1f}" fill="#94a3b8" font-size="11" text-anchor="end">سرمایه مبنا: {init_cap:,.0f} TMN</text>
    <text x="{pad_x}" y="{pad_y - 8}" fill="#94a3b8" font-size="10">{max_eq:,.0f}</text>
    <text x="{pad_x}" y="{h - pad_y + 16}" fill="#94a3b8" font-size="10">{min_eq:,.0f}</text>
    <path d="{path_d} L {get_x(len(equities) - 1):.1f} {h - pad_y} L {pad_x} {h - pad_y} Z" fill="url(#grad-equity)"/>
    <path d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    <circle cx="{get_x(0):.1f}" cy="{get_y(equities[0]):.1f}" r="4" fill="#38bdf8"/>
    <circle cx="{get_x(len(equities) - 1):.1f}" cy="{get_y(last_eq):.1f}" r="5" fill="{stroke_color}"/>
</svg>"""
    return svg

