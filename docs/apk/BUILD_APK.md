# بناء ملف APK مجاناً (15 دقيقة، بدون Android Studio)

## المتطلبات
- التطبيق شغال على دومين HTTPS. مثال: `https://civilbot.duckdns.org` (راجع docs/hosting).
- افتح الرابط في كروم الجوال وتأكد إن خيار "تثبيت التطبيق" يظهر. هذا يعني إن الـ PWA سليم.

## الطريقة 1: PWABuilder (الأسهل، من المتصفح)
1. ادخل https://www.pwabuilder.com واكتب رابط الدومين، ثم Start.
2. اضغط **Package for stores**، ثم **Android**، ثم **Generate Package**.
   - Package ID: `app.civilbot.twa`
   - App name: `CivilBot`
   - Signing key: **New** (احفظ ملف المفتاح وكلمة المرور في مكان آمن، لأنك تحتاجه لكل تحديث)
3. نزّل الملف المضغوط. بداخله:
   - `app-release-signed.apk`: للتثبيت المباشر والتوزيع
   - `app-release-bundle.aab`: لرفعه على Google Play
   - `assetlinks.json`
4. افتح `assetlinks.json` وانسخ قيمة `sha256_cert_fingerprints` إلى `.env`:
   ```
   TWA_PACKAGE=app.civilbot.twa
   TWA_SHA256=AB:CD:...
   ```
   ثم شغّل `docker compose restart api`. تأكد إن الرابط `https://DOMAIN/.well-known/assetlinks.json` يعرض البصمة.
   **مهم:** بدون هذه الخطوة يظهر شريط عنوان المتصفح أعلى التطبيق.
5. انقل الـ APK للجوال وثبّته، مع السماح بالتثبيت من مصادر غير معروفة.

## الطريقة 2: Bubblewrap (سطر الأوامر)
```bash
npm i -g @bubblewrap/cli
bubblewrap init --manifest=https://civilbot.duckdns.org/manifest.webmanifest
bubblewrap build          # → app-release-signed.apk
keytool -list -v -keystore android.keystore | grep SHA256   # → TWA_SHA256
```
إعداد جاهز موجود في `twa-manifest.json`.

## التوزيع المجاني
- **مباشر:** ارفع الـ APK على GitHub Releases أو قناة التلجرام، وضع الرابط في صفحة الهبوط.
- **Google Play (اختياري):** حساب مطور برسوم 25$ مرة واحدة، وارفع ملف `.aab`. بعد ما Play يوقّع التطبيق، أضف بصمته الثانية (App signing key) إلى `TWA_SHA256`، وافصل البصمات بفاصلة.
- **iPhone:** من Safari اختر "مشاركة"، ثم "إضافة إلى الشاشة الرئيسية". مجاني بدون App Store.

## التحديثات
تحديث الواجهة أو المحركات على السيرفر يصل للجميع فوراً. إعادة بناء الـ APK لازمة فقط عند تغيير الاسم أو الأيقونة أو الدومين.
