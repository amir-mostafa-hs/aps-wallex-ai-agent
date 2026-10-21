# TODO اجرایی ۴۸ ساعته

## راهنمای اولویت

- **P0:** برای ارسال اولین سفارش واقعی و حفظ حساب لازم است.
- **P1:** برای امتیاز فنی، تکرارپذیری و گزارش معتبر لازم است.
- **P2:** فقط اگر زمان پس از تکمیل P0/P1 ماند.

قانون اجرایی: هر Task باید یک رفتار قابل‌دمو و تست مشخص داشته باشد. تا وقتی P0های ایمنی و ثبت رویداد تمام نشده‌اند، UI یا استراتژی‌های متعدد را polish نکنید.

## Day 1 — تأیید زیرساخت و ساخت مسیر عمودی

### ساعت ۰ تا ۲ — شروع Repo و Spike فنی [P0]

- [ ] ساخت Git repo و branch اصلی، `.gitignore`, `pyproject.toml`, `.env.example` و logging پایه.
- [ ] نصب و اجرای Matt Pocock skills (در صورت سازگاری ابزار): `npx skills@latest add mattpocock/skills`.
- [ ] خواندن مستند فعلی Wallex API، ثبت endpointها و schemaها در `docs/WALLEX_API_NOTES.md`.
- [ ] با API Key فعلی، فقط درخواست‌های read-only انجام شود: account/balance، markets، open orders/trades اگر در API موجود است.
- [ ] اثبات دسترسی واقعی کلید به حساب اعتباری؛ account identifier/نوع حساب و balance باید ثبت و تأیید شوند.
- [ ] استخراج دقیق نمادهای ممنوع از `assets.md` و ذخیره در config versioned؛ فهرست مجاز نهایی از intersection API-active Spot و denylist ساخته شود.
- [ ] تأیید min quantity/notional، tick size، step size، endpointهای order details/cancel و محدودیت درخواست.
- [ ] شناسایی تاریخچه کندل و داده کافی برای Backtest. اگر موجود نبود، مانع را ثبت و مسیر fallback مشخص کن.
- [ ] LangChain را با adapter درست برای LLM API کاربر اضافه کن؛ `TradeIntent` ساختاریافته Pydantic را smoke-test کن. هیچ ابزار معامله خصوصی به Agent نده.
- [ ] endpoint کندل را در docs فعلی تأیید کن؛ فقط به نمونه قدیمی `/v1/udf/history` تکیه نکن. اگر endpoint 5m/15m تأیید نشد، از کندل 1m، locally resample کن.

**خروجی ساعت ۲:** یادداشت API با نمونه پاسخ‌های sanitized، market denylist بررسی‌شده، `.env.example`، فهرست موانع. اگر API حساب اعتباری کار نمی‌کند، بقیه کار به Mock/Shadow local ادامه یابد و Live متوقف بماند.

### ساعت ۲ تا ۶ — Vertical slice داده تا ذخیره‌سازی [P0]

- [ ] پیاده‌سازی `WallexAdapter` برای لیست بازار، balance، market data و order lookup/cancel/create (در ابتدا create فقط پشت live guard).
- [ ] مدل‌های typed با Pydantic و validation پاسخ API.
- [ ] SQLite با WAL و جدول‌های حداقلی: `market_snapshot`, `candidate`, `ai_decision`, `risk_event`, `order`, `fill`, `position`, `system_event`.
- [ ] همه timestampها UTC؛ raw secrets هرگز وارد DB/log نشوند.
- [ ] یک CLI/command اجرا شود که بازارهای مجاز و balance را چاپ کند و snapshot را DB بنویسد.

**Acceptance:** اجرای دوباره همان command خطا ندهد؛ یک بازار ممنوع نمایش داده نشود؛ مقادیر منبع با API تطبیق داشته باشد.

### ساعت ۶ تا ۱۰ — Scanner و Candidate scoring [P0]

- [ ] Market universe را از API + denylist بساز.
- [ ] دریافت داده warm-up کندل 1m و ساخت محلی 5m/15m/1h؛ فقط تایم‌فریم‌هایی که با endpoint/داده موجود قابل پشتیبانی‌اند فعال شوند.
- [ ] پیاده‌سازی cadence تفکیک‌شده: feature scan هر 15s، market-summary refresh حدود 30s، AI review حداقل هر 30s (budget اولیه حداکثر 3 call/min)، order reconcile حدود 5s؛ همه قابل تنظیم و مشروط به rate-limit تست‌شده.
- [ ] build/rebuild کندل‌های محلی از stream trade؛ روی کندل ناتمام با احتیاط رفتار شود و timestamp/freshness ثبت گردد.
- [ ] محاسبه ویژگی‌های کم‌هزینه: returns، trend/EMA slope، volatility/ATR، relative volume، spread، depth/imbalance و data freshness.
- [ ] فیلتر نقدشوندگی/حداقل ارزش و stale data.
- [ ] Candidate ranker بساز که تمام بازارها را بررسی کند، اما فقط top-K را برای AI بفرستد.
- [ ] خروجی هر چرخه، score و علت حذف/قبول هر بازار را ذخیره کند.

