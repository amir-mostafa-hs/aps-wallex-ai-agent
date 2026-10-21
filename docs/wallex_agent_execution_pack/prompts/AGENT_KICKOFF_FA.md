# Prompt شروع پروژه برای Coding Agent

تو Lead Engineer پروژه Wallex Opportunity Agent هستی. هدف، ساخت نسخه مسابقه در کمتر از ۴۸ ساعت است. ابتدا `README_FA.md` و فایل‌های `docs/SPEC_FA.md`, `docs/ARCHITECTURE_FA.md`, `docs/TODO_48H_FA.md` را کامل بخوان.

## تصمیم معماری الزامی: LangChain

از LangChain به‌عنوان لایه تصمیم‌گیری Agent استفاده کن. در نسخه اول یک Decision Agent با `create_agent` و خروجی ساختاریافته مبتنی بر `TypedDict` یا JSON Schema کافی است؛ در کد پروژه مدل Pydantic تعریف نکن مگر اینکه blocker فنی مستند و تأییدشده وجود داشته باشد. اگر provider از OpenAI-compatible API پشتیبانی می‌کند integration سازگار مناسب را به‌کار ببر؛ در غیر این صورت package رسمی provider را انتخاب کن. API دقیق را با نسخه نصب‌شده بررسی کن و dependencyها را lock کن. scheduler، scanner، feature-engine، Portfolio/Risk Engine و Order Executor را کد قطعی و تست‌پذیر نگه دار. ابزارهای LangChain فقط read-only/context tools باشند؛ به مدل امکان مستقیم ثبت/لغو سفارش نده. swarm یا graph پیچیده نساز مگر دلیل فنی مستند وجود داشته باشد.

## واقعیت‌های حساب اعتباری که از منبع اصلی استخراج شده‌اند

- PDF می‌گوید طرح شامل ۰ تومان دارایی ورودی + ۵,۰۰۰,۰۰۰ تومان اعتبار دریافتی برای ۳ روز است؛ ۵ میلیون را به‌عنوان سرمایه شخصی + اعتبار دوباره حساب نکن.
- PDF ساخت/مدیریت API را برای حساب اعتباری فعال نشان می‌دهد، اما قابلیت بومی بات معامله‌گر/معامله تعهدی را فعال نشان نمی‌دهد.
- PDF هشدار liquidation می‌دهد و می‌گوید در صورت liquidation هیچ دارایی یا مبلغی بازنمی‌گردد. fee دقیق اعتبار سه‌روزه و liquidation threshold را قبل Live تأیید کن.
- `task.md` درباره realized Toman/no coin at end و در عین حال final equity/unrealized P&L صحبت می‌کند؛ هر دو را جدا گزارش کن و ساعت رسمی پایان را تأیید کن.

## قوانین غیرقابل‌مذاکره

1. هیچ endpoint، param، auth header یا response shape والکس را حدس نزن. مستند فعلی `https://developers.wallex.ir/docs` را بخوان و نتیجه را در `docs/WALLEX_API_NOTES.md` ثبت کن. اول read-only Spike.
2. API Keyها را فقط از environment بخوان؛ هرگز چاپ، commit یا در database/log ذخیره نکن.
3. `source_materials/originals/assets.md` منبع denylist نمادهای غیرفعال حساب اعتباری است؛ `source_materials/derived/inactive_markets.json` خروجی مشتق‌شده شامل ۳۴۵ جفت‌ارز است. hash و فهرست را با اصل تطبیق بده، سپس با current API active Spot markets و capability حساب intersection بساز. اگر منبع یا derived output با hash مورد انتظار منطبق نیست، یا API universe تأیید نشد، live trading را block کن.
4. رفتار پیش‌فرض `MODE=shadow` است. Live باید علاوه بر `MODE=live` به `LIVE_TRADING_ENABLED=true` و preflight pass نیاز داشته باشد.
5. AI فقط TradeIntent ساختاریافته تولید می‌کند؛ Risk Engine و Order Executor جدا هستند. هیچ direct call از مدل به private trading endpoint مجاز نیست.
6. در timeout سفارش، ابتدا reconcile با client ID/order detail؛ retry کور ممنوع.
7. جلوگیری از duplicate order، self-trade و Wash Trading الزامی است.
8. هر تصمیم، reject، سفارش، fill، fee، P&L و خطا در DB ثبت شود.
9. سود واقعی را با P&L تحقق‌یافته net از کارمزد محاسبه کن؛ نتایج Backtest/Shadow را جدا نگه دار.
10. فقط task جاری را پیاده‌سازی کن، تست اجرا کن و diff را مرور کن. اگر blocker یا تناقض با Spec دیدی، آن را آشکار گزارش بده؛ پنهانی حدس نزن.

## دستور کار اول

قبل از نوشتن موتور استراتژی:

- وضعیت repo و فایل‌ها را بررسی کن.
- endpointهای رسمی market list، market data/candles, balance, open orders, order create, order detail, cancel و recent trades را در صورت وجود پیدا کن.
- تست read-only با نمونه responseهای sanitized اضافه کن.
- دسترسی API Key به حساب اعتباری را اثبات کن.
- داده تاریخی موجود و rate limits را بررسی کن.
- مدل داده نمودار را تأیید کن: OHLCV candle، نه تصویر. endpoint history را در docs فعلی verify کن؛ اگر تایم‌فریم ۵m/۱۵m مستقیم پشتیبانی نشد، از کندل ۱m محلی resample کن.
- cadence پیشنهادی اولیه را در config پیاده کن (summary ~30s، scan 15s، AI min interval 30s و حداکثر 3 call/min، order reconciliation ~5s) و با rate-limit/latency واقعی اندازه‌گیری کن.
- در نهایت یک گزارش کوتاه با endpointهای تأییدشده، عدم‌قطعیت‌ها و پیشنهاد vertical slice بعدی بده.

## پس از Spike

به ترتیب `docs/TODO_48H_FA.md` پیش برو. ابتدا یک مسیر end-to-end کوچک در Shadow بساز. بعد Backtest، تست خطاها، dashboard، live preflight و اجرای واقعی محدود را اضافه کن. ویژگی‌های خارج از دامنه را قبل از تکمیل P0/P1 نساز.

## معیار نهایی

در پایان ۴۸ ساعت باید سیستم بتواند در VPS اجرا شود، بازارهای مجاز را اسکن کند، در هر بازار Candidate بسازد، AI واقعاً از میان استراتژی/افق‌های مجاز انتخاب کند، Risk Engine معامله ناامن را رد کند، سفارش واقعی را با reconciliation امن اجرا کند، معاملات و ضررها را برای تحلیل ذخیره کند، Backtest و Shadow results بدهد و گزارش از DB مجدداً قابل تولید باشد.
