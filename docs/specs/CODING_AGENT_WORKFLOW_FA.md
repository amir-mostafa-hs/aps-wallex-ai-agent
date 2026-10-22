# گردش‌کار Coding Agent در ۴۸ ساعت

## 1. ابزارها و اصول

- Codex یا Antigravity را روی یک Git repo واحد استفاده کنید.
- یک Coding Agent در هر لحظه مالک تغییرات معماری/فایل‌های مشترک باشد؛ موازی‌سازی فقط برای taskهایی که interface آنها مشخص و جداست.
- هر task باید یک رفتار قابل‌دمو، معیار پذیرش و تست داشته باشد. Skill chain پیشنهادی بر مبنای صفحه رسمی فعلی AI Hero است: `/setup-matt-pocock-skills` در صورت نیاز → `/to-spec` (اگر Spec issue لازم است) → `/to-tickets` → `/implement` برای هر ticket جداگانه → TDD در مرز تست توافق‌شده → `/code-review`. برای Antigravity سازگاری مستقیم را تست کنید و فرض نگیرید.
- به‌جای prompt بزرگ «کل ربات را بساز»، یک vertical slice کوچک بسازید، تست کنید و سپس توسعه دهید.
- تغییرات کوچک commit شوند؛ پس از هر milestone اجرای تست‌ها و بازبینی diff اجباری باشد.

## 2. بررسی Matt Pocock / AI Hero

صفحه رسمی AI Hero مهارت‌ها را به شکل فایل‌های قابل نصب برای workflow مهندسی AI معرفی می‌کند و در فهرست فعلی Codex را صریحاً نام می‌برد. Antigravity در فهرست سازگاری رسمی صفحه‌ای که بررسی شد نام‌برده نشده؛ می‌توان از متن/خروجی Markdown این روش در آن استفاده کرد، اما compatibility مستقیم را تا زمان تست ابزار فرض نکنید.

نصب رسمی کلی:

```bash
npx skills@latest add mattpocock/skills
```

مهارت‌های مفید برای این پروژه (نام/موجودبودن هر skill را در نسخه نصب‌شده بررسی کنید):

- `/setup-matt-pocock-skills` — راه‌اندازی repo/زبان مشترک برای Agentها.
- `/to-spec` — ثبت تصمیم‌های توافق‌شده در Spec؛ برای پروژه چندمرحله‌ای.
- `/to-tickets` — شکستن Spec به ticketهای کوچک با blockerهای روشن و خروجی قابل‌دمو.
- `/implement` — ساخت task test-first و اجرای چرخه پیاده‌سازی.
- `/tdd` — نام‌گذاری seamهای تست و اجرای red-green-refactor.
- `/code-review` — بازبینی diff در برابر Spec و استانداردهای کد.
- `/writing-for-agents` — نوشتن مستندات و دستورالعمل‌هایی که Agent می‌تواند دقیق مصرف کند.
- `/grill-with-docs` — اگر تصمیم تازه‌ای مهم کشف شد، ثبت اصطلاحات و تصمیم‌ها.

مستندهای رسمی: https://www.aihero.dev/skills و https://github.com/mattpocock/skills

## 3. Sequence پیشنهادی

1. **ثبت context:** این بسته، `assets.md` اصلی و لینک‌های رسمی Wallex را به Agent بدهید؛ قرارداد یگانه Agent در `docs/AGENT_CONTRACT_FA.md` و شکاف منابع در `docs/SOURCE_MATERIALS_AND_GAPS_FA.md` را هم بخواند. بخواهید قبل از کد، endpointها را از مستند رسمی تأیید کند و هیچ endpoint/schema را حدس نزند.
2. **Spec:** `docs/DECISION_REGISTER_FA.md` تصمیم‌های کاربر و `docs/SPEC_FA.md` نیازمندی محصول را نگه می‌دارند؛ `docs/AGENT_CONTRACT_FA.md` مرجع واحد schema است. تصمیم‌های جدید را به اسناد ثبت کنید، نه promptهای پراکنده.
3. **Ticketing:** اگر workflow مهارت‌ها tracker راه‌اندازی می‌خواهد، local Markdown tickets یا issue tracker را configure کنید؛ سپس `/to-tickets` و blockers را مرور کنید.
4. **Vertical slice اول:** API read-only → market universe → DB event → snapshot/status.
5. **Vertical slice دوم:** Candidate → AI JSON → risk decision → Shadow fill → P&L record.
6. **Vertical slice سوم:** همان مسیر با executor واقعی، فقط پس از gateهای P0.
7. **TDD:** برای sizing، risk rejects، order state transitions، duplicate prevention و realized P&L تست‌های مبتنی بر رفتار بنویسید.
8. **Review:** بعد از هر task، `/code-review`؛ بعد تست روی VPS و restart reconciliation.
9. **Freeze:** در انتهای ۴۸ ساعت commit tag و config/model/prompt versions ثبت شود؛ feature جدید روی نسخه زنده deploy نشود مگر fix ضروری.

## 4. Promptهای لازم به Agent

- «اول repo و Spec را بخوان؛ حدس درباره Wallex API ممنوع است. endpoint، params، response و auth را در docs/API notes با لینک رسمی ثبت کن. اگر چیزی معلوم نیست، یک spike کوچک read-only بساز.»
- «ابتدا seams و معیار پذیرش این task را پیشنهاد کن؛ تا قبل از تست‌های رفتاری و acceptance، featureهای نامرتبط اضافه نکن.»
- «فقط این ticket را انجام بده؛ اگر نیاز به تغییر معماری بزرگ است، متوقف شو و گزینه‌ها/هزینه را اعلام کن.»
- «برای هر order-related change سناریوی timeout بعد از submit، partial fill، cancel failure، restart و duplicate prevention را تست کن.»
- «هر تصمیم AI باید schema-validated باشد و به TradeIntent ختم شود؛ هیچ direct exchange call در code مسیر LLM نباشد.»
- «بعد از پیاده‌سازی، تست‌های مرتبط را اجرا کن، diff را خلاصه کن، نتایج واقعی تست را گزارش کن و هیچ تست اجرا نشده‌ای را سبز ادعا نکن.»

## 5. قواعد جلوگیری از اتلاف وقت

- قبل از شروع، همه endpointها و schemaها را با مستند رسمی/یک read-only request بررسی کنید.
- اول هیچ UI پیچیده‌ای نسازید؛ وضعیت ضروری را با endpoint/صفحه ساده نمایش دهید.
- از LLM روی هر بازار و هر tick استفاده نکنید؛ scanner همه بازارها را سبک بررسی کند و فقط top-K candidate به مدل برسد.
- در نسخه زنده، مدل نباید کد یا strategy implementation جدید اجرا کند.
- LangChain را برای یک Decision Agent با خروجی ساختاریافته به‌کار ببرید؛ تا پایان P0/P1 سراغ swarm چندایجنتی، planner پیچیده یا LangGraph سفارشی نروید مگر blocker مشخصی وجود داشته باشد.
- زمان‌بندی scanner مستقل از LangChain باشد؛ LLM روی هر بازار و هر tick اجرا نشود.
- از اضافه‌کردن اخبار، پیام‌رسان، multiple exchange و optimizer پرهیز کنید تا P0 و P1 تمام شود.
- وقتی خطای execution unresolved است، به توسعه feature جدید ادامه ندهید.