**Acceptance:** روی fixtureهای ثابت نتایج قابل‌تکرارند؛ candidate بدون داده کافی هرگز به مدل نمی‌رسد.

### ساعت ۱۰ تا ۱۳ — AI Decision Service [P0]

- [ ] تعریف schema نسخه‌دار برای `TradeIntent`.
- [ ] اجرای یک فراخوانی LangChain Agent روی top Candidateها؛ ورودی شامل ویژگی‌ها و context محدود؛ خروجی Pydantic/JSON schema اعتبارسنجی شود.
- [ ] اجازه انتخاب strategy/horizon و پارامترهای bounded؛ هیچ call مستقیم به trade API از مدل.
- [ ] اعتبارسنجی JSON، timeout، retry محدود، هزینه/latency log و fallback به NO_TRADE.
- [ ] ثبت مدل، prompt version، ورودی/خروجی sanitized و rationale.

**Acceptance:** پاسخ نامعتبر، confidence بیرون بازه، symbol خارج از allowlist یا پارامتر خارج از حدود منجر به سفارش نمی‌شود.

### ساعت ۱۳ تا ۱۷ — Risk Engine و Portfolio Allocator [P0]

- [ ] تنظیم مقدارهای آغازین در `.env` و مرور انسانی قبل Live.
- [ ] sizing با فاصله stop، ریسک پولی، سقف notional، سرمایه آزاد، cash reserve و max aggregate exposure.
- [ ] چند position هم‌زمان و max open positions.
- [ ] فیلتر expected edge پس از fee/spread/slippage.
- [ ] daily/run drawdown gate و stop/hold behavior.
- [ ] reject reasonهای مشخص مثل `STALE_DATA`, `INSUFFICIENT_BALANCE`, `MAX_EXPOSURE`, `EDGE_BELOW_COST`, `DRAWDOWN_LIMIT`.

**Acceptance:** تست‌های مرزی اثبات کنند که AI نمی‌تواند limitها را دور بزند؛ حجم بزرگ یا بازار ممنوع رد شود.

### ساعت ۱۷ تا ۲۱ — Execution state machine [P0]

- [ ] Order state machine، client ID یکتا و DB persistence قبل از submit.
- [ ] مدیریت `FILLED`, `PARTIALLY_FILLED`, `CANCELLED`, `REJECTED` و `UNKNOWN`.
- [ ] پس از timeout، ابتدا query/reconcile شود؛ retry کور ممنوع.
- [ ] startup reconciliation با balance/open orders/trades.
- [ ] single-writer lock، per-symbol lock و جلوگیری از self-trade: قبل از سفارش مخالف، cancel و تأیید سفارش باز قبلی.
- [ ] تست روی Mock exchange: timeout بعد از پذیرفته‌شدن سفارش، partial fill، cancel failure، restart.

**Acceptance:** سناریوی timeout/restart دو سفارش ناخواسته ایجاد نمی‌کند.

### ساعت ۲۱ تا ۲۴ — اولین end-to-end در Shadow [P0]

- [ ] اجرای loop کامل: scanner → AI → risk → simulated executor → DB.
- [ ] ثبت ردها، تصمیمات بدون معامله و فرضیات قیمت/fee/slippage Shadow.
- [ ] اجرای پیوسته حداقل ۳۰ تا ۶۰ دقیقه در Shadow و مرور خطاها (این بازه پیشنهاد اجرایی است، نه قانون برگزارکننده).
- [ ] ساخت dashboard/CLI وضعیت حداقلی یا endpoint `/health`, `/status`, `/pause`, `/resume`, `/kill` پشت auth.

**Milestone پایان Day 1:** سیستم می‌تواند بدون ارسال سفارش واقعی، از ابتدا تا انتها پایدار اجرا و تمام تصمیم‌ها را بازسازی کند.

## Day 2 — تست، اجرای واقعی، پایداری و تحویل

### ساعت ۲۴ تا ۲۸ — Backtest حداقلی اما معتبر [P1]

- [ ] replay تاریخچه با همان قرارداد strategy/feature/risk.
- [ ] لحاظ کردن fee واقعی از تنظیمات/endpoint، spread/slippage محافظه‌کارانه، minimum quantity و عدم استفاده از داده آینده.
- [ ] تست در چند بازار و چند رژیم، نه فقط نماد/بازه برنده.
- [ ] گزارش: net P&L، drawdown، تعداد معاملات، win rate، profit factor، expectancy، fees، average hold و assumptions.
- [ ] اگر history کافی در دسترس نیست، گزارش محدودیت را ثبت کن؛ داده ساختگی را نتیجه Backtest معرفی نکن.

### ساعت ۲۸ تا ۳۲ — تست سناریویی و Shadow مقایسه‌ای [P0/P1]

- [ ] unit/integration tests: fee, sizing, stops, partial fill, API timeout, stale data, model timeout, invalid JSON, precision, min notional.
- [ ] تست Self-Trade/Wash guard و restart reconciliation.
- [ ] اجرای Shadow دوم با config ثابت؛ مقایسه خروجی‌ها و latency.
- [ ] اجرای `/code-review` روی diff و رفع P0/P1 findings.

