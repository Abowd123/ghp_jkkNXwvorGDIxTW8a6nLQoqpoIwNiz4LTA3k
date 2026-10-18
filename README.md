# CivilBot · مجاني بالكامل · بوت تلجرام + تطبيق Android

بوت تلجرام للمهندس المدني. هذه النسخة تغطي المرحلة 1 من الخطة كاملة:

| الأداة | الأمر | المخرجات |
|---|---|---|
| 📈 SFD & BMD (بسيطة، كابولي، مثبتة، مستمرة، بروز) | `/beam` | صورة (تحميل + قص + عزم + ترخيم) + خطوات + PDF |
| 📐 خصائص المقاطع (rect, T, I, L, C, circle, pipe, box, أي مضلع) | `/section` | صورة المقطع + A, x̄, ȳ, Ix, Iy, S, Z, r, المحاور الرئيسية |
| 🏗 تصميم كمرة خرسانية ACI 318-19 (مفرد/مزدوج + قص) | `/rc` | خطوات الحل ببنود الكود + اختيار الأسياخ + رسم القطاع |
| 🖼 Cross-Section Visualizer | ضمن `/rc` | PNG بمقياس حقيقي للأسياخ والكانات والغطاء |
| 🧠 القوانين خطوة بخطوة (حل لأي مجهول بـ SymPy) | `/formula` | القانون، الرموز والوحدات، التعويض، النتيجة |
| 🔁 محول الوحدات (kN, ton, kip, MPa, psi, kg/cm², psf…) | `/convert` | نتيجة فورية |
| 📄 المذكرة الحسابية | زر بعد كل حساب | PDF بالعربي |
| 🔒 إطلاق تجريبي مغلق | `BETA_USERS` + `/feedback` + `/stats` | قائمة سماح، حد يومي، سجل استخدام، ملاحظات |

## المرحلة 2: التحليل والتصميم المتقدم

| الأداة | الأمر | المخرجات |
|---|---|---|
| 🔺 محلل الجمالونات (مخصص أو جاهز Pratt/Howe/Warren) | `/truss` | صورة ملونة (شد أزرق، ضغط أحمر، صفري متقطع) + فحص m+r=2j + جدول القوى |
| 🏛 الإطارات 2D (Portal, Gable, أو مخصص، مع مفصلات) | `/frame` | مخططات N و V و M + شكل التشوه + ردود الأفعال |
| 🏢 الأعمدة + منحنى التفاعل P-M + النحافة | `/column` | منحنى P-M، رسم القطاع، DXF، بنود BBS |
| ⬜ البلاطات (اتجاه واحد بمعاملات ACI، اتجاهين بتحليل صفائح عددي) | `/slab` | خرائط العزوم، الحديد، الترخيم، DXF |
| 🎯 القص الثاقب | `/punch` | فحص ACI 22.6 مع السماكة المطلوبة |
| 🟫 القواعد المنفصلة (مع عزم) | `/footing` | الأبعاد، السماكة (ثاقب + قص)، الحديد، DXF (مسقط + قطاع) |
| 🧱 الجدران الساندة الكابولية | `/wall` | الانقلاب، الانزلاق (Shear key تلقائي)، ضغط التربة، الحديد، DXF |
| ⚖️ تراكيب الأحمال (ACI/ASCE LRFD, ASD, BS 8110) | `/combo` | كل التراكيب + الحاكمة |
| 🧭 مسار الأحمال والمساحات التخديمية (45°) | `/trib` | مسقط ملون + أحمال مكافئة للكمرات + أحمال الأعمدة |
| 📐 Parametric DXF Builder (6 قوالب) | تلقائي مع التصميم | كمرة (واجهة + قطاع)، عمود، قاعدة، بلاطة، جدار ساند |
| 📋 جدول تفريد الحديد BBS (BS 8666) | `/bbs` | يتجمع تلقائياً من كل التصاميم، Excel + صورة |

أمثلة:
```
/truss type=pratt span=12 h=3 n=6 P=20
/frame type=portal L=6 H=4 w=15 P=20 base=fixed
/frame N=0,0;0,4;6,4;6,0 M=1-2;2-3;3-4 S=1:fixed;4:pin W=2:15 F=2:20,0 hinge=2j
/column b=400 h=500 fc=28 fy=420 Pu=1800 Mu=220 lu=3.5
/slab Lx=4 Ly=5 edges=FSFS wD=2 wL=3 fc=28 fy=420
/slab type=one L=4 wD=2 wL=3 support=both
/punch c1=400 c2=400 d=200 fc=28 Vu=550 pos=interior
/footing PD=800 PL=500 qa=200 c1=400 c2=400 fc=25 fy=420 M=60
/wall H=5 phi=30 gamma=18 q=10 qa=200
/combo D=120 L=80 W=40 code=aci
/trib X=5,6 Y=4,4.5 q=12
/rc b=300 h=600 fc=28 fy=420 Mu=250 Vu=180 span=6
/bbs
```

