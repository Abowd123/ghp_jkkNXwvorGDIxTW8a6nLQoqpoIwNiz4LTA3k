# CivilBot Mini App

ملفات ثابتة (Static) ترفعها على أي استضافة HTTPS (GitHub Pages / Netlify / Cloudflare Pages / نفس السيرفر خلف Nginx).

- `editor.html`: محرر إطارات وجمالونات بالرسم واللمس، يرسل النموذج للبوت عبر `Telegram.WebApp.sendData`.
- `viewer3d.html`: عارض ثلاثي الأبعاد (three.js) للمنشأ وشكل التشوه المتحرك. يقرأ النموذج من `#base64` في الرابط أو من `window.__MODEL__`.

بعد الرفع ضع في `.env`:
```
WEBAPP_URL=https://your-domain/webapp
```
ثم سجّل الدومين عند @BotFather ← Bot Settings ← Configure Mini App / Domain.
