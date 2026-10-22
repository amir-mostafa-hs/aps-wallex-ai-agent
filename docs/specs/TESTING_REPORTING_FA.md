# Backtest، Shadow Test، Live Validation و گزارش نهایی

## 1. تفاوت سه حالت

| حالت | منبع داده | سفارش واقعی | چه چیزی را اثبات می‌کند؟ |
|---|---|---|---|
| Backtest | تاریخچه/replay | خیر | رفتار روی گذشته با مفروضات معلوم |
| Shadow | بازار زنده | خیر | latency، تصمیم AI، کیفیت داده و منطق بدون ریسک سرمایه |
| Live | بازار زنده + account API | بله | اجرای واقعی، fill، fee، پایداری و P&L تحقق‌یافته |

هر mode باید از هم جدا، در لاگ و گزارش قابل تشخیص باشد. نتایج Shadow یا Backtest هرگز به‌عنوان سود تحقق‌یافته گزارش نشوند.

## 2. قرارداد Backtest

- استراتژی و Feature Engine با live مشترک باشند.
- زمان هر تصمیم فقط از داده‌های در دسترس تا همان لحظه استفاده کند؛ look-ahead ممنوع.
- کارمزد از تنظیمات/منبع تأییدشده، spread/slippage محافظه‌کارانه و محدودیت مقدار در نظر گرفته شوند.
- order fills بر اساس فرضیه‌ای روشن مدل شوند؛ fill فرضی limit order تضمین‌شده نیست.
- اگر AI callهای تاریخی را replay می‌کنیم، خروجی تصمیم و prompt/model version cache شود تا اجرا قابل‌تکرار باشد و تغییر مدل نتایج را بی‌صدا تغییر ندهد.
- بک‌تست روی چند نماد مجاز و چند بازه زمانی/رژیم انجام شود؛ بهترین پنجره به‌تنهایی کافی نیست.
- اگر data history کافی نیست، مقدار کمبود داده و اثر آن بر اعتبار تست در report ذکر شود.

## 3. Shadow Test

- از همان scanner، AI decision، allocator و risk engine استفاده می‌کند؛ فقط executor شبیه‌سازی‌شده است.
- برای هر سفارش مجازی، timestamp سیگنال، قیمت مرجع، فرضیه ورود/خروج، fee، spread/slippage و علت fill فرضی ثبت شود.
- shadow order را با قیمت لحظه ورود/خروجِ آتی مقایسه کنید؛ از «پرشده فرض‌کردن» خودکار تمام سفارش‌های limit اجتناب شود.
- سناریوهای stale data، timeout مدل و reconnect هم در Shadow رخدادهای لاگ‌شده تولید کنند.
- معیار موفقیت Shadow فقط سود نیست؛ پایداری، تصمیم در زمان مناسب، تعداد candidate، کیفیت ردها، احتمال fill و نبود duplicate intent هم بررسی شود.

## 4. حداقل تست‌های خودکار P0

### Market data & universe

- [ ] نماد denylist هرگز Candidate نمی‌شود.
- [ ] بازار inactive یا غیر Spot رد می‌شود.
- [ ] داده stale/missing مانع ورود جدید می‌شود.
- [ ] tick/step/min notional رعایت می‌شود.

### AI contract

- [ ] JSON نامعتبر یا schema نامعتبر → NO_TRADE.
- [ ] نماد خارج allowlist → reject.
- [ ] پارامتر خارج محدوده → reject، نه clamp خاموش و نامرئی.
- [ ] timeout و rate limit باعث flood retry نمی‌شوند.
- [ ] خروجی AI نمی‌تواند مستقیماً سفارش را ارسال کند.

### Risk & portfolio

- [ ] order sizing با stop distance و risk budget سازگار است.
- [ ] هرگز بیش از max exposure/open positions وارد نمی‌شود.
- [ ] cash reserve حفظ می‌شود.
- [ ] drawdown limit ورود جدید را pause می‌کند.
- [ ] expected edge کمتر از مجموع هزینه‌ها → no trade.
- [ ] یک Candidate در دو چرخه هم‌زمان دو سفارش همسان ایجاد نمی‌کند.

