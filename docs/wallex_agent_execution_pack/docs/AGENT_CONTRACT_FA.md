# قرارداد یگانه Agent — Wallex Opportunity Agent

نسخه: 1.0 · وضعیت: مرجع پیاده‌سازی و تست

این فایل **منبع واحد قرارداد تصمیم Agent** است. اگر نمونه‌ای در `SPEC_FA.md`، `MARKET_SCANNING_DECISION_LOGIC_FA.md`، promptها یا کد با این فایل اختلاف داشت، این قرارداد ملاک است و بقیه فایل‌ها باید اصلاح شوند. این قرارداد API والکس را تعریف نمی‌کند؛ قرارداد داخلی محصول است.

## 1. مرز مسئولیت

- LangChain یک Decision Agent را orchestration می‌کند و خروجی ساختاریافته می‌سازد.
- Agent می‌تواند Candidateها را مقایسه کند، استراتژی مجاز و افق نگهداری انتخاب کند، پارامترهای whitelisted را تنظیم کند و تصمیم `NO_TRADE / BUY / HOLD / EXIT` بدهد.
- Agent **هیچ ابزار نوشتنی برای ثبت، لغو یا تغییر سفارش**، هیچ API Key والکس برای معامله و هیچ راهی برای دورزدن Risk Engine ندارد.
- کد قطعی محصول داده را تازه‌سازی می‌کند، مقادیر و روابط را validate می‌کند، حجم مجاز را محاسبه می‌کند، ریسک/قواعد را enforce می‌کند و سفارش را اجرا می‌کند.
- مدل AI حسابداری P&L را انجام نمی‌دهد. سود/زیان واقعی فقط از fillها و feeهای تطبیق‌یافته با داده exchange محاسبه می‌شود.

## 2. واژگان که نباید با یکدیگر اشتباه شوند

| مفهوم | مقادیر/تعریف | معنی |
|---|---|---|
| `candle_timeframe` | `1m`, `5m`, `15m`, `1h` (1h اختیاری) | طول بازه کندلی که از آن ویژگی استخراج می‌شود؛ این مقدار برابر زمان نگهداری معامله نیست. |
| `horizon_profile` | `FAST`, `INTRADAY_SHORT`, `INTRADAY` | پروفایل پیشنهادی مدت معامله؛ به ترتیب حدود 1–5، 5–30 و 30–120 دقیقه. این حدود baseline قابل‌تنظیم‌اند و باید تست شوند. |
| `scan_interval` | baseline برابر 15 ثانیه | فاصله محاسبه دوباره feature/Candidate از cache؛ نه درخواست LLM و نه کندل جدید. |
| `AI review interval` | baseline: فاصله حداقل 30 ثانیه و حداکثر 3 call در دقیقه، هر دو قید با هم | فراخوانی عمیق مدل فقط برای Candidateهای منتخب. فاصله 30ثانیه‌ای ممکن است سقف مؤثر را از سه call/min کمتر کند. |
| `candidate snapshot age` | baseline حداکثر 45 ثانیه | تازگی مجاز داده برای ranking اولیه؛ به معنای مجوز ثبت سفارش نیست. |
| `execution quote age` | baseline حداکثر 5 ثانیه | تازگی quote/orderbook که درست قبل از ثبت سفارش دوباره دریافت و بررسی می‌شود. اگر قابل تأیید نیست، ورود مسدود است. |

**نکته:** همه اعداد بالا تنظیم‌های اولیه‌اند، نه محدودیت اعلام‌شده از طرف Wallex یا مقادیر بهینه اثبات‌شده.

## 3. قرارداد تصمیم `TradeIntent`

نمونه JSON زیر شکل مفهومی قرارداد را نشان می‌دهد. پیاده‌سازی باید قواعد شرطی بخش بعد را اعمال کند؛ صرف داشتن JSON کافی نیست.