### ساعت ۳۲ تا ۳۵ — Live preflight [P0]

- [ ] کلید API حداقل‌دسترسی؛ برداشت/withdrawal مجاز نباشد اگر چنین scopeی موجود است؛ Secret فقط در محیط runtime.
- [ ] تأیید حساب اعتباری، balance و نمادهای قابل معامله.
- [ ] صحت محاسبه fee/quantity/tick/step/min notional.
- [ ] Live خاموش پیش‌فرض؛ فقط با flag واضح و تأیید دستی فعال شود.
- [ ] تست ایجاد/cancel سفارش تنها طبق قوانین مسابقه و با کمترین حجم مجاز، اگر این تست پیش از مسابقه مجاز است. اگر نیست، اولین سفارش واقعی فقط پس از بررسی کامل کنترل‌ها.
- [ ] روی VPS firewall و dashboard auth تنظیم شود؛ زمان سیستم sync باشد.

### ساعت ۳۵ تا ۳۸ — شروع معاملات واقعی با کنترل ریسک [P0]

- [ ] deploy نسخه tag شده و ثبت commit hash/config hash/prompt version.
- [ ] اطمینان از فقط یک process اجرایی.
- [ ] شروع live با مقادیر محافظه‌کارانه؛ ابتدا مراقبت انسانی از اولین سفارش و اولین fill؛ سپس اجازه unattended طبق runbook.
- [ ] alert/log برای drawdown، feed stale، API outage، model outage، unknown order state و execution error.
- [ ] بعد از اولین معامله، بازسازی دستی P&L یک معامله از fills و fee واقعی.

### ساعت ۳۸ تا ۴۲ — تثبیت و Observability [P1]

- [ ] نمایش حساب، equity، P&L، exposure، cash reserve، open positions/orders، latest AI decisions، ریسک ردشده و API health.
- [ ] دکمه/فرمان Pause New Entries و Emergency Stop تست شود.
- [ ] restart کنترل‌شده؛ اثبات بدون duplicate order و با positions درست.
- [ ] rotation و backup دیتابیس.
- [ ] snapshot گزارش هر ۱۵ دقیقه/ساعتی بر اساس نیاز منابع؛ گزارش‌گیری نباید loop معامله را block کند.

### ساعت ۴۲ تا ۴۶ — Runbook، تحویل، دموی فنی [P1]

- [ ] README: نصب، `.env`, run modes، start/stop/restart، recovery، تولید گزارش.
- [ ] ثبت نسخه dependency lock و commit مربوط به اجرای زنده.
- [ ] مستند معماری و تصمیم‌های استراتژی.
- [ ] نمونه لاگ یک معامله سودده، یک زیان‌ده/ردشده و یک خطا با داده حساس حذف‌شده.
- [ ] آماده‌سازی سناریوی دمو حدود ۵ دقیقه، طبق نیاز مطرح‌شده در بریف قبلی.
- [ ] گرفتن artifactهای Backtest و Shadow و تصویربرداری/خروجی dashboard.

### ساعت ۴۶ تا ۴۸ — Gate نهایی و freeze [P0/P1]

- [ ] `pytest`، lint، smoke test و health check سبز.
- [ ] مرور آخرین ۳۰ تا ۶۰ دقیقه لاگ live؛ اگر خطای سفارش نامشخص یا drift موجودی وجود دارد، pause و reconcile.
- [ ] tag نسخه مسابقه و ذخیره config فعال، prompt version و commit hash.
- [ ] تأیید اینکه معاملات live ادامه دارند و DB/event logging رشد می‌کند.
- [ ] هر قابلیت P2 که ریسک regression دارد به بعد از مسابقه منتقل شود.

## پس از ۴۸ ساعت — Bot Run و گزارش معامله

- [ ] سرویس به‌صورت پیوسته در طول پنجره مجاز مسابقه اجرا شود؛ restart/health monitoring فعال باشد.
- [ ] snapshotهای دوره‌ای و event logs ذخیره شوند.
- [ ] پایان دوره: sync نهایی orders/trades/balance با API؛ هیچ open order یا position در محاسبه P&L نادیده گرفته نشود.
- [ ] تولید `reports/final_report.md` و فایل CSV/JSON شامل trades، fills، decisions و risk events.
- [ ] گزارش سود و زیان تحقق‌یافته خالص به تومان، fees، gross volume، max drawdown، تعداد معاملات، uptime، خطاها، زمان تصمیم و نرخ fill را پوشش دهد.
- [ ] اگر مسابقه پایان یافته، تا زمان تطبیق مانده‌ها سفارش جدید ثبت نشود.

## ترتیب اجرای حداقلی اگر زمان کم آمد

۱) دسترسی/market universe → ۲) risk engine → ۳) order state machine → ۴) DB logs → ۵) یک استراتژی + AI انتخاب واقعی → ۶) Shadow → ۷) Live safety gate → ۸) گزارش. داشبورد زیبا، اخبار، strategy generation و swarm چندایجنتی را قربانی کنید؛ نه کنترل ریسک، reconciliation یا لاگ را.
