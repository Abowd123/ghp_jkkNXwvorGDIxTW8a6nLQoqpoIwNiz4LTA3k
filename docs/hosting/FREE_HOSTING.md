# التنصيب المجاني (تمت المراجعة في أكتوبر 2026)

## المقارنة
| الخدمة | المجاني | يكفي CivilBot؟ | ملاحظات |
|---|---|---|---|
| **Oracle Cloud Always Free (ARM A1)** | **2 أنوية + 12GB RAM + 200GB قرص، للأبد** | ✅ **الأفضل** | خُفّض من 4/24 إلى 2/12 في 2026، ولا يزال كافياً جداً. يطلب بطاقة للتحقق فقط، بدون خصم |
| Render (free web) | 512MB، وينام بعد 15 دقيقة | ⚠️ للتطبيق فقط | الاستيقاظ يأخذ حوالي دقيقة. لا يصلح للبوت |
| Koyeb (free) | 0.1 نواة + 512MB | ❌ | ضعيف جداً للرسومات و PDF |
| Hugging Face Spaces | Docker أصبح مدفوعاً، و api.telegram.org محجوب | ❌ | |
| Google Cloud e2-micro | 1GB | ⚠️ | ممكن مع WORKERS=0 لكن بطيء |
| GitHub Pages / Cloudflare Pages | استضافة ملفات ثابتة | ✅ لصفحة الهبوط | |

**الذكاء الاصطناعي مجاناً:** مفتاح Gemini من Google AI Studio مجاني، بحدود تقارب 15 طلب في الدقيقة و 1500 في اليوم. والبوت متوافق معه مباشرة لأن عميله متوافق مع OpenAI (راجع `.env.example`).
تنبيه: في الخطة المجانية قد تستخدم Google الصور والنصوص لتحسين نماذجها، فاذكر هذا في سياسة الخصوصية.
تحليل الشروخ يعمل محلياً بـ OpenCV بدون أي مفتاح. قارئ المعادلات وتوزيع الأعمدة يحتاجان المفتاح.

**الدومين مجاناً:** DuckDNS يعطي `civilbot.duckdns.org` مجاناً، و Caddy يصدر شهادة HTTPS تلقائياً.

**التكلفة الإجمالية: صفر.**

## الخطوات على Oracle (حوالي 30 دقيقة)
1. سجّل في https://cloud.oracle.com/free واختر Home Region قريب منك، مثل Jeddah أو Dubai أو Frankfurt.
   **انتبه:** Always Free يعمل فقط في منطقتك الرئيسية، ولا يمكن تغييرها لاحقاً.
2. **Compute، ثم Instances، ثم Create**:
   - Image: Ubuntu 24.04
   - Shape: **VM.Standard.A1.Flex** بنواتين و 12GB
   - Boot volume: 50GB
   - أضف مفتاح SSH
   - إذا ظهرت رسالة "Out of capacity" جرّب بعد ساعات، أو اختر Availability Domain آخر.
3. **Networking، ثم VCN، ثم Security List**: أضف Ingress للمنافذ TCP 80 و 443 من `0.0.0.0/0`.
4. من https://www.duckdns.org سجّل دخول، وأنشئ `civilbot`، وضع الـ Public IP حق السيرفر.
5. على السيرفر:
   ```bash
   git clone <repo> civilbot   # أو ارفع ملف ZIP وفك ضغطه
   cd civilbot && bash deploy/oracle/setup.sh   # المرة الأولى تنشئ .env
   nano .env    # BOT_TOKEN, ADMIN_IDS, DOMAIN=civilbot.duckdns.org, LLM_API_KEY (Gemini)
   bash deploy/oracle/setup.sh
   ```
6. افتح `https://civilbot.duckdns.org` للتطبيق، وأرسل `/start` للبوت.

**الوضع الافتراضي:** البوت يعمل بـ polling، فلا يحتاج webhook ولا منفذ مفتوح. التطبيق يعمل خلف Caddy على HTTPS.

## الأداء المتوقع على 2 OCPU
في الاختبار: 4 أنوية أعطت حوالي 18 طلب في الثانية، و p95 أقل من ثانيتين مع 30 مستخدم متزامن.
على نواتين تتوقع حوالي **8 إلى 9 طلبات في الثانية**، وهذا يكفي آلاف المستخدمين النشطين يومياً. التحقق: `python scripts/loadtest.py --workers 2 --concurrency 10`.

## إذا تعذّر Oracle
شغّل البوت على أي جهاز عندك بشكل دائم بأمر واحد `docker compose up -d`، مثل لابتوب قديم أو Raspberry Pi 4/5 بذاكرة 4GB أو أكثر، مع WORKERS=2.
وارفع التطبيق على Render المجاني (`render.yaml` جاهز)، مع العلم إنه ينام بعد 15 دقيقة.

## الصيانة
- النسخ الاحتياطي يومي في `./backups`. للنسخ اليدوي: `/backup` من تلجرام.
- التحديث: `git pull && docker compose -f docker-compose.yml -f deploy/oracle/compose.oracle.yml up -d --build`
- المراقبة: `docker compose ps` يجب أن يظهر healthy، وتقرير المؤشرات يصلك يومياً على تلجرام.
- حسابات Oracle المجانية الخاملة قد تُسترجع، والبوت النشط يستهلك CPU فلا يُعتبر خاملاً.