```json
{
  "contract_version": "1.0",
  "decision_id": "unique-decision-id",
  "cycle_id": "scanner-cycle-id",
  "symbol": "APPROVED_SYMBOL",
  "action": "BUY",
  "strategy_id": "momentum",
  "horizon_profile": "FAST",
  "confidence": 0.72,
  "reason_code": "SIGNAL_VALID",
  "decision_rationale": "شرح تصمیم مبتنی بر featureهای ورودی",
  "invalidation_condition": "شرط مشخصی که thesis را نامعتبر می‌کند",
  "stop_distance_pct": 0.8,
  "take_profit_distance_pct": 1.2,
  "max_holding_minutes": 5,
  "parameter_overrides": {},
  "evidence_ids": ["snapshot-id", "feature-set-id"]
}
```

### مقادیر مجاز

- `action`: یکی از `NO_TRADE`, `BUY`, `HOLD`, `EXIT`.
- `strategy_id`: یکی از `momentum`, `trend_following`, `mean_reversion` یا `null` در تصمیمی که به استراتژی جدید/ورود اشاره ندارد.
- `horizon_profile`: یکی از `FAST`, `INTRADAY_SHORT`, `INTRADAY` یا `null` وقتی تصمیم به افق جدید مربوط نیست.
- `confidence`: عدد بین 0 و 1؛ این مقدار احتمال کالیبره‌شده موفقیت فرض نمی‌شود و نمی‌تواند هیچ کنترل ریسک را دور بزند.
- `reason_code`: یکی از `EDGE_INSUFFICIENT`, `SIGNAL_VALID`, `SIGNAL_INVALIDATED`, `RISK_CONTEXT`, `DATA_UNCERTAIN`, `OTHER`.
- `parameter_overrides`: فقط کلیدهای ازپیش‌تعریف‌شده و محدوده‌های تنظیم‌شده در config. کلید جدید یا مقدار بیرون محدوده رد می‌شود.
- `evidence_ids`: فقط شناسه‌هایی که واقعاً در context همین تصمیم به Agent داده شده‌اند؛ شناسه یا شواهد ساختگی ممنوع.

## 4. معنای دقیق actionها

- `NO_TRADE`: در این چرخه **ورود جدید ثبت نکن**. دلیل باید ثبت شود. اگر پوزیشن باز وجود دارد، مدیریت مستقل آن همچنان فعال می‌ماند؛ این action به معنای خاموش‌کردن stop نیست.
- `BUY`: پیشنهاد باز کردن پوزیشن خرید Spot جدید در نماد مجاز. Risk Engine اندازه نهایی را محاسبه می‌کند. در نسخه MVP، روی نمادی که پوزیشن یا سفارش ورود unresolved دارد، ورود جدید رد شود؛ افزودن به پوزیشن موجود/averaging-down تا زمانی که جداگانه تست و فعال نشده ممنوع است.
- `HOLD`: پوزیشن موجود حفظ می‌شود و در همین تصمیم سفارش جدیدی ارسال نمی‌شود. Stop سخت، سقف زمان نگهداری و kill switch همچنان فعال‌اند.
- `EXIT`: پیشنهاد بستن **کل مقدار باقی‌مانده پوزیشن Spot متعلق به همین Agent**. در MVP خروج جزئی پشتیبانی نمی‌شود؛ اگر بعداً لازم شد باید فیلد/قرارداد نسخه‌دار و تست‌های مستقل اضافه شود. مقدار قابل فروش فقط از ledger پوزیشن و fillهای واقعی محاسبه می‌شود. هیچ فروش بدون موجودی و هیچ short-selling مجاز نیست.

`HOLD` و `NO_TRADE` مترادف نیستند: اولی وضعیت پوزیشن موجود را توصیف می‌کند؛ دومی صرفاً عدم ورود جدید در چرخه را.

### حداقل فیلدهای لازم بر اساس action