ملاحظات هندسية:
- محرك الإطارات والجمالونات بطريقة الصلابة المباشرة، متحقق منه مقابل حلول Portal frame المغلقة (Ph/2·(3k+1)/(6k+1) و wL²/4h(2k+3)).
- البلاطات ذات الاتجاهين تُحل بالفروق المحدودة لمعادلة الصفائح، ومتحقق منها مقابل جداول Timoshenko (0.0479 و 0.00406 و 0.0513) بخطأ أقل من 1.5%.
- ملفات DXF بصيغة R12 بدون أي مكتبات خارجية، وتفتح في AutoCAD و BricsCAD و LibreCAD، مع طبقات CONCRETE و REBAR و STIRRUP و DIM و TEXT.

## المرحلة 3: التخصصات الأخرى والتصور

| القسم | الأوامر | المحتوى |
|---|---|---|
| 🌍 ميكانيكا التربة | `/bearing` `/mohr` `/lateral` `/consol` `/bulb` `/slope` | قدرة التحمل (Terzaghi/Meyerhof/Hansen/Vesic مع المياه الجوفية)، دائرة مور، Rankine/Coulomb، الهبوط بالتصلب ومنحنى الزمن، بصيلات Boussinesq، ثبات المنحدرات بطريقة Bishop |
| 🧪 المواد | `/mix` `/sieve` | تصميم خلطة ACI 211.1 كامل مع تصحيح الرطوبة وعدد الأكياس، تحليل منخلي مع FM و Cu و Cc وحدود ASTM C33 |
| 💧 الهيدروليكا | `/channel` `/pipe` | Manning (عمق عادي وحرج، Froude، أفضل مقطع) لمستطيل/شبه منحرف/مثلث/دائري، أنابيب Darcy-Colebrook و Hazen-Williams وقدرة المضخة |
| 📏 المساحة | `/traverse` `/level` `/hcurve` `/vcurve` `/earth` | تصحيح Bowditch والمساحة، الميزانية (Rise & Fall)، جداول توقيع المنحنيات الأفقية والرأسية، الحفر والردم ومنحنى Mass haul |
| 🛣 الطرق | `/pavement` `/ssd` | رصف مرن AASHTO 93 (طبقات)، مسافة الرؤية للتوقف وقيم K |
| 🔩 المنشآت المعدنية | `/sbeam` `/scol` `/stab` `/bplate` | AISC 360-16: كمرات (LTB، Lp/Lr، القص، الترخيم) مع اختيار تلقائي، أعمدة وانحناء مشترك H1، وصلة Shear tab (براغي، تحمل، Block shear، لحام) + DXF، لوح القاعدة DG1 |
| 🎬 التصور | `/il` `/anim` | خطوط التأثير (رد فعل/قص/عزم) مع شاحنة تصميم متحركة، GIF للانبعاج بأربع حالات ركائز، GIF للترخيم، GIF لأنماط الاهتزاز |
| 🎓 الاختبارات | `/quiz` `/score` | مسائل بأرقام عشوائية في 7 مواضيع، تصحيح تلقائي ±2%، حل بالخطوات، لوحة تقدم تحدد نقاط الضعف |

مكتبة القطاعات المعدنية: IPE100–600 و HEA100–300 و HEB100–300، والخصائص تنحسب من الأبعاد مع أنصاف أقطار الجذر، وتطابق الجداول الأوروبية بفرق أقل من 0.2%.

أمثلة:
```
/bearing B=2 L=2 Df=1.5 c=0 phi=30 gamma=18 method=meyerhof FS=3
/slope H=10 beta=30 c=10 phi=30 gamma=18
/mix fc=28 slump=75 nmsa=19 fm=2.8 rodded=1600 mcfa=3 absfa=1
/sieve sizes=4.75,2.36,1.18,0.6,0.3,0.15,0.075 mass=20,80,120,150,90,30,10
/channel shape=trap b=3 z=2 n=0.015 S=0.001 Q=10
/traverse az=45-30-00,135-12-00,225,315-06 d=100,100,100.05,99.98
/hcurve R=300 delta=40 PI=1000
/pavement W18=5e6 R=95 S0=0.45 MR=50 MRb=200 MRsb=100
/sbeam Mu=150 Vu=120 Lb=3 L=6 w=15
/stab Vu=250 d=20 grade=A325N tp=10
/il L=20 S=pin@0 S=roller@10 S=roller@20 qty=M x=5 truck=145@4.3,145@4.3,35
/anim type=buckling E=200e6 I=8e-6 L=4
/quiz concrete
```

