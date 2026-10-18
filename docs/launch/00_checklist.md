# قائمة الإطلاق العام (المرحلة 5)

## قبل الإطلاق بأسبوعين
- [ ] سيرفر Oracle Always Free مجاني (2 OCPU / 12GB) + دومين DuckDNS مجاني (docs/hosting/FREE_HOSTING.md)
- [ ] `cp .env.example .env` وتعبئة BOT_TOKEN, WEBHOOK_URL, ADMIN_IDS, SUPPORT_CONTACT, LLM_API_KEY
- [ ] `WORKERS` = عدد أنوية المعالج، و `BETA_USERS` فارغ (مفتوح للجميع)
- [ ] `docker compose up -d --build` ثم `docker ps` يجب أن يظهر healthy خلال دقيقتين
- [ ] اختبار حمل على السيرفر نفسه: `python scripts/loadtest.py --requests 300 --concurrency 30`
- [ ] إعداد BotFather (انظر 01_botfather.md)
- [ ] تشغيل التطبيق على الدومين وبناء APK (docs/apk/BUILD_APK.md) ورفعه على صفحة الهبوط
- [ ] رفع صفحة الهبوط docs/landing على GitHub Pages أو Netlify

## أسبوع الإطلاق
- [ ] نشر منشور الإطلاق (02_posts.md) في القروبات والحسابات
- [ ] تعيين سفير لكل جامعة ومتابعة روابط /invite حقته
- [ ] متابعة تقرير المؤشرات اليومي الذي يصل للأدمن
- [ ] الرد على كل /feedback خلال 24 ساعة

## المؤشرات المستهدفة (3 أشهر)
| المؤشر | الهدف | من أين تقرأه |
|---|---|---|
| مستخدمون نشطون شهرياً | 1000 | `/stats` والتقرير اليومي |
| الاحتفاظ بعد 7 أيام | 30% أو أكثر | التقرير اليومي |
| تثبيتات APK | 300 | GitHub Releases |
| زمن الحسابات | أقل من 3 ث | السجلات + loadtest |
| زمن الرسومات | أقل من 15 ث | السجلات |
| دقة اختبارات التحقق | 99% | `pytest` في CI |

## خطة النسخ الاحتياطي والطوارئ
- نسخة احتياطية تلقائية يومياً في /backups (آخر 7 نسخ) + `/backup` يدوياً
- إذا علق البوت: Docker يعيد تشغيله تلقائياً عند فشل HEALTHCHECK
- الاسترجاع: أوقف الحاوية، انسخ أحدث ملف من backups إلى data/civilbot.sqlite3، شغّل
