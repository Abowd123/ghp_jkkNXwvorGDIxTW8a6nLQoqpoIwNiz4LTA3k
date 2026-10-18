# نشر CivilBot على Railway

## 1) ارفع المشروع على GitHub
```bash
unzip civilbot-railway.zip -d civilbot && cd civilbot
git init && git add . && git commit -m "civilbot"
git branch -M main
git remote add origin https://github.com/USER/civilbot.git
git push -u origin main
```

## 2) خدمة البوت
1. Railway ← New Project ← Deploy from GitHub repo ← اختر المستودع.
2. تبويب **Variables** ← Raw Editor والصق:
```
BOT_TOKEN=ضع_التوكن
ADMIN_IDS=ايديك
FREE_MODE=1
WORKERS=2
```
   (اختياري: `LLM_API_KEY` و `LLM_BASE_URL` و `LLM_MODEL`)
3. تبويب **Settings ← Volumes ← New Volume** وحدد Mount Path = `/data` (لحفظ قاعدة البيانات والنسخ الاحتياطي).
4. Deploy. افتح Logs وأرسل `/start` للبوت.

> لا تضع `WEBHOOK_URL`. البوت يعمل polling ولا يحتاج دومين.

## 3) خدمة التطبيق (اختياري، PWA + API)
1. في نفس المشروع: New ← GitHub Repo ← نفس المستودع.
2. Variables: `SERVICE=api` و `WORKERS=1`
3. Settings ← Networking ← **Generate Domain**، ثم افتح الرابط.
4. Settings ← Deploy ← Healthcheck Path = `/health`

## ملاحظات
- شغّل نسخة واحدة فقط من البوت. تشغيل نسختين يسبب خطأ Conflict في تلجرام.
- لو الذاكرة قليلة: `WORKERS=1` (أو `0` لخيط واحد).
- التحديث: أي `git push` يعيد النشر تلقائياً.