## المرحلة 4: الذكاء الاصطناعي والإنتاجية

| الميزة | كيف | التفاصيل |
|---|---|---|
| 🔍 محلل الشروخ | أرسل صورة + `crack element=beam zone=support coin=25` | تقطيع الشروخ بـ OpenCV، الاتجاه والتماسك، العرض بالمليمتر (بمقياس أو عملة)، تشخيص حسب أنماط ACI 224.1R، مقارنة مع حدود ACI 224R، ورأي ثاني من نموذج رؤية (اختياري) |
| 🧮 قارئ المعادلات | أرسل صورة + `equation` | نموذج رؤية يقرأ المعادلة ← SymPy يتحقق منها ← تصير حاسبة تفاعلية تحل لأي مجهول. الأرقام دائماً من SymPy |
| 🏠 توزيع الأعمدة | أرسل اسكتش + `layout L=15 span=6` | كشف الجدران، شبكة محاور مرقمة، إضافة محاور وسطية لو البحر أكبر من الحد، أعمدة حمراء عند تقاطعات الجدران |
| 📚 مقارنة الأكواد | `/codes سؤالك` | 16 موضوع × 4 أكواد (ACI 318-19 و BS 8110 و EC2 و SBC 304) مع أرقام البنود. الذكاء الاصطناعي يلخص فقط من الصفوف المسترجعة |
| 📋 جدول الأعمدة | `/schedule` أو Excel | تصميم كل الأعمدة، اختيار أصغر مقطع اقتصادي، تجميع المتشابه في أنواع C1 و C2، وتصدير PNG و Excel و DXF |
| 🧾 حصر الكميات | `/boq` | خرسانة وحديد وشدات وبلوك ولياسة وبلاط مع الهالك، وتقدير تكلفة، وتصدير Excel بمعادلات |
| ✏️ المحرر الرسومي | `/editor` | Telegram Mini App ترسم فيه الإطار أو الجمالون باللمس وترسله للتحليل |
| 🧊 عارض 3D | تلقائي بعد `/frame` و `/truss` | three.js مع تشوه متحرك (زر داخل تلجرام لو WEBAPP_URL مضبوط، وإلا ملف HTML) |
| 📁 المشاريع والسجل | `/projects` `/newproject` `/history` `/export` | كل حساب ينحفظ، إعادة تشغيل بضغطة، وتصدير المشروع ZIP فيه كل المذكرات PDF وملفات DXF و Excel |
| 📑 استيراد Excel | `/templates` ثم ارفع الملف | كل ورقة = أداة وكل صف = حساب (rc, column, footing, beam, sbeam, bearing, schedule, boq) وترجع النتائج في Excel |

**تفعيل الذكاء الاصطناعي:** ضع `LLM_API_KEY` (أي مزود متوافق مع OpenAI: OpenAI أو OpenRouter أو Groq أو Together أو Ollama). بدون المفتاح تشتغل كل الميزات ما عدا قراءة المعادلات، ومحلل الشروخ يشتغل بالتحليل الهندسي بدون الرأي الثاني.

**تفعيل الـ Mini App:** ارفع مجلد `civilbot/webapp` على أي استضافة HTTPS، وضع `WEBAPP_URL`، وسجّل الدومين في @BotFather.

## الإصدار المجاني + تطبيق APK + تنصيب مجاني

- **مجاني بالكامل** (`FREE_MODE=1` افتراضياً): كل الأدوات مفتوحة، بدون دفع وبدون علامة مائية. يبقى فقط حد يومي 300 عملية ومحدد معدل للحماية من الإساءة. كود الباقات باقٍ ويرجع مع `FREE_MODE=0`.
- **تطبيق Android:**
  - `python -m civilbot.api` يشغّل الواجهة البرمجية وتطبيق PWA عربي (`civilbot/webapp/app`)
  - طريقة تحويله إلى APK بأداة PWABuilder المجانية في [docs/apk/BUILD_APK.md](docs/apk/BUILD_APK.md)
  - دراسة الخيارات في [docs/apk/STUDY.md](docs/apk/STUDY.md)
- **تنصيب مجاني:**
  - Oracle Cloud Always Free (2 نواة / 12GB) مع دومين DuckDNS و HTTPS تلقائي
  - `bash deploy/oracle/setup.sh`
  - التفاصيل في [docs/hosting/FREE_HOSTING.md](docs/hosting/FREE_HOSTING.md)

## المرحلة 5: الإطلاق العام

**الأداء:** المهام الثقيلة تعمل في مجموعة عمليات منفصلة (`WORKERS`) مع خيط BLAS واحد لكل عملية، وكاش للنتائج المتكررة، ومحدد معدل لكل مستخدم، ومهلة لكل مهمة.

