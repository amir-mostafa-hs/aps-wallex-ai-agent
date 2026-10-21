# Wallex API Notes — تکمیل در Spike فنی

وضعیت: قالب آماده؛ **قبل از Live باید با API رسمی فعلی پر و تأیید شود.** از endpointهایی که فقط در blog یا نمونه قدیمی دیده شده‌اند استفاده نکنید مگر در docs فعلی تأیید شوند.

منبع اصلی: https://developers.wallex.ir/docs
صفحه کلی: https://developers.wallex.ir/

## Endpoint inventory

| Capability | Endpoint / method | Auth | Confirmed? | Sample response fixture | Rate limit / notes |
|---|---|---|---|---|---|
| List all markets | TODO | public/private? | NO | TODO | TODO |
| Spot market metadata | TODO | TODO | NO | TODO | active, min qty/notional, tick/step |
| Ticker / orderbook | TODO | TODO | NO | TODO | TODO |
| OHLCV/history | TODO | TODO | NO | TODO | history depth / pagination |
| Account balance / available amount | TODO | private | NO | sanitized fixture | verify credit account scope |
| Open orders | TODO | private | NO | sanitized fixture | TODO |
| Create Spot order | TODO | private | NO | sanitized fixture | client ID and retry semantics |
| Order detail by client ID | TODO | private | NO | sanitized fixture | must work for reconciliation |
| Cancel order | TODO | private | NO | sanitized fixture | cancellation race semantics |
| Recent user trades/fills | TODO | private | NO | sanitized fixture | fee asset + timestamps |
| WebSocket stream | TODO | depends | NO | sanitized fixture | subscribe/reconnect/heartbeat |

## Required evidence

For each endpoint capture a sanitized request, sanitized response, API docs URL, timestamp of verification and a test name. Never store API Key, account identifiers or real personal data in fixture files.

## Preflight checklist

- [ ] API Key reads the intended credit account; available balance aligns with the competition start capital.
- [ ] Market symbols and Spot-enabled flags align with current API.
- [ ] `assets.md` denylist is extracted, code-reviewed and applied.
- [ ] Price precision, quantity precision, step size and minimum notional verified per symbol.
- [ ] Create order schema and permitted order types verified.
- [ ] `client_id` support and query-by-client-ID semantics verified.
- [ ] Unknown POST outcome can be reconciled before retry.
- [ ] Cancel response does not falsely imply no fill; post-cancel fills are reconciled.
- [ ] Fee field and currency conversion to Toman verified.
- [ ] Endpoint rate limits and WebSocket retry/reconnect policy documented.
- [ ] روش اجرای stop-loss برای Spot account تأیید شده (سفارش شرطی exchange-side در صورت پشتیبانی یا watchdog محلی دارای تست) و recovery آن مستند شده است.
- [ ] Historical candle depth is sufficient for the claimed backtest period.


## نتیجه جستجوی مستندات عمومی اولیه (باید در Spike دوباره verify شود)

- صفحه رسمی اصلی: https://developers.wallex.ir/docs
- صفحه عمومی API: https://developers.wallex.ir/ — در مثال بازارها، یک پاسخ/درخواست تجمیعی بازار از مسیر `GET https://api.wallex.ir/hector/web/v1/markets` نشان داده می‌شود. پیش از استفاده، schema و نرخ محدودیت را از docs فعلی تأیید کنید.
- WebSocket: https://developers.wallex.ir/socket — مستندات عمومی WebSocket، داده real-time و کانال‌های بازار مانند trades/depth را معرفی می‌کند. صفحه معاملات انجام‌شده: https://developers.wallex.ir/socket/trade و نمونه subscription با `MARKET@trade` و آدرس `wss://api.wallex.ir/ws` را نشان می‌دهد. اتصال حداکثر حدود ۳۰ دقیقه معرفی شده و heartbeat/reconnect باید پیاده‌سازی شود؛ محدودیت‌ها را دوباره در مستند فعال بررسی کنید.
- Candle history reference قدیمی‌تر: https://api-docs.wallex.ir/ مسیر `GET https://api.wallex.ir/v1/udf/history` با پارامترهای `symbol`, `resolution`, `from`, `to` را معرفی می‌کند و resolutionهای `1`, `60`, `180`, `360`, `720`, `1D` را فهرست کرده است. این دامنه/مستند را منبع قطعی فعلی فرض نکنید؛ endpoint تاریخچه باید در docs جاری یا با پاسخ موفق API تأیید شود.
- Spot order create reference: https://developers.wallex.ir/spot/createorder — مسیر نشان‌داده‌شده `POST /v1/account/orders` است؛ فقط پس از تطبیق با بخش جاری مستند و حساب اعتباری استفاده کنید.

**نکته:** داده کندل معمولاً به‌صورت OHLCV عددی به دست می‌آید؛ تصویر چارت را لازم نداریم. اگر فقط کندل ۱ دقیقه‌ای تأیید شد، تایم‌فریم‌های ۵/۱۵ دقیقه‌ای با aggregation محلی ساخته شوند. تمام cadenceهای درج‌شده در `MARKET_SCANNING_DECISION_LOGIC_FA.md` پیشنهادهای آغازین هستند و نباید بدون سنجش نرخ درخواست/تأخیر به عنوان سقف یا مقدار بهینه فرض شوند.


## تصمیم MCP در MVP

- مسیر اصلی اجرا و تطبیق سفارش در MVP، API مستقیم والکس از طریق `WallexAdapter` است تا timeout، retry، شناسه سفارش و پاسخ‌های اجرا مستقیماً کنترل/تست شوند.
- MCP می‌تواند بعداً برای اتصال استاندارد Agent به ابزارهای فقط‌خواندنی ارزیابی شود؛ در MVP به Agent ابزار ارسال/لغو سفارش نمی‌دهیم.
- در مستند MCP درباره تأیید قبل از عملیات حساس توضیحاتی وجود دارد؛ تا وقتی رفتار واقعی و محدودیت‌های آن برای اجرای خودکار روشن/آزمایش نشده، MCP را جایگزین قطعی execution adapter فرض نکنید.

## وضعیت منبع و زمان تأیید

- صفحه اصلی رسمی API در بازبینی اسناد در تاریخ 2026-10-22 قابل دسترسی بود: https://developers.wallex.ir/docs؛ این صفحه بخش‌های Spot، اعتبار معاملاتی و WebSocket را فهرست می‌کند.
- بازشدن صفحه مستندات به معنی تأیید همه endpointها، permissionها یا rate limitها نیست. هر ردیف جدول بالا تا ثبت response fixture و تست، `Confirmed=NO` می‌ماند.