| فیلد | `NO_TRADE` | `BUY` | `HOLD` | `EXIT` |
|---|---|---|---|---|
| `symbol`, `action`, `decision_id`, `cycle_id`, `contract_version` | لازم | لازم | لازم | لازم |
| `decision_rationale`, `reason_code`, `evidence_ids` | لازم | لازم | لازم | لازم |
| `strategy_id`, `horizon_profile` | می‌تواند null باشد | لازم و مجاز | از پوزیشن/تصمیم جاری یا null با توضیح | از پوزیشن/تصمیم جاری یا null با توضیح |
| `stop_distance_pct` | null | مثبت و محدود به config | مدیریت stop از policy قطعی، نه از LLM | null؛ خروج بر اساس پوزیشن واقعی |
| `take_profit_distance_pct` | null | اختیاری؛ اگر حاضر، مثبت/محدود | null یا مطابق قرارداد پوزیشن | null |
| `max_holding_minutes` | null | عدد مثبت در محدوده پروفایل | از policy/پوزیشن موجود | null یا زمان باقیمانده مستند |
| `invalidation_condition` | null یا متن دلیل عدم ورود | لازم | اختیاری/شرط بازبینی | متن دلیل خروج یا null |

این ماتریس قرارداد معنایی است؛ قرارداد provider-side را در JSON Schema/TypedDict به شکل سازگار پیاده کنید و سپس همان شروط را در Validator اجرا کنید. `decision_rationale` برای همه actionها اجباری است و باید دلیل `NO_TRADE` را هم توضیح دهد.

## 5. صف بازبینی پوزیشن و Candidate

مدیریت پوزیشن موجود نباید قربانی شلوغی صف ورودهای جدید شود:

- کنترل stop، max holding time، drawdown و kill switch قطعی و مستقل از LLM در تمام زمان اجرا فعال می‌ماند.
- در صف بازبینی AI، ابتدا پوزیشن‌هایی اولویت می‌گیرند که به invalidation، سقف زمان نگهداری یا شرط مدیریت ریسک نزدیک‌اند؛ سپس Candidateهای جدید بررسی می‌شوند.
- بودجه فراخوانی AI بین بازبینی پوزیشن و فرصت ورود مشترک است. اگر بودجه تمام شد یا مدل timeout کرد، ورودی جدید متوقف می‌شود؛ کنترل‌های سخت و policy قطعی پوزیشن همچنان فعال می‌مانند.
- وقتی AI برای پوزیشن باز فراخوانی می‌شود، snapshot قیمت/ویژگی و وضعیت پوزیشن همان نماد به context داده می‌شود. هر تصمیم `HOLD` یا `EXIT` باید به پوزیشن شناخته‌شده همان نماد مربوط باشد.
- برای جلوگیری از ambiguity در MVP، حداکثر یک پوزیشن Agent-owned به‌ازای هر نماد وجود دارد و تا زمان بسته‌شدن/تطبیق پوزیشن، ورود یا averaging-down جدید روی همان نماد ممنوع است.

## 6. قواعد شرطی و Validator

Validator زمان اجرا باید دست‌کم این موارد را بررسی کند:

1. نسخه قرارداد شناخته‌شده و تمام فیلدهای ضروری حاضر باشند.
2. نوع داده و enumها، مقادیر عددی، بازه confidence، حدود stop/target/time و کلیدهای parameter override معتبر باشند.
3. `symbol` در market allowlist فعال/Spot باشد و در denylist ممنوع نباشد.
4. `evidence_ids` از شواهد موجود در context همان decision باشند.
5. `BUY` فقط با داده جدید، quote تازه، هزینه معامله معتبر، حساب reconcileشده، بازار مجاز و شرایط risk pass قابل ادامه است.
6. `HOLD` یا `EXIT` باید به پوزیشن شناخته‌شده/سفارش‌های همان نماد مربوط باشند؛ خروجی مدل حق ندارد موجودی را جعل کند.
7. برای `BUY`، `strategy_id`, `horizon_profile`, `decision_rationale` و stop policy لازم‌اند؛ `decision_rationale` باید thesis ورود، شواهد و دلیل انتخاب را توضیح دهد و فیلد جداگانه‌ای به نام `thesis` در قرارداد نسخه 1.0 وجود ندارد. `stop_distance_pct` مثبت و در محدوده config الزامی است؛ `take_profit_distance_pct` در صورت ارائه باید مثبت و در محدوده مجاز باشد. زمان خروج/stop باید توسط policy قطعی اجرا شود، نه فقط یادداشت در خروجی LLM. فیلدهای لازم برای `NO_TRADE` می‌توانند `null` باشند.
8. داده کهنه، snapshot تغییرکرده، timeout، پاسخ نامعتبر یا mismatch حساب باعث عدم ورود جدید می‌شود. اگر پوزیشن باز است، خروج سخت و reconciliation با قواعد مستقل ادامه دارد.
9. خروجی Agent هرگز شامل qty/order payload نهایی قابل‌ارسال به exchange نیست؛ quantity/price/order type توسط لایه قطعی محاسبه و validate می‌شود.
10. تصمیم raw/normalized، خطاها و ردها با timestamp UTC ذخیره می‌شوند؛ Secret یا داده حساس در context/log قرار نمی‌گیرد.

## 7. چرا `TypedDict`/JSON Schema و نه مدل Pydantic پروژه؟

- پیاده‌سازی پروژه از LangChain structured output با `TypedDict` به‌عنوان مسیر پیش‌فرض یا JSON Schema استفاده می‌کند؛ مدل‌های Pydantic در کد دامنه تعریف نمی‌شوند.
- `TypedDict` در Python به‌تنهایی runtime validation نیست؛ JSON Schema هم باید از مسیر مناسب LangChain/provider ارسال شود. علاوه بر آن، Validator مستقل برای قواعد معنایی/ریسک حتماً لازم است.
- ممکن است LangChain، integration مدل، یا FastAPI یک dependency غیرمستقیم Pydantic نصب کند. الزام این پروژه حذف اجباری dependency ترانزیتی نیست؛ الزام این است که مدل‌های اصلی و منطق اعتبارسنجی دامنه به مدل‌های Pydantic مستقیم وابسته نباشند.
- نسخه‌های LangChain/provider باید lock و smoke-test شوند؛ structured output واقعی و محل دریافت `structured_response` براساس نسخه نصب‌شده verify شود.

## 8. آزمون‌های قرارداد

- [ ] هر چهار action از نظر معنا و شروط ورودی تست شوند.
- [ ] action ناشناخته، نماد ممنوع، evidence ساختگی، confidence خارج بازه و parameter override ناشناخته رد شود.
- [ ] `BUY` با snapshot کهنه، quote کهنه، open order unresolved یا پوزیشن موجود در همان نماد رد شود.
- [ ] `EXIT` بدون پوزیشن/موجودی واقعی قابل‌فروش رد شود؛ در MVP فقط کل پوزیشن بسته می‌شود و خروج جزئی پشتیبانی نشده است.
- [ ] بازبینی پوزیشن‌های باز در صف AI مشخص، اولویت‌دار و جدا از کنترل‌های قطعی stop تست شود؛ خالی‌شدن بودجه AI نباید stop سخت را غیرفعال کند.
- [ ] timeout/invalid output باعث order نشود؛ stop سخت پوزیشن موجود همچنان عمل کند.
- [ ] سازوکار اجرای stop (exchange-side conditional order در صورت پشتیبانی، یا local watchdog تست‌شده) روشن و در preflight تأیید شده باشد؛ فرض نکنید stop در صرافی قرار داده شده مگر پاسخ API آن را تأیید کند.
- [ ] یک خروجی معتبر با input ثابت، پس از normalization و validation، در Backtest/Shadow/Live contract مشترک مصرف شود.