| اختبار الحمل (4 أنوية) | قبل | بعد |
|---|---|---|
| 30 مستخدم متزامن، p50 | 4.62 ث | 1.55 ث |
| 30 مستخدم متزامن، p95 | 8.38 ث | 1.98 ث |
| الإنتاجية | 6.2 طلب/ث | 18.5 طلب/ث (22.9 مع الكاش) |
| 4 متزامنين، p95 | | 0.44 ث |

السبب الرئيسي للتحسن: كل عملية كانت تفتح 4 خيوط BLAS على 4 أنوية (16 خيط يتصارعون). الآن خيط واحد لكل عملية + تسخين الخطوط عند التشغيل.

**الاشتراكات (Telegram Stars، معطلة في الإصدار المجاني):** /plans ← فاتورة XTR ← precheckout ← تفعيل الباقة. مجاني (10 يومياً، علامة مائية) · طالب 150⭐ · محترف 450⭐ · مكاتب 1500⭐ (10 مقاعد + شعار). الأسعار من `.env`.

**النمو:** روابط دعوة `/invite` (3 أيام طالب للطرفين)، أكواد ترويج `/promo` و `/redeem`، رابط `t.me/Bot?start=promo_CODE`.

**التشغيل:** تقرير مؤشرات يومي للأدمن، نسخ احتياطي يومي، HEALTHCHECK في Docker، أوامر `/terms` `/privacy` `/paysupport` `/deleteme`، CI على GitHub Actions.

**حزمة الإطلاق:** `docs/launch/` (قائمة الإطلاق، BotFather، منشورات جاهزة، برنامج السفراء، الأسئلة الشائعة) و `docs/landing/index.html` صفحة هبوط.

## النشر على Railway
شاهد [RAILWAY.md](RAILWAY.md): `Dockerfile.railway` + `railway.json` + `start.sh` جاهزة (`SERVICE=bot` أو `SERVICE=api`).

## التشغيل محلياً
```bash
pip install -r requirements.txt
cp .env.example .env   # ضع BOT_TOKEN من @BotFather
export $(cat .env | xargs)
python -m civilbot.bot.main
```
## التشغيل على سيرفر
```bash
docker compose up -d --build
```
اضبط `WEBHOOK_URL=https://your-domain` لتفعيل الـ webhook (خلف Nginx/Caddy مع HTTPS).

## الاختبارات
```bash
pytest -q
```
56 اختبار تحقق (منها صور شروخ ومخططات اصطناعية، و Excel، ومحاكاة نموذج الذكاء الاصطناعي) مقابل حلول ومراجع منشورة (Timoshenko، جداول Das لعوامل التحمل، Newmark، مثال دليل AASHTO 93، جداول IPE/HEB الأوروبية، Moody، …) وكلها ناجحة.

## أمثلة سريعة
```
/beam L=6 type=ss w=25 P=40@2
/beam L=10 S=pin@0 S=roller@5 S=roller@10 w=20
/beam L=8 S=pin@0 S=roller@6 w=15@0-6 P=30@8 M=10@3
/rc b=300 h=600 fc=28 fy=420 Mu=250 Vu=180
/section T bf=800 tf=120 bw=300 h=600
/formula euler E=200e6 I=8e-6 K=1 L=4
/convert 25 kN/m2 to psf
```

## الهيكل
```
civilbot/
├── core.py          # كائن النتيجة الموحد (Result/Step)
├── services.py      # تحليل النصوص → المحركات → النتائج (بدون اعتماد على تلجرام)
├── services2.py     # المرحلة 2
├── services3.py     # المرحلة 3
├── services4.py     # المرحلة 4
├── ai/              # llm (عميل عام), cracks (OpenCV), equation (SymPy), layout, codes (قاعدة الأكواد)
├── webapp/          # editor.html (Mini App) + viewer3d.html (three.js)
├── engines/         # beam, section, rc_beam, formulas, units, frame, rc_column, slab, footing, retaining, loads, bbs,
│                    # geotech, materials, hydraulics, survey, roads, steel, influence, quiz, schedule, boq
├── drawing/         # plots.py, plots2.py, plots3.py (PNG) + dxf.py (DXF) + anim.py (GIF)
├── reports/pdf.py   # WeasyPrint PDF
└── bot/             # main.py (python-telegram-bot v21), storage.py (SQLite للتجربة)
```
المحركات مستقلة عن البوت، فنفس الكود يشتغل لاحقاً في Mini App أو API (المرحلة 4).

> ⚠️ النتائج لأغراض تعليمية ومراجعة أولية ولا تغني عن مراجعة مهندس مرخص.