### Execution

- [ ] POST timeout پس از پذیرش سفارش → reconcile، نه duplicate retry.
- [ ] partial fill موقعیت و ریسک را درست تغییر می‌دهد.
- [ ] cancel قبل از order مخالف تأیید می‌شود.
- [ ] restart، open orders و balances را reconcile می‌کند.
- [ ] UNKNOWN order state ورود جدید در همان symbol را متوقف می‌کند تا وضعیت مشخص شود.

### Reporting

- [ ] fee در P&L net کسر می‌شود.
- [ ] سود تحقق‌یافته از unrealized mark-to-market جداست.
- [ ] مبلغ‌ها در currency هدف (تومان) تبدیل یا به‌طور شفاف علامت‌گذاری می‌شوند.
- [ ] گزارش از دیتابیس همان نسخه مجدداً قابل تولید است.

## 5. گزارش نهایی مسابقه

### خلاصه اجرایی

- زمان شروع/پایان، commit hash، model/prompt version، config hash و mode.
- equity شروع، balance پایان و realized net P&L به تومان.
- رتبه سود نهایی تنها اگر رتبه رسمی برگزارکننده در دسترس باشد؛ رتبه را از داده خودمان جعل نکنیم.

### عملکرد

- تعداد کل معاملات بسته‌شده، تعداد برد/باخت و win rate.
- gross realized P&L، fees، net realized P&L، سود/زیان متوسط معامله، expectancy و profit factor.
- حجم معامله (turnover) با توضیح تعریف gross buy+sell؛ از دو بار شمردن مقدارهای پرشده برای معیارهایی که حجم را طور دیگری تعریف می‌کنند اجتناب شود.
- equity curve مبتنی بر ارزش‌گذاری حساب و realized P&L curve به‌صورت جداگانه؛ maximum drawdown باید تعریف روشنی داشته باشد و سود تحقق‌نیافته نباید با realized P&L جمع/اشتباه شود.
- میانگین/میانه مدت نگهداری، مصرف سرمایه، cash reserve و تعداد پوزیشن هم‌زمان.

### کیفیت فنی

- uptime %، scan cycles، latency داده، p50/p95 تصمیم AI، AI timeout/error rate.
- تعداد سفارش‌ها: submitted, filled, partial, cancelled, rejected, unknown.
- fill rate، execution latency، fees و لغزش تخمینی/واقعی در صورت قابل اندازه‌گیری بودن.
- تعداد rejectهای Risk Engine با breakdown علت.
- self-trade / duplicate-order guard events؛ هدف رخداد self-trade واقعی صفر است.
- نمونه تصمیم‌های AI با input evidence IDs و دلایل ورود/خروج.

### بررسی زیان

برای هر زیان مهم، این قالب استفاده شود:

- `trade_id`, symbol، strategy و horizon
- thesis در زمان ورود و invalidation condition
- نتیجه واقعی و خالص از fee
- طبقه علت: `confirmed`, `likely`, `unknown`
- شاهد مورد استفاده، یا علت عدم امکان تشخیص
- اقدام: بدون تغییر، بررسی بیشتر، کاهش وزن استراتژی در آن market/regime، یا آزمایش پارامتر در shadow/backtest

از نسبت‌دادن علت به خبر، نهنگ، manipulation یا هر رویداد بیرونی بدون شواهد قابل اتکا خودداری شود.

## 6. Runbook زمان اجرای پیوسته

- health check منظم؛ اگر feed یا account connection خراب است، ورود جدید متوقف شود.
- پس از restart، اول reconcile، بعد scanner؛ نه برعکس.
- یک process اجرایی فعال باشد.
- لاگ rotate و DB backup شود؛ event loop معامله منتظر گزارش‌گیری نماند.
- Dashboard فقط روی localhost/VPN/private network و پشت auth.
- API Key با حداقل دسترسی، بدون برداشت؛ در لاگ و Git هیچ‌وقت چاپ نشود.
- اگر order state نامشخص ماند، در همان symbol سفارش جدید نفرستید و به انسان هشدار دهید.
