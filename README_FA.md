# Wallex Opportunity Agent — بسته اجرایی هکاتون

**هدف:** تحویل یک AI Trading Agent قابل‌اجرا برای حساب اعتباری اختصاصی هکاتون والکس، با تمرکز بر معاملات Spot کوتاه‌مدت، اسکن چندبازاری، تخصیص تطبیقی سرمایه، مدیریت ریسک، اجرای پایدار، Backtest، Shadow Test و گزارش نهایی معاملات. در این نسخه، **LangChain لایه orchestration تصمیم AI** است؛ زمان‌بندی اسکن، محاسبه سیگنال، ریسک و اجرای سفارش در ماژول‌های قطعی باقی می‌مانند.

> این بسته، مشخصات و برنامه پیاده‌سازی است؛ سودآوری استراتژی را تضمین نمی‌کند. مقادیر اولیه ریسک در `docs/ARCHITECTURE_FA.md` فقط نقطه شروع محافظه‌کارانه برای آزمایش‌اند و باید قبل از معاملات واقعی تأیید شوند.

## فایل‌ها و ساختار مخزن

- `docs/specs/DECISION_REGISTER_FA.md` — تمام تصمیم‌های قطعی Grill-me و جدول امتیازدهی
- `docs/specs/GRILL_ME_HISTORY_FA.md` — تاریخچه گام‌به‌گام Grill-me و منطق انتخاب گزینه‌ها
- `docs/specs/AGENT_CONTRACT_FA.md` — منبع یگانه قرارداد ورودی/خروجی Agent، actionها و افق نگهداری
- `docs/specs/SPEC_FA.md` — صورت نیازمندی محصول، معیارهای پذیرش و محدوده نسخه اول
- `docs/specs/ARCHITECTURE_FA.md` — معماری پیشنهادی، LangChain و مرز مسئولیت Agent / Risk / Execution
- `docs/specs/MARKET_SCANNING_DECISION_LOGIC_FA.md` — cadence اسکن، دریافت/ساخت کندل، featureها و مسیر دقیق تصمیم ورود
- `docs/specs/TODO_48H_FA.md` — برنامه اولویت‌بندی‌شده برای ۴۸ ساعت توسعه
- `docs/specs/TESTING_REPORTING_FA.md` — بک‌تست، شدو تست، راه‌اندازی طولانی‌مدت و گزارش
- `docs/specs/WALLEX_API_NOTES.md` — endpoint inventory و Spike checklist
- `docs/specs/CODING_AGENT_WORKFLOW_FA.md` — گردش‌کار Codex / Antigravity و مهارت‌های Matt Pocock
- `docs/specs/PACKAGE_CONTENTS_FA.md` — فهرست کامل محتویات بسته
- `docs/agents/` — پیکربندی مهارت‌های مهندسی Matt Pocock (ردیاب تسک، برچسب‌های تریاژ و مستندات دامنه)
- `docs/prompts/AGENT_KICKOFF_FA.md` — پرامپت آماده شروع کار با Coding Agent
- `docs/reports/FINAL_REPORT_TEMPLATE.md` — قالب گزارش معامله
- `docs/sources/` — منابع اولیه هکاتون (`assets.md`، `task.md`، `intro-text.md` و denylist بازارهای غیرفعال `inactive_markets.json`)
- `docs/media/` — رسانه‌های ویدیویی و صوتی معرفی هکاتون
- `.env.example` — فهرست تنظیمات و نام Secretها؛ هیچ کلید واقعی در آن قرار ندهید.

## تصمیم‌های تثبیت‌شده

1. حساب: حساب اعتباری اختصاصی هکاتون؛ معاملات Spot و بدون لوریج. اجرای سفارش‌ها پس از فعال‌سازی Live و preflight کاملاً خودکار است؛ تأیید دستی تک‌تک سفارش‌ها وجود ندارد.
2. سرمایه مبنای مسابقه ۵ میلیون تومان است؛ PDF می‌گوید ۰ تومان دارایی ورودی + ۵ میلیون تومان اعتبار سه‌روزه. مبلغ را دو بار نشمارید؛ شرایط و موجودی واقعی حساب باید تأیید شود.
3. نمادها: اصل `source_materials/originals/assets.md` شامل denylist ۳۴۵ جفت بازار غیرفعال است؛ آن را با بازارهای فعال Spot در API و قابلیت واقعی حساب تطبیق دهید.
4. ایده: Opportunity Radar چندبازاری؛ هر بازار مستقل ارزیابی می‌شود، سپس فرصت‌ها در سطح پرتفوی رتبه‌بندی و سرمایه به‌صورت تطبیقی تخصیص داده می‌شود.
5. نسخه اول: انتخاب بین استراتژی‌ها و تنظیم پارامترهای مجاز (Option B). تغییر اساسی یا تولید استراتژی جدید تنها پس از آزمون (حرکت تدریجی به Option C).
6. Orchestration AI با LangChain؛ فقط یک Decision Agent در نسخه مسابقه، با خروجی ساختاریافته TypedDict/JSON Schema. هیچ دسترسی مستقیم به ابزار ارسال سفارش ندارد.
7. تصمیم AI: انتخاب فرصت، استراتژی، افق زمانی و پارامترهای مجاز؛ لایه قطعی ریسک و اجرا تصمیم ناامن را رد می‌کند.
8. معاملات: چند موقعیت باز مجاز، اما با سقف exposure، ریسک، تعداد موقعیت و ذخیره نقدی.
9. تست: Backtest و Shadow Test موازی با توسعه؛ معاملات واقعی فقط بعد از عبور از دروازه‌های ایمنی.
10. خبر/فاندامنتال: خارج از دامنه نسخه اول؛ تمرکز بر قیمت، حجم، نقدشوندگی، نوسان و داده‌های بازار.
11. خروج: روش ترکیبی؛ مدیریت تطبیقی خروج توسط Agent در چارچوب سقف‌های قطعی ریسک.
12. گزارش: سود/زیان تحقق‌یافته خالص، کارمزد، حجم، افت سرمایه، کیفیت اجرا، دلیل تصمیم‌ها و زیان‌های توضیح‌داده‌شده یا نامشخص ثبت شوند.

