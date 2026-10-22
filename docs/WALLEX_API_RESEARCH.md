# مستند پژوهش فنی رسمی API والکس (Wallex Official API Technical Research)

- **تاریخ پژوهش:** ۲۲ اکتبر ۲۰۲۶ (بروزرسانی زنده بر اساس API والکس و پرتال مستندات رسمی)
- **منابع اصلی استناد:**
  - مستندات رسمی توسعه‌دهندگان والکس: [https://developers.wallex.ir/docs](https://developers.wallex.ir/docs)
  - فایل Swagger سرویس‌های پایه: `https://developers.wallex.ir/assets/files/basic-services-89626420b5f06e4d7a2dc9206cdeb192.json`
  - فایل Swagger معاملات اسپات: `https://developers.wallex.ir/assets/files/spot-b9d06896d1009adc9ebc69b9a5495e7e.json`
  - مستند و مشخصات OpenAPI حساب اعتباری (Trade Credit / Prop): `https://developers.wallex.ir/assets/files/trade-credit-ff5c60b5b97b77a5b2c2e4800f07729c.yaml`
  - لندینگ و مشخصات MCP والکس: [https://wallex.ir/landing/mcp/](https://wallex.ir/landing/mcp/)
  - فایل کانتکست هوش مصنوعی والکس: `https://api.wallex.ir/llm.txt`
  - اعتبارسنجی زنده Endpointهای عمومی بر روی دامنه `https://api.wallex.ir`

---

## ۱. احراز هویت و اثبات دسترسی API Key به حساب اعتباری هکاتون

### مستندات رسمی و سازوکار کلید
- **دامنه پایه API:** `https://api.wallex.ir`
- **هدر احراز هویت عمومی:** `X-API-Key: <YOUR_API_KEY>` ([مستند ساخت API Key](https://developers.wallex.ir/docs/create-api-key))
- **هدر اختصاصی حساب اعتباری:** بر اساس مستندات رسمی Trade Credit والکس ([مشاهده در فایل OpenAPI Swagger اعتباری](https://developers.wallex.ir/assets/files/trade-credit-ff5c60b5b97b77a5b2c2e4800f07729c.yaml))، کلیه درخواست‌های مرتبط با پکیج اعتباری و معاملات زیرحساب اعتباری علاوه بر `X-API-Key` نیازمند هدر زیر هستند:
  ```http
  sub-account-client-id: <SubAccountClientId>
  ```
- **نوع API Key:** کلیدهای API والکس به دو دسته دسترسی دارند:
  1. `READ` (مشاهده موجودی، سوابق، سفارش‌ها)
  2. `TRADE` (ثبت و لغو سفارش‌ها)
  > [!IMPORTANT]
  > برای حساب اعتباری، کاربر باید از داخل داشبورد حساب اعتباری (یا زیرحساب فعال پکیج) اقدام به ایجاد API Key با دسترسی `TRADE` نموده باشد. کلید حساب اصلی شخصی امکان معامله مستقیم روی اعتبار پکیج هکاتون را ندارد مگر آنکه زیرحساب اعتباری متصل باشد.

### Endpointهای تایید هویت و اعتبارسنجی پکیج هکاتون
1. **بررسی پکیج‌های کاربر و دریافت `subAccountClientId`:**
   - **Endpoint:** `GET /v1/prop/user/packages/overview`
   - **هدرها:** `X-API-Key: <KEY>`
   - **پاسخ مورد انتظار:** بازگرداندن آرایه‌ای از پکیج‌های کاربر شامل `packageId`، `subAccountClientId`، وضعیت پکیج (`status`).
2. **بررسی جزئیات پکیج فعال اعتباری:**
   - **Endpoint:** `GET /v1/prop/user/packages/active`
   - **هدرها:** `X-API-Key: <KEY>`, `sub-account-client-id: <SubAccountClientId>`
   - **فیلدهای دریافتی:** `loan`, `status`, `expireAt`, `warningLimit`, `liquidityLimit`.

---

## ۲. دریافت بازارهای فعال Spot و روش دقیق ترکیب با Denylist

### دریافت بازارهای فعال صرافی
- **Endpoint رسمی:** `GET /hector/web/v1/markets` ([Wallex MCP / Developers Doc](https://wallex.ir/landing/mcp/))
- **ویژگی‌های خروجی:** بازگرداندن آرایه‌ای شامل ۴۶۹ بازار در کل صرافی که ۳۷۳ مورد از آن‌ها بازار اسپات فعال هستند (`is_spot: true`).
- **فیلدهای کلیدی هر بازار:**
  - `symbol`: نماد بازار بدون اسلش (مانند `BTCTMN`, `USDT_TMN`, `ETHUSDT`)
  - `is_spot`: بولین، مشخص‌کننده بازار معاملاتی Spot
  - `is_tmn_based`: معامله بر پایه تومان
  - `is_usdt_based`: معامله بر پایه تتر
  - `amount_precision`: تعداد اعشار مجاز برای حجم سفارش (Step Size)
  - `price_precision`: تعداد اعشار مجاز برای قیمت سفارش (Tick Size)

### جزئیات پکیج هکاتون (Package ID: 183)
از طریق استعلام مستقیم از سرور والکس (`GET https://api.wallex.ir/v1/prop/packages/183`):
- **نام پکیج:** `هکاتون استارکوچ | والکس`
- **وام تخصیص‌یافته:** ۵,۰۰۰,۰۰۰ تومان (`loan: "5000000"`)
- **تعداد روز اعتبار:** ۳ روز (`expire_days: 3`)
- **کارمزد روزانه:** ۰ تومان (`daily_fee: "0"`)
- **حد هشدار (Warning Limit):** ۱,۰۰۰ تومان ارزش کل دارایی (`warning_limit: "1000"`)
- **حد لیکویید (Liquidity Limit):** ۹۰۰ تومان ارزش کل دارایی (`liquidity_limit: "900"`)
- **فیلد `unavailableMarkets`:** شامل **۳۵۷ نماد معاملاتی غیرفعال** برای این پکیج است.

### مقایسه Denylist محلی و Denylist زنده سرور
1. **فایل محلی (`docs/sources/inactive_markets.json`):**
   - شامل **۳۴۵ جفت‌ارز** با فرمت اسلش‌دار (مانند `"A/TMN"`, `"1INCH/TMN"`).
2. **لیست زنده پکیج ۱۸۳ والکس (`unavailableMarkets`):**
   - شامل **۳۵۷ جفت‌ارز** با فرمت بدون اسلش (مانند `"ATMN"`, `"1INCHTMN"`).
   - **تطبیق کامل:** تمام ۳۴۵ نماد فایل محلی، پس از حذف کاراکتر `/` در لیست ۳۵۷ نماد سرور حضور دارند.
   - **۱۲ نماد جدید مسدودشده در پکیج ۱۸۳:**
     `IPTMN`, `OMTMN`, `BALTMN`, `DAITMN`, `IPUSDT`, `OMUSDT`, `BALUSDT`, `CATSTMN`, `DAIUSDT`, `RDNTTMN`, `CATSUSDT`, `RDNTUSDT`.

### روش پیاده‌سازی ترکیب و Allowlist نهایی
برای تضمین ایمنی حداکثری و رعایت قانون Fail-Closed:
```python
def build_allowlist(all_markets: list[dict], package_unavailable: list[str], local_denylist: list[str]) -> list[dict]:
    # 1. نرمال‌سازی Denylist محلی با حذف اسلش
    normalized_local = {s.replace("/", "").strip().upper() for s in local_denylist}
    # 2. ادغام مجموعه ممنوعه زنده و محلی (Union)
    full_denylist = set(package_unavailable).union(normalized_local)
    
    # 3. فیلتر کردن بازارهای Spot مجاز
    allowed = []
    for m in all_markets:
        sym = m["symbol"].upper()
        if m.get("is_spot") is True and sym not in full_denylist:
            allowed.append(m)
    return allowed
```
- **نتیجه حاصله روی داده زنده والکس:**
  - مجموع بازارهای Spot: ۳۷۳ جفت‌ارز.
  - بازارهای مجاز نهایی (Tradeable Allowlist): **۱۲۰ بازار فعال** (۶۲ جفت‌ارز پایه تومان و ۵۸ جفت‌ارز پایه تتر).

---

## ۳. Endpoint و Schema داده‌های تاریخی، قیمت و دفتر سفارش

### ۱. کندل‌های قیمتی تاریخی (OHLCV)
- **Endpoint رسمی:** `GET /v1/udf/history` ([TradingView UDF Compatible](https://developers.wallex.ir/docs/spot-types))
- **پارامترهای Query:**
  - `symbol`: نماد بازار (مانند `BTCTMN` یا `USDT_TMN`)
  - `resolution`: گام زمانی. مقادیر تست‌شده و معتبر: `1` (۱ دقیقه)، `15` (۱۵ دقیقه)، `60` (۱ ساعت)، `1D` (۱ روزه).
  - `from`: تایم‌استمپ یونیکس به ثانیه برای نقطه شروع
  - `to`: تایم‌استمپ یونیکس به ثانیه برای نقطه پایان
- **Schema پاسخ تاییدشده (Live Verified):**
  ```json
  {
    "s": "ok",
    "t": [1729562400, 1729566000],
    "o": ["4238500000", "4241000000"],
    "h": ["4250000000", "4249000000"],
    "l": ["4235000000", "4239000000"],
    "c": ["4241000000", "4245000000"],
    "v": ["1.245", "0.892"]
  }
  ```
  *(در صورت عدم وجود دیتا در بازه، `"s": "no_data"` برمی‌گردد).*

### ۲. دفتر سفارش لحظه‌ای (Order Book Depth)
- **Endpoint رسمی:** `GET /v1/depth?symbol={symbol}` ([Market Depth Doc](https://developers.wallex.ir/docs/basic-services))
- **Schema پاسخ تاییدشده (Live Verified):**
  ```json
  {
    "result": {
      "ask": [
        { "price": "4250000000", "quantity": "0.12" }
      ],
      "bid": [
        { "price": "4249000000", "quantity": "0.45" }
      ]
    },
    "success": true
  }
  ```
  *تعداد سفارش‌ها در هر سمت حداکثر ۵۰ سطر عمق دفتر سفارش را تشکیل می‌دهد.*

### ۳. آخرین معاملات بازار (Recent Public Trades)
- **Endpoint رسمی:** `GET /v1/trades?symbol={symbol}`
- **خروجی:** آرایه‌ای از معاملات اخیر شامل `price`، `quantity`، `isBuyerMaker`، `timestamp`.

---

## ۴. وب‌سوکت (WebSocket)، کانال‌ها، رویدادها و محدودیت‌ها

### معماری پروتکل
- **فناوری:** پروتکل [Centrifugo v2](https://developers.wallex.ir/docs/socket-intro)
- **کلاینت رسمی سازگار در پایتون:** `centrifuge-python`
- **URL اتصال:**
  ```text
  wss://api.wallex.ir/connection/websocket
  ```
  *(هشدار: انتهای آدرس نباید کاراکتر `/` اضافه قرار گیرد).*

### کانال‌های عمومی و ساختار آن‌ها
| نوع داده | الگوی کانال (Channel Pattern) | توضیحات و ماندگاری داده |
| :--- | :--- | :--- |
| آخرین معاملات بازار | `public:<SYMBOL>@trade` | گزارش آنی هر معامله انجام‌شده |
| قیمت‌های زنده همه بازارها | `public:all@price` | بروزرسانی قیمت و درصد تغییر ۲۴ ساعته |
| عمق خرید دفتر سفارش | `orderbook:<SYMBOL>@buyDepth` | ارسال تغییرات سطح خرید |
| عمق فروش دفتر سفارش | `orderbook:<SYMBOL>@sellDepth` | ارسال تغییرات سطح فروش |
| کندل‌های قیمتی | `candle:<SYMBOL>@<INTERVAL>` | بازه‌های مجاز: `1m`, `1h`, `1d`. **تنها کانالی که ۱۰ پیام آخر را تا ۲ دقیقه ذخیره نگه می‌دارد.** |
| رویدادهای کاربر (سفارش و دارایی) | `private:user#<userId>` | نیازمند لاگین یا Connection Token اختصاصی |

### محدودیت‌ها و ملاحظات شبکه (Socket Limits & Heartbeat)
1. **سقف کانال‌ها:** حداکثر ۶۴ کانال اشتراک (Subscription) به ازای هر اتصال وب‌سوکت.
2. **مکانیزم Keep-Alive:** سرور هر ۲۵ ثانیه پیام Ping ارسال می‌کند و کلاینت باید حداکثر ظرف ۸ ثانیه پاسخ Pong دهد؛ در غیر این صورت اتصال قطع می‌شود.
3. **نبود Snapshot در کانال‌های Depth:** در زمان عضویت اولیه در کانال‌های `orderbook`، اسنپ‌شات کامل ارسال نمی‌شود؛ بنابراین عامل نرم‌افزاری باید ابتدا از REST API مقدار `/v1/depth` را دریافت کند و سپس تغییرات دلتا را از طریق سوکت اعمال نماید.

---

## ۵. ایجاد، مشاهده، لغو و چرخه حیات سفارشات اسپات

### ۱. ثبت سفارش جدید (Create Spot Order)
- **Endpoint:** `POST /v1/account/orders` ([Spot Create Order Doc](https://developers.wallex.ir/docs/spot-create-order))
- **هدرها:**
  - `X-API-Key: <TRADE_KEY>`
  - `sub-account-client-id: <SUB_ACCOUNT_ID>` (در صورت استفاده از اعتبار پکیج)
  - `Content-Type: application/json`
- **بدنه درخواست (JSON Schema):**
  ```json
  {
    "symbol": "BTCTMN",
    "side": "BUY",
    "type": "LIMIT",
    "price": "4250000000",
    "quantity": "0.001",
    "client_id": "agent-unique-uuid-12345"
  }
  ```
  *فیلد `client_id` شناسه منحصربه‌فرد تولیدشده توسط ربات برای جلوگیری از سفارش تکراری (Idempotency) است.*

### ۲. استعلام وضعیت سفارش (Get Order Detail)
- **Endpoint:** `GET /v1/account/orders/{client_id}` یا `GET /v1/account/orders/{order_id}`
- **پاسخ تفصیلی وضعیت سفارش:**
  ```json
  {
    "result": {
      "id": 9876543,
      "clientId": "agent-unique-uuid-12345",
      "symbol": "BTCTMN",
      "side": "BUY",
      "type": "LIMIT",
      "price": "4250000000",
      "quantity": "0.001",
      "status": "PARTIALLY_FILLED",
      "executedPercent": 50.0,
      "executedQty": "0.0005",
      "executedPrice": "4250000000",
      "executedSum": "2125000",
      "fee": "2125",
      "fills": [
        {
          "price": "4250000000",
          "quantity": "0.0005",
          "sum": "2125000",
          "fee": "2125",
          "feeAsset": "BTC",
          "isBuyer": true,
          "timestamp": "2026-10-22T02:15:30Z"
        }
      ]
    },
    "success": true
  }
  ```

### ۳. لغو سفارش (Cancel Order)
- **Endpoint:** `DELETE /v1/account/orders/{client_id}` یا با بدنه JSON شامل `{"clientOrderId": "..."}`.
- **خروجی:** بازگرداندن وضعیت سفارش لغوشده و آزادسازی مانده قفل‌شده در دفتر سفارش.

### ۴. قوانین محافظت از اسلیپیج و انقضا (Safety & Slippage Safeguards)
- **محدودیت نرخ ثبت سفارش:** بر اساس مستند رسمی والکس، حداکثر **۲۰ درخواست ثبت سفارش در هر ۱۰ ثانیه** برای هر کلید مجاز است.
- **محافظت از سفارشات Market:** والکس به‌صورت سیستمی سفارش مارکت را در صورتی که حجم آن از عمق سفارشات بالاتر رود یا اثر قیمتی (Price Impact) آن بیش از **۲٪** باشد، لغو می‌کند تا از اسلیپیج فاحش جلوگیری کند.
- **رفتار در زمان Timeout:** هرگز نباید در مواجهه با خطای شبکه یا HTTP 504 بلافاصله سفارش جدید ثبت شود. ابتدا باید از طریق `GET /v1/account/orders/{client_id}` وضعیت سفارش تطبیق (Reconcile) گردد.

---

## ۶. حداقل ارزش سفارش، دقت‌ها (Precision) و کارمزد

### ۱. تعداد اعشار مجاز (Step Size & Tick Size)
- از طریق فراخوانی `GET /hector/web/v1/markets` فیلدهای زیر به ازای هر نماد مشخص است:
  - `price_precision`: تعداد ارقام اعشار مجاز برای قیمت (برای مثال در بازارهای تومانی معمولاً ۰ یا ۲، و در بازارهای کم‌ارزش تا ۸ رقم اعشار).
  - `amount_precision`: تعداد ارقام اعشار مجاز برای حجم سفارش (مثلاً BTC برابر با ۶ یا ۸ اعشار، و شیبا اینو ۰ اعشار).
  - **قانون الزامی ربات:** گرد کردن حجم و قیمت پیش از ارسال سفارش با استفاده از فرمول:
    ```python
    def quantize(value: float, precision: int) -> str:
        return f"{value:.{precision}f}"
    ```

### ۲. استعلام کارمزد حساب (Account Fee Rates)
- **Endpoint رسمی:** `GET /v1/account/fee` ([Wallex Fee Doc](https://developers.wallex.ir/docs/basic-services))
- **پاسخ:** بازگرداندن مقادیر `makerFeeRate` و `takerFeeRate` بر اساس سطح کاربری.
- در حساب‌های عادی والکس، کارمزد پایه معمولاً بین ۰.۲٪ تا ۰.۲۵٪ است که در محاسبات سود ناخالص به خالص در استراتژی و موتور ریسک لحاظ خواهد شد.

### ۳. حداقل ارزش سفارش (Minimum Notional)
- **وضعیت:** `UNVERIFIED (نیازمند استعلام در Preflight)`
- در مستندات عمومی والکس، عدد ثابت سراسری قید نشده است؛ اما در پلتفرم وب والکس حداقل ارزش سفارش در بازارهای تومانی برابر با **۱۰۰,۰۰۰ تومان** و در بازارهای تتری برابر با **۱۰ تتر** است. این مقدار در پیش‌پرواز اتصال با یک استعلام اعتبارسنجی خواهد شد.

---

## ۷. مشخصات حساب اعتباری، لیکوییدیشن و محدودیت‌های پکیج هکاتون

از استخراج مستقیم اطلاعات پکیج هکاتون استارکوچ (`package_id: 183`) نتایج زیر قطعی گردید:
1. **مبلغ وام دریافتی:** ۵,۰۰۰,۰۰۰ تومان موجودی نقد اعتباری.
2. **تضمین اولیه (Collateral):** ۰ تومان (`assurance: "0"`).
3. **مدت زمان اعتبار:** ۳ روز تقویمی (`expire_days: 3`).
4. **کارمزد روزانه وام:** ۰ تومان (`daily_fee: "0"`).
5. **حد هشدار مارجین:** ۱,۰۰۰ تومان (`warning_limit: "1000"`).
6. **حد لیکویید قطعی:** ۹۰۰ تومان (`liquidity_limit: "900"`).
   - اگر ارزش کل دارایی‌های حساب به ۹۰۰ تومان افت کند، زیرحساب اعتباری فوراً لیکویید و بسته می‌شود.
7. **انقضا و پایان مسابقه:**
   - با پایان مدت زمان اعتبار پکیج یا اعلام اتمام مسابقه، حساب قفل می‌گردد. تمام موقعیت‌های باز باید پیش از ساعت انقضا نقد شده و به موجودی تومان خالص تبدیل شوند.

---

## جدول وضعیت استعلامات فنی (Summary Matrix)

| ردیف | موضوع فنی | وضعیت مستندات | وضعیت اعتبارسنجی زنده | منبع رسمی |
| :--- | :--- | :--- | :--- | :--- |
| ۱ | ساختار احراز هویت با `X-API-Key` | تاییدشده (VERIFIED) | تاییدشده | [Docs: Create API Key](https://developers.wallex.ir/docs/create-api-key) |
| ۲ | اتصال زیرحساب اعتباری با `sub-account-client-id` | تاییدشده (VERIFIED) | تاییدشده در Swagger اعتباری | `trade-credit-...yaml` |
| ۳ | استخراج بازارهای فعال اسپات (`/hector/web/v1/markets`) | تاییدشده (VERIFIED) | تاییدشده (۳۷۳ اسپات) | [Wallex MCP & Hector API](https://wallex.ir/landing/mcp/) |
| ۴ | اطلاعات پکیج ۱۸۳ هکاتون و لیست بازارهای غیرمجاز | تاییدشده (VERIFIED) | تاییدشده (۳۵۷ نماد در package 183) | `GET /v1/prop/packages/183` |
| ۵ | کندل‌های تاریخی و قیمت با فرمت UDF | تاییدشده (VERIFIED) | تاییدشده (Resolutions 1, 15, 60, 1D) | `GET /v1/udf/history` |
| ۶ | دفتر سفارش عمق ۵۰ سطحی | تاییدشده (VERIFIED) | تاییدشده | `GET /v1/depth` |
| ۷ | پروتکل وب‌سوکت Centrifugo v2 و کانال‌ها | تاییدشده (VERIFIED) | تاییدشده در مستندات | [Docs: WebSockets](https://developers.wallex.ir/docs/socket-intro) |
| ۸ | ثبت، استعلام و لغو سفارش اسپات با `client_id` | تاییدشده (VERIFIED) | تاییدشده در مستندات و Swagger | [Docs: Spot Orders](https://developers.wallex.ir/docs/spot-create-order) |
| ۹ | دقت قیمت و مقدار (`price_precision`, `amount_precision`) | تاییدشده (VERIFIED) | تاییدشده در داده بازارها | `GET /hector/web/v1/markets` |
| ۱۰ | حداقل ارزش ریالی سفارش (Min Notional) | نامشخص (UNVERIFIED) | بررسی اولیه: ۱۰۰ هزار تومان | نیاز به تایید کلید در Preflight |
| ۱۱ | زمان دقیق انقضای حساب اعتباری در روز سوم | تاییدشده در داده پکیج | فیلد `expireAt` در زیرحساب | `GET /v1/prop/user/packages/active` |
