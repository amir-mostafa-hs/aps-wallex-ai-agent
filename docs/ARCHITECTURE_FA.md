# معماری فنی پیشنهادی

## 1. تصمیم معماری برای مهلت ۴۸ ساعته

**پیشنهاد:** یک سرویس Python واحد با ماژول‌های کوچک و interfaceهای مشخص؛ نه microservice و نه swarm سنگین.

دلایل: کتابخانه‌های بالغ تحلیل داده، پیاده‌سازی سریع Backtest، تست‌پذیری، امکان اجرای asyncio و سادگی Deploy. Matt Pocock skills به روش کار Coding Agent مربوط است و محدود به زبان TypeScript نیست. اگر تیم از قبل در TypeScript بسیار سریع‌تر است، این تصمیم قابل تغییر است؛ اما در مهلت فعلی Python مسیر پیش‌فرض است.

پشته پیشنهادی:

- Python 3.12+
- `httpx` برای REST، `websockets`/کتابخانه سازگار برای stream اگر مستندات فعلی تأییدش کند
- `pydantic` برای config و schema پاسخ مدل
- `pytest` برای تست، `ruff` برای lint/format، `mypy` در صورت زمان
- `SQLite` با WAL برای event/trade/decision logs و تنظیمات کوچک
- `FastAPI` برای health/status/control endpoints و یک صفحه ساده وضعیت
- `pandas`/`numpy` فقط جایی که برای features و backtest لازم است
- Docker Compose یا systemd برای اجرای پایدار روی VPS؛ یکی را انتخاب کنید و هم‌زمان هر دو deployment را نسازید.

وابستگی بزرگ Agent framework را تا زمانی که یک قابلیت مشخص لازم ندارد، اضافه نکنید. Orchestration اصلی می‌تواند یک loop شفاف و تست‌پذیر باشد.

## 2. اجزای منطقی

```text
Wallex REST / Market Stream
          |
          v
WallexAdapter ---- Account/Order Reconciler
          |
          v
MarketUniverse (assets.md denylist + API active/spot metadata)
          |
          v
MarketDataStore -> FeatureEngine -> CandidateScanner
                                      |
                                      v
                              AI Decision Service
                                      |
                                      v
                          Portfolio/Risk Engine
                                      |
                                      v
                              Order Executor
                                      |
                                      v
                         Fill Reconciler / P&L
                                      |
                  +-------------------+------------------+
                  v                                      v
             SQLite Events                         Status Dashboard
                  |
                  v
         Backtest / Shadow / Reports
```

## 3. مرز مسئولیت‌ها

### WallexAdapter

- تنها محل تماس با endpoints رسمی والکس.
- public data و private account operations را از هم جدا نگه دارد.
- تبدیل responseهای exchange به مدل‌های داخلی typed را انجام دهد.
- timeout، retry محدود، rate limit و خطاها را یک‌دست کند.
- هیچ API Key را در exception یا log چاپ نکند.

### MarketUniverse / FeatureEngine

- نمادهای فعال API را با denylist `assets.md` و حداقل شرایط اجرای حساب ترکیب کند.
- ویژگی‌های price return، volatility/ATR، relative volume، spread، orderbook imbalance و روند را محاسبه کند.
- داده stale یا ناقص را علامت بزند؛ داده قدیمی نباید به Agent برسد.
- تمام بازارها را سبک غربال کند و فقط top-K Candidate را به مدل بدهد.

### AI Decision Service

- به‌صورت واقعی بین `momentum`, `trend_following`, `mean_reversion` (یا استراتژی‌های مورد تأیید) انتخاب کند و horizon/پارامترهای محدود را تعیین کند.
- prompt ثابت نسخه‌دار و پاسخ JSON با schema validation داشته باشد.
- context کوچک و متراکم بگیرد، نه کل order book و همه کندل‌ها.
- timeout، token cost، latency و raw validated output را ثبت کند.
- نتواند مستقیم API معامله را فراخوانی کند؛ فقط `TradeIntent` تولید می‌کند.
- fallback مدل: no-trade یا نگه‌داشتن موقعیت؛ نه درخواست دوباره نامحدود.

### Portfolio Allocator / Risk Engine

AI می‌تواند پیشنهاد سرمایه و خروج بدهد، اما این لایه مستقل است و پیش از اجرا باید همه شروط را enforce کند.

- سرمایه آزاد و قابل‌معامله را با API و position ledger تطبیق دهد.
- ریسک تا stop را به‌صورت notional risk محاسبه کند؛ از یکسان فرض‌کردن risk% و notional% پرهیز شود.
- max position notional، max total exposure، max open positions، cash reserve، max daily loss و max run drawdown را کنترل کند.
- هزینه برآوردی (fee + spread + slippage) را از expected edge کم کند.
- در شرایط stale data، account mismatch، unknown order state، drawdown stop یا API degradation ورود جدید را مسدود کند.
- stop/exit را با شروط و آستانه‌های قطعی enforce کند؛ تغییر AI نمی‌تواند kill switch را دور بزند.

### Order Executor

