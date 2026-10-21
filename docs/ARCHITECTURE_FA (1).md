# معماری فنی پیشنهادی

## 1. تصمیم معماری برای مهلت ۴۸ ساعته

**پیشنهاد:** یک سرویس Python واحد با ماژول‌های کوچک و interfaceهای مشخص؛ نه microservice و نه swarm سنگین.

دلایل: کتابخانه‌های بالغ تحلیل داده، پیاده‌سازی سریع Backtest، تست‌پذیری، امکان اجرای asyncio و سادگی Deploy. Matt Pocock skills به روش کار Coding Agent مربوط است و محدود به زبان TypeScript نیست. اگر تیم از قبل در TypeScript بسیار سریع‌تر است، این تصمیم قابل تغییر است؛ اما در مهلت فعلی Python مسیر پیش‌فرض است.

پشته پیشنهادی:

- Python 3.12+
- **LangChain برای لایه تصمیم‌گیری AI**: استفاده از API مدرن `create_agent` و خروجی ساختاریافته مبتنی بر Pydantic؛ نه زنجیره قدیمی/غیرضروری و نه swarm چندعاملی.
- اتصال مدل ابری: اگر provider از API سازگار با OpenAI پشتیبانی می‌کند، adapter مناسب LangChain مثل `langchain-openai`؛ در غیر این صورت integration رسمی همان provider. مدل و provider در config قابل تعویض بمانند.
- `httpx` برای REST و کتابخانه WebSocket سازگار با مستندات فعلی والکس
- `pydantic` برای config و schema پاسخ مدل
- `pytest` برای تست، `ruff` برای lint/format، `mypy` در صورت زمان
- `SQLite` با WAL برای event/trade/decision logs و تنظیمات کوچک
- `FastAPI` برای health/status/control endpoints و یک صفحه ساده وضعیت
- `pandas`/`numpy` فقط جایی که برای features و backtest لازم است
- Docker Compose یا systemd برای اجرای پایدار روی VPS؛ یکی را انتخاب کنید و هم‌زمان هر دو deployment را نسازید.

**مرز مهم LangChain:** LangChain خروجی تصمیم Agent را orchestration و ساختاریافته می‌کند؛ scheduler، جمع‌آوری داده، محاسبه ویژگی‌ها، تخصیص سرمایه، Risk Engine و Order Executor در کد عادی و قابل‌آزمون می‌مانند. Agent هیچ ابزار ثبت/لغو سفارش و هیچ API Key والکس برای معامله دریافت نمی‌کند؛ نهایت خروجی‌اش یک `TradeIntent` است. `LangGraph` فقط اگر بعداً به workflow stateful/چندمرحله‌ای واقعاً نیاز شد اضافه شود؛ در نسخه مسابقه، یک Agent تصمیم‌گیر کافی است.

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
MarketDataStore -> CandleBuilder -> FeatureEngine -> CandidateScanner
                                                    |
                                                    v
                                       LangChain Decision Agent
                                       (Pydantic TradeIntent)
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

### LangChain Decision Agent

- در پیاده‌سازی از API مدرن LangChain (`create_agent`) و خروجی ساختاریافته Pydantic استفاده شود؛ نام دقیق importها با نسخه lock شده package تطبیق داده شود.
- به‌صورت واقعی بین `momentum`, `trend_following`, `mean_reversion` (یا استراتژی‌های مورد تأیید) انتخاب کند و horizon/پارامترهای محدود را تعیین کند.
- prompt ثابت نسخه‌دار و پاسخ JSON/schema validation داشته باشد.
- context کوچک و متراکم بگیرد، نه کل order book و همه کندل‌ها: آخرین snapshot، ویژگی‌های مشتق‌شده، وضعیت حساب/پوزیشن و هزینه اجرای برآوردی.
- ابزارهای در دسترس Agent فقط read-only و domain-specific باشند؛ private trading endpoint به Agent داده نشود.
- timeout، token cost، latency، model/provider version و خروجی validated ثبت شود.
- فقط `TradeIntent` تولید می‌کند؛ تصمیم نهایی اجرا به Risk Engine واگذار می‌شود.
- fallback مدل: `NO_TRADE` یا نگه‌داشتن مدیریت امن موقعیت؛ نه درخواست دوباره نامحدود.

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

## 3.1 زمان‌بندی اسکن و داده‌های نمودار

جزئیات اجرایی و منطق ورود در `docs/MARKET_SCANNING_DECISION_LOGIC_FA.md` ثبت شده است. Baseline پیشنهادی برای روز اول، پس از بررسی rate-limit:

- refresh فهرست بازار و metadata: هر ۱۵ دقیقه و هنگام startup/reconnect
- refresh خلاصه قیمت/بازار برای کل universe: حدود هر ۳۰ ثانیه (فقط اگر endpoint تجمیعی و rate limit اجازه دهند)
- recalculation اسکنر روی cache تازه: هر ۱۵ ثانیه
- WebSocket معاملات/عمق: event-driven برای بازارهای قابل subscribe؛ اتصال باید heartbeat و reconnect امن داشته باشد
- بازبینی AI: حداقل فاصله ۳۰ ثانیه بین فراخوانی‌ها، حداکثر ۳ فراخوانی در دقیقه در نسخه اولیه؛ رویداد مهم می‌تواند candidate را زودتر علامت بزند اما نباید budget را دور بزند
- پیگیری وضعیت سفارش/پوزیشن: event-driven به‌همراه reconcile دوره‌ای هر ۵ ثانیه (پس از تأیید محدودیت API)
- reconcile موجودی حساب: هر ۳۰ ثانیه و هنگام startup / بعد از رخداد نامشخص سفارش

این مقادیر **تنظیم پیشنهادی قابل‌آزمایش‌اند، نه محدودیت رسمی والکس یا بهینه‌سازی اثبات‌شده**. اگر rate limit، تعداد بازارها یا تأخیر مدل اجازه نداد، فرکانس را کم کنید؛ برای حفظ uptime، نه باید API را flood کرد و نه LLM را روی هر tick فراخواند.

**تفکیک سه مفهوم:** (۱) scan interval، فاصله زمانی محاسبه دوباره فرصت‌هاست؛ (۲) candle timeframe، طول هر کندل OHLCV است؛ (۳) AI review interval، حداقل فاصله‌ای است که مدل دوباره تصمیم عمیق می‌دهد. برای این پروژه این‌ها یکی نیستند.

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
