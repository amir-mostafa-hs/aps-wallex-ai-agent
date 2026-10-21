# مراجع متن‌باز و ابزارهای مهندسی مورد بررسی

این سند مراجع برای اقتباس از الگوهاست، نه توصیه برای کپی کامل مخزن. هیچ‌یک از مخازن زیر به‌عنوان اتصال آماده و تأییدشده Wallex فرض نمی‌شود؛ کد و license باید قبل از اقتباس بررسی شود.

## 1. نمونه‌های معاملاتی/Agent

### Bitpin AI Trader
- Repo: https://github.com/Erfouni/bitpin-ai-trader
- چرا بررسی شد: نمونه مرتبط با فضای صرافی ایرانی و مسابقه AI trading؛ ایده جداسازی تحلیل مدل از کنترل اجرایی، مشاهده‌پذیری و گزارش‌دهی برای ما مفید است.
- احتیاط: کد کامل این پروژه در این کار ممیزی نشده و cadence/معماری آن لزوماً متناسب با معاملات کوتاه‌مدت سه‌روزه نیست. آن را الگوی مفهومی ببینید، نه کد production آماده.

### Freqtrade
- Repo: https://github.com/freqtrade/freqtrade
- مفید برای: backtesting، استراتژی، گزارش معامله و برخی الگوهای مدیریت اجرا.
- احتیاط: از پشتیبانی آماده Wallex فرض نکنید؛ قبل از استفاده، فهرست exchangeها و نیاز اتصال را در نسخه جاری بررسی کنید. احتمالاً ساخت/تأیید adapter اختصاصی لازم است.

### Hummingbot
- Repo: https://github.com/hummingbot/hummingbot
- مفید برای: مفهوم چرخه اجرای استراتژی، مدیریت سفارش و اتصال به صرافی‌ها.
- احتیاط: آوردن کامل چارچوب در مهلت ۴۸ ساعته احتمالاً پیچیدگی زیادی ایجاد می‌کند؛ فقط قطعه‌ای را اقتباس کنید که نیاز روشن را حل می‌کند.

### TradingAgents
- Repo: https://github.com/TauricResearch/TradingAgents
- مفید برای: جداسازی نقش‌های تحلیل، تصمیم و ریسک و مستندسازی شواهد تصمیم.
- احتیاط: چارچوب تحقیقاتی چندایجنتی، جایگزین آماده موتور اجرای سفارش Wallex نیست؛ swarm سنگین در MVP خارج از دامنه است.

## 2. تصمیم برای پروژه ما

- از هیچ پروژه‌ای به‌عنوان exchange adapter آماده استفاده نکنید مگر پشتیبانی و رفتار واقعی Wallex اثبات شود.
- در نسخه مسابقه، یک سرویس Python ماژولار و یک LangChain Decision Agent کافی است؛ scanner و risk/execution deterministic باقی می‌مانند.
- Backtest/Shadow/Live باید قرارداد تصمیم و محاسبات feature/risk مشترک داشته باشند.

## 3. LangChain و خروجی ساختاریافته

- Agents: https://docs.langchain.com/oss/python/langchain/agents
- Structured output: https://docs.langchain.com/oss/python/langchain/structured-output
- LangChain structured output می‌تواند با `TypedDict` یا JSON Schema استفاده شود؛ برای شروع TypedDict class را مستقیم به strategy/schema argument قابل پشتیبانی نسخه نصب‌شده بده. JSON Schema خام را طبق نسخه LangChain در `ProviderStrategy` یا `ToolStrategy` مناسب قرار بده. نسخه package و provider باید pin/smoke-test شود. Validator تجاری مستقل همچنان لازم است. هیچ Pydantic model در کد دامنه تعریف نشود.

## 4. AI Hero / Matt Pocock Skills

- فهرست رسمی: https://www.aihero.dev/skills
- repo رسمی: https://github.com/mattpocock/skills
- نصب: `npx skills@latest add mattpocock/skills`
- چرخه پیشنهادی برای این پروژه: `/setup-matt-pocock-skills` در صورت نیاز → `/grill-with-docs` (تصمیم‌ها در این گفت‌وگو انجام شده) → `/to-spec` برای ثبت spec اگر لازم شد → `/to-tickets` → یک ticket در هر نوبت با `/implement` → TDD در seamهای مورد توافق → `/code-review`.
- هر Ticket باید یک رفتار قابل‌دمو در کل مسیر بدهد، blockers روشن داشته باشد و تست مشخص ارائه کند؛ Ticketها را صرفاً بر اساس لایه‌های فنی تقسیم نکنید.
- AI Hero صفحه فعلی ابزارهایی مانند Codex را فهرست می‌کند. سازگاری مستقیم Antigravity در بررسی فعلی قطعی نشده؛ به‌جای فرض، نصب و اجرای smoke test در همان ابزار انجام شود.

## 5. مستندات Wallex

- API docs: https://developers.wallex.ir/docs
- MCP: https://wallex.ir/landing/mcp/
- MCP به‌عنوان راه اختیاری برای اتصال Agent به ابزارهای read-only قابل ارزیابی است؛ مسیر اصلی ایجاد/لغو سفارش MVP از API مستقیم و adapter دارای تست باشد مگر اینکه نیاز/محدودیت تأییدشده‌ای دلیل دیگری بیاورد.
- هر endpoint در `WALLEX_API_NOTES.md` تا وقتی مستند جاری، sanitized response و تست آن ثبت نشده، `Confirmed` محسوب نشود.