- تنها ماژول مجاز برای ارسال/cancel سفارش.
- قبل از ارسال: symbol، side، precision، min quantity/notional، available balance، open orders، risk approval و mode را validate کند.
- از client ID یکتا و DB persistence قبل از درخواست استفاده کند.
- در timeout، ابتدا order status reconcile شود؛ retry کور ممنوع.
- partial fill را پشتیبانی کند و پوزیشن را تنها بر اساس fill واقعی تغییر دهد.
- برای جلوگیری از self-trading، reversal را به‌صورت cancel-and-confirm سپس submit پیاده کند و در هر symbol فقط یک فرمان اجرایی هم‌زمان اجازه دهد.

### Trade Auditor / Learner

- محاسبه‌های P&L و اجرای گزارش deterministic باشند، نه وابسته به تفسیر LLM.
- AI می‌تواند بعد از معامله فرضیه علت زیان را با برچسب `confirmed / likely / unknown` پیشنهاد دهد؛ علت قطعی بدون داده تأییدشده مجاز نیست.
- تغییرات پارامترها را پیشنهاد کند؛ promotion به live تابع آزمون و معیارهای ازپیش‌تعریف‌شده باشد.

## 4. قراردادهای داخلی اصلی

حداقل مدل‌ها:

- `MarketInfo(symbol, base_asset, quote_asset, active, spot_enabled, min_qty, min_notional, qty_step, price_tick)`
- `MarketSnapshot(symbol, ts, bid, ask, last, candles, volume, spread_bps, volatility, imbalance, is_stale)`
- `Candidate(symbol, features, candidate_score, data_quality, estimated_cost_bps)`
- `TradeIntent(symbol, action, strategy_id, horizon, confidence, stop, target, max_holding, rationale, evidence_ids)`
- `RiskDecision(approved, approved_qty, reject_code, projected_exposure, risk_amount)`
- `OrderRecord(client_id, exchange_order_id, symbol, side, order_type, qty, fills, fee, state, timestamps)`
- `TradeRecord(entry/exit fills, net_realized_pnl_tmn, holding_time, close_reason, post_trade_analysis)`

Enumهای `action`, `strategy_id`, `mode`, `order_state`, `risk_reject_code` باید محدود و versioned باشند.

## 5. حالت‌های اجرا

`MODE=backtest | shadow | live`

- `backtest`: داده تاریخی/replay؛ هیچ درخواست private سفارش ارسال نمی‌شود.
- `shadow`: داده live و تصمیم حقیقی AI، اما سفارش‌ها مجازی‌اند؛ قیمت فرضی، fee/slippage و علت fill فرضی ثبت شود.
- `live`: فقط با `LIVE_TRADING_ENABLED=true` و تأیید راه‌اندازی وارد می‌شود.

Mode باید در هر log row و گزارش ثبت شود. هرگز از Shadow به Live با یک flag مبهم یا UI بی‌احراز هویت سوئیچ نشود.

## 6. ریسک‌های اجرایی و حداقل تنظیم اولیه

مقادیر زیر **مقادیر پیش‌فرض پیشنهادی برای شروع تست هستند، نه قانون هکاتون و نه استراتژی سود تضمین‌شده**. در config قابل‌تغییرند و پیش از Live با تیم مرور شوند:

```env
RISK_PER_TRADE_EQUITY_PCT=0.005
MAX_POSITION_NOTIONAL_EQUITY_PCT=0.15
MAX_TOTAL_EXPOSURE_EQUITY_PCT=0.40
MAX_OPEN_POSITIONS=3
MIN_CASH_RESERVE_EQUITY_PCT=0.50
MAX_DAILY_DRAWDOWN_EQUITY_PCT=0.025
MAX_RUN_DRAWDOWN_EQUITY_PCT=0.05
```

تعریف‌ها:

- `RISK_PER_TRADE`: زیان تخمینی تا stop نسبت به equity.
- `MAX_POSITION_NOTIONAL`: سقف ارزش ورودی یک پوزیشن.
- `MAX_TOTAL_EXPOSURE`: مجموع ارزش مواجهه فعال.
- `MIN_CASH_RESERVE`: حداقل وجه نقد آزاد.
- Drawdown limit: ایجاد موقعیت جدید را pause می‌کند، هشدار می‌فرستد و حسب policy سفارش‌های ورودی باز را cancel می‌کند. فروش اضطراری همه دارایی‌ها به‌صورت کور انجام نمی‌شود.

با رسیدن به stop/risk cap، Agent اجازه کاهش محدودیت‌ها را ندارد. مقادیر را در گزارش Backtest و نسخه config اجراشده ثبت کنید.

## 7. Observability

Dashboard حداقلی باید این موارد را نمایش دهد:

- mode و وضعیت RUNNING/PAUSED/SAFE-STOP
- balance، equity تقریبی، cash آزاد، exposure و reserve
- realized P&L net، fee و drawdown
- تعداد Candidateها، تصمیم‌های AI، تأخیر تصمیم، نرخ رد Risk Engine
- open positions / orders و وضعیت fill
- آخرین خطاها، reconnectها، health check و زمان آخرین داده معتبر
- دکمه‌های Pause New Entries، Resume (فقط پس از رفع علت توقف)، Cancel Open Entry Orders و Emergency Stop

Dashboard و control endpoints باید پشت auth و شبکه خصوصی باشند؛ روی اینترنت عمومی بدون محافظت publish نشوند.