## مسیر سریع شروع

1. این پوشه را داخل مخزن پروژه قرار دهید یا محتوای آن را به مخزن جدید منتقل کنید.
2. قبل از پیاده‌سازی، `docs/specs/DECISION_REGISTER_FA.md`, `docs/specs/AGENT_CONTRACT_FA.md`, `docs/specs/SPEC_FA.md` و `docs/specs/ARCHITECTURE_FA.md` را به Coding Agent بدهید.
3. ابتدا `docs/specs/MARKET_SCANNING_DECISION_LOGIC_FA.md` را بخوانید؛ تفاوت cadence اسکن با timeframe کندل و AI review interval را رعایت کنید.
4. ابتدا فقط یک vertical slice بسازید: دریافت بازارها و موجودی → تولید یک Candidate → LangChain تصمیم ساختاریافته → Risk Engine → ثبت در SQLite → Shadow Order → گزارش نتیجه.
5. پس از کارکردن مسیر عمودی، اجرای واقعی را با دروازه‌های سخت ایمنی فعال کنید. Live نیازمند `MODE=live`, `LIVE_TRADING_ENABLED=true`, `LIVE_PREFLIGHT_ACKNOWLEDGED=true` و تأیید preflight است؛ این تأیید یک‌باره است و سفارش‌های پس از آن خودکار اجرا می‌شوند.
6. هیچ‌وقت API Key را در Git، لاگ، Screenshot یا پرامپت ذخیره نکنید.
7. `docs/specs/AGENT_CONTRACT_FA.md` مرجع action و horizon است؛ در صورت اختلاف با مثال‌های قدیمی‌تر، این قرارداد و سپس SPEC اصلاح‌شده ملاک است.
8. LangChain لایه Agent است؛ هیچ Pydantic model در کد دامنه تعریف نشود. وجود Pydantic به‌عنوان dependency ترانزیتی به‌تنهایی خطا نیست.
9. منابع اصلی در `docs/sources/` (`assets.md` و ...) و `docs/media/` حفظ شده‌اند؛ `docs/sources/assets.md` به‌صورت اصلی و در کنار denylist مشتق‌شده (۳۴۵ جفت غیرفعال در `docs/sources/inactive_markets.json`) موجود است. پیش از Live، فایل مشتق‌شده باید با API فعال Spot و capability واقعی حساب تطبیق داده شود. موارد تأییدنشده، از جمله کارمزد اعتبار سه‌روزه، threshold liquidation، و روش/زمان رسمی پایان مسابقه، در اسناد ثبت شده‌اند.

## منابع فنی مرجع

- Wallex API: https://developers.wallex.ir/docs
- Wallex market/API landing: https://developers.wallex.ir/
- Wallex ثبت سفارش Spot: https://developers.wallex.ir/spot/createorder
- Wallex جزئیات سفارش: https://developers.wallex.ir/spot/singleorderdetail
- Wallex MCP: https://wallex.ir/landing/mcp/
- Matt Pocock skills: https://www.aihero.dev/skills
- Matt Pocock GitHub: https://github.com/mattpocock/skills

## محدودیت مهم

قبل از کدنویسی کامل، یک Spike فنی کوتاه لازم است: تأیید اینکه API Key به حساب اعتباری هکاتون دسترسی درست دارد، endpointهای بازار و موجودی قابل‌اتکا هستند، حداقل حجم/گام قیمت معلوم است، و داده تاریخی/کندل برای بک‌تست با چه endpoint و محدودیت نرخ در دسترس است. اگر داده تاریخی کافی در دسترس نبود، این محدودیت باید در گزارش Backtest شفاف نوشته شود؛ داده ساختگی را به‌عنوان داده واقعی گزارش نکنید.

## هشدار حساب اعتباری (از PDF اصلی)

PDF طرح می‌گوید ۰ تومان دارایی ورودی + ۵,۰۰۰,۰۰۰ تومان اعتبار برای ۳ روز؛ حساب credit در صورت کاهش ارزش تا threshold می‌تواند liquidation شود و متن می‌گوید پس از liquidation دارایی/مبلغی بازنمی‌گردد. جدول PDF ساخت/مدیریت API را در حساب اعتباری نشان می‌دهد، اما قابلیت بومی «بات معامله‌گر» و معامله تعهدی را فعال نشان نمی‌دهد. هزینه دقیق اعتبار سه‌روزه و thresholdها را قبل از Live تأیید کنید. جزئیات در `docs/SOURCE_REVIEW_FA.md` است.
