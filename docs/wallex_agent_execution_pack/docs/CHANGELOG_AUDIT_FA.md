# گزارش بازبینی جامع و تغییرات بسته

نسخه: 1.2-source-recovered · تاریخ: 2026-10-22

## 1. حفظ فایل‌های قبلی

هیچ مسیر از نسخه قبلی بسته حذف نشده است؛ snapshot دقیق نسخه قبلی نیز در پوشه `archive/` داخل بسته حفظ شده است. اسناد جاری در مسیرهای اصلی به‌روز شده‌اند تا دیگر به نبود فایل‌های منبع اشاره نکنند.

## 2. منابعی که در این دور اضافه و دقیقاً حفظ شدند

- `source_materials/originals/assets.md`
- `source_materials/originals/intro-text.md`
- `source_materials/originals/task.md`
- `source_materials/originals/هکاتون استارکوچ _ والکس.pdf`

افزون بر نسخه‌های اصلی:
- `source_materials/derived/inactive_markets.json` و `.csv` از `assets.md` استخراج شدند؛ ۳۴۵ جفت بازار، ۳۴۵ مورد یکتا، صفر تکراری.
- `source_materials/derived/SOURCE_SHA256.txt` برای اثبات یکسانی بایت‌ها ایجاد شد.
- `docs/SOURCE_REVIEW_FA.md` مرور صفحه‌به‌صفحه/فایل‌به‌فایل منبع و تعارض‌های واقعی را ثبت می‌کند.

## 3. موارد فنی/محصولی حفظ‌شده و هم‌راستا

- تاریخچه Grill-me و تصمیم‌های قطعی کاربر حفظ شد.
- قرارداد Agent مرجع واحد actionها، horizon و structured output باقی است.
- LangChain orchestration Agent؛ TypedDict/JSON Schema + Validator Python؛ بدون Pydantic model مستقیم در کد دامنه.
- cadence اسکن، timeframe کندل و AI review interval از هم جدا هستند.
- Live default-off و fail-closed، reconcile سفارش نامعلوم، محافظت از duplicate/self-trade و دروازه ریسک لازم است.
- Backtest/Shadow/Live جدا می‌مانند؛ realized P&L، equity/unrealized P&L و drawdown جدا گزارش می‌شوند.

## 4. یافته‌های مهم از PDF و task.md

- PDF حساب را «۰ تومان دارایی ورودی + ۵,۰۰۰,۰۰۰ تومان اعتبار برای ۳ روز» معرفی می‌کند.
- قابلیت API برای حساب اعتباری در جدول PDF فعال دیده می‌شود؛ قابلیت بومی بات معامله‌گر و معامله تعهدی برای حساب اعتباری فعال نشان داده نشده است.
- PDF ریسک liquidation را جدی توصیف می‌کند: در صورت لیکوییدشدن، هیچ دارایی یا مبلغی بازنمی‌گردد.
- رایگان بودن بازپرداخت اعتبار سه‌روزه در بنر و مثال عمومی کارمزد روزانه در متن PDF کنار هم هستند؛ هزینه دقیق این طرح باید از UI/برگزارکننده تأیید شود.
- task.md به‌طور هم‌زمان از equity نهایی/unrealized P&L و الزام realized Toman و باقی‌نماندن کوین در پایان می‌گوید؛ گزارش و منطق خروج این موارد را جدا نگه می‌دارند و deadline رسمی باید تأیید شود.

## 5. اعتبارسنجی نهایی

مقادیر شمارش، integrity آرشیو، SHA-256 و تعداد مسیرهای محفوظ بعد از بسته‌بندی در `docs/PACKAGE_AUDIT_FA.md` و `MANIFEST_SHA256.txt` ثبت می‌شوند. وجود snapshot قدیمی برای تاریخچه است و نباید به‌جای اسناد جاری استفاده شود.
