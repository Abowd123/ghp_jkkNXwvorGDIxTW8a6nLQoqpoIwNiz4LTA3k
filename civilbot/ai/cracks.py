"""Concrete crack analysis: OpenCV segmentation + geometric features + rule-based diagnosis
(ACI 224.1R patterns, ACI 224R tolerable widths), optionally cross-checked by a vision LLM."""
from __future__ import annotations
import io
import math
import numpy as np
import cv2
from ..core import Result, InputError, fmt
from . import llm

TOLERABLE = [("dry air / protective membrane", 0.41), ("humidity, moist air, soil", 0.30), ("de-icing chemicals", 0.18),
             ("seawater & spray, wetting/drying", 0.15), ("water-retaining structures", 0.10)]


def _load(img_bytes: bytes, max_side=900):
    arr = np.frombuffer(img_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise InputError("ما قدرت أقرأ الصورة")
    h, w = img.shape[:2]
    s = max_side / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
        return img, s
    return img, 1.0


def segment(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    k = max(9, (min(g.shape) // 40) | 1)
    bh = cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    _, m = cv2.threshold(bh, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = max(_, 18)
    m = (bh > thr).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    out = np.zeros_like(m)
    min_len = max(20, min(g.shape) // 15)
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        elong = max(w, h) / max(1, min(w, h))
        fill = area / max(1, w * h)
        if max(w, h) >= min_len and (elong >= 2.5 or fill < 0.35):
            out[lab == i] = 255
    return out


def skeleton(mask):
    sk = np.zeros_like(mask)
    el = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    img = mask.copy()
    while True:
        er = cv2.erode(img, el)
        op = cv2.dilate(er, el)
        sk = cv2.bitwise_or(sk, cv2.subtract(img, op))
        img = er
        if cv2.countNonZero(img) == 0:
            break
    return sk


def features(mask):
    sk = skeleton(mask)
    ys, xs = np.nonzero(sk)
    if len(xs) < 15:
        return None
    lines = cv2.HoughLinesP(sk, 1, np.pi / 180, threshold=15, minLineLength=max(10, min(mask.shape) // 25), maxLineGap=6)
    angs, lens = [], []
    if lines is not None:
        for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4):
            L = math.hypot(x2 - x1, y2 - y1)
            a = math.degrees(math.atan2(-(y2 - y1), x2 - x1)) % 180   # 0 = horizontal, 90 = vertical
            angs.append(a); lens.append(L)
    angs, lens = np.array(angs), np.array(lens)
    if len(angs):
        # circular mean on doubled angles
        c = np.sum(lens * np.cos(np.radians(2 * angs))); s = np.sum(lens * np.sin(np.radians(2 * angs)))
        dom = (math.degrees(math.atan2(s, c)) / 2) % 180
        R = math.hypot(c, s) / np.sum(lens)          # 1 = all parallel, 0 = random
    else:
        dom, R = 0.0, 0.0
    # branch points on skeleton
    sk01 = (sk > 0).astype(np.uint8)
    nb = cv2.filter2D(sk01, -1, np.ones((3, 3), np.float32)) - sk01
    branches = int(np.sum((sk01 == 1) & (nb >= 3)))
    dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
    widths = 2 * dist[sk > 0]
    n_comp = cv2.connectedComponents(mask)[0] - 1
    return dict(dominant=dom, coherence=R, branches=branches, length_px=float(len(xs)), wmax_px=float(np.percentile(widths, 98)),
                wmean_px=float(np.mean(widths)), components=n_comp, coverage=float(np.count_nonzero(mask)) / mask.size, angles=(angs, lens), sk=sk)


def coin_scale(img, coin_mm):
    g = cv2.medianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), 5)
    c = cv2.HoughCircles(g, cv2.HOUGH_GRADIENT, 1.2, 50, param1=100, param2=40, minRadius=10, maxRadius=min(g.shape) // 4)
    if c is None:
        return None, None
    x, y, r = max(c[0], key=lambda t: t[2])
    return coin_mm / (2 * r), (int(x), int(y), int(r))


def diagnose(f, element="beam", zone="", ):
    a, R, br = f["dominant"], f["coherence"], f["branches"]
    inclined = 25 <= a <= 65 or 115 <= a <= 155
    vertical = 65 < a < 115
    horizontal = a <= 25 or a >= 155
    if R < 0.6 or (f["components"] >= 8 and R < 0.75):
        if f["wmax_px"] > 6 and element in ("slab", "wall", "pavement", "beam", "column"):
            return ("Map cracking (random pattern)", "Drying/plastic shrinkage, or ASR if wide with gel/staining", "شروخ شبكية: انكماش لدن/جاف، أو تفاعل قلوي-سيليكا إذا كانت عريضة مع ترسبات", 0.6)
        return ("Map cracking (random pattern)", "Plastic or drying shrinkage / thermal", "شروخ شبكية: انكماش لدن أو جاف أو حراري", 0.65)
    e = element
    if e == "beam":
        if vertical:
            return ("Flexural cracks", "Bending tension (typically mid-span bottom or over supports top)", "شروخ انحناء: إجهاد شد بسبب العزم (منتصف البحر من أسفل أو فوق الركائز من أعلى)", 0.75 if zone in ("", "mid") else 0.6)
        if inclined:
            return ("Shear (diagonal tension) cracks", "Inadequate shear capacity near supports / concentrated loads", "شروخ قص قطرية: نقص مقاومة القص قرب الركائز أو تحت الأحمال المركزة — خطيرة وتحتاج فحص عاجل", 0.75 if zone in ("", "support") else 0.6)
        return ("Longitudinal cracks", "Reinforcement corrosion (splitting along bars) or bond failure", "شروخ طولية موازية للحديد: صدأ التسليح أو فقد التماسك", 0.6)
    if e == "column":
        if vertical:
            return ("Vertical (splitting) cracks", "Excessive axial compression / corrosion of longitudinal bars", "شروخ رأسية: ضغط محوري زائد أو صدأ الحديد الطولي — خطر انهيار", 0.65)
        if horizontal:
            return ("Horizontal cracks", "Flexure (lateral load / eccentricity) or corrosion of ties", "شروخ أفقية: انحناء بسبب حمل جانبي أو لا مركزية، أو صدأ الكانات", 0.6)
        return ("Diagonal cracks", "Shear (lateral load, short-column effect)", "شروخ قطرية: قص بسبب أحمال جانبية أو تأثير العمود القصير", 0.65)
    if e == "wall":
        if inclined:
            return ("Diagonal cracks", "Differential settlement or shear; at opening corners: shrinkage/stress concentration", "شروخ قطرية: هبوط تفاضلي أو قص، وعند زوايا الفتحات: تركيز إجهادات/انكماش", 0.65)
        if vertical:
            return ("Vertical cracks", "Restrained shrinkage / thermal movement (missing joints)", "شروخ رأسية: انكماش مقيد أو حركة حرارية (نقص فواصل التمدد)", 0.65)
        return ("Horizontal cracks", "Lateral earth pressure (retaining) or corrosion", "شروخ أفقية: ضغط تربة جانبي أو صدأ", 0.55)
    # slab / pavement
    if R > 0.6:
        return ("Parallel cracks", "Flexure (under-reinforcement / overload) or restrained shrinkage across the short span", "شروخ متوازية: انحناء (نقص تسليح/تحميل زائد) أو انكماش مقيد", 0.6)
    return ("Map cracking", "Plastic / drying shrinkage", "شروخ شبكية: انكماش", 0.55)


def analyze(img_bytes: bytes, element="beam", zone="", scale=None, coin=None, exposure=None) -> Result:
    element = (element or "beam").lower()
    if element not in ("beam", "column", "slab", "wall", "pavement"):
        raise InputError("element = beam / column / slab / wall / pavement")
    img, s = _load(img_bytes)
    mask = segment(img)
    f = features(mask)
    r = Result("cracks", "Crack analysis & diagnosis", inputs=dict(element=element, zone=zone or "-", scale=f"{scale} mm/px" if scale else "-",
                                                                   reference=f"coin {coin} mm" if coin else "-"))
    if not f:
        r.add("Segmentation", "black-hat morphology + Otsu", "", "no clear cracks detected")
        r.warnings.append("ما لقيت شروخ واضحة. صوّر الشرخ عن قرب وبإضاءة جانبية")
        r.outputs = dict(found=False)
        r.images["annotated"] = _annot(img, mask, None, None, None)
        return r
    mmpx = None
    circle = None
    if scale:
        mmpx = scale / s
    elif coin:
        mmpx, circle = coin_scale(img, coin)
    r.add("Segmentation & skeleton", "black-hat → Otsu → elongation filter → morphological skeleton",
          f"{f['components']} crack segment(s) , coverage {fmt(f['coverage'] * 100, 2)} %", f"skeleton length {fmt(f['length_px'], 0)} px")
    r.add("Orientation", "length-weighted Hough angles (0° = horizontal)", f"coherence R = {fmt(f['coherence'], 2)} (1 parallel, 0 random)",
          f"dominant angle = {fmt(f['dominant'], 1)}°")
    if mmpx:
        wmax, wmean, L = f["wmax_px"] * mmpx, f["wmean_px"] * mmpx, f["length_px"] * mmpx
        r.add("Width & length", "w = 2·distance-transform along skeleton × scale", f"scale = {fmt(mmpx, 4)} mm/px" + (" (coin)" if circle else ""),
              f"w,max ≈ {fmt(wmax, 2)} mm , w,mean ≈ {fmt(wmean, 2)} mm , total length ≈ {fmt(L / 10, 1)} cm")
        sev = "hairline" if wmax < 0.1 else "fine" if wmax < 0.3 else "medium" if wmax < 1.0 else "wide"
        lim = [f"{n}: {w} mm {'✔' if wmax <= w else '✘'}" for n, w in TOLERABLE]
        r.add("Severity vs ACI 224R tolerable widths", "", "\n".join(lim), f"class: {sev}")
    else:
        wmax = None
        r.warnings.append("بدون مقياس ما أقدر أحسب العرض بالمليمتر: أضف scale=mm/px أو صوّر عملة بجانب الشرخ واكتب coin=25")
    typ, cause_en, cause_ar, conf = diagnose(f, element, zone)
    r.add("Rule-based diagnosis (ACI 224.1R patterns)", "", cause_en, f"{typ} — confidence {fmt(conf * 100, 0)} %")
    ai = None
    if llm.enabled():
        try:
            ok, buf = cv2.imencode(".jpg", img)
            prompt = (f"This is a photo of a cracked concrete {element}{' near ' + zone if zone else ''}. Our image analysis found dominant crack angle "
                      f"{f['dominant']:.0f}° (0=horizontal), coherence {f['coherence']:.2f}. Classify the crack pattern. Return JSON: "
                      "{type_en, cause_ar, severity_ar, actions_ar (list of 3 short Arabic recommendations), confidence (0-1)}.")
            ai = llm.parse_json(llm.vision(prompt, buf.tobytes(), "You are a structural forensic engineer. Be cautious; recommend inspection when unsure."))
            r.add("Vision-AI second opinion", "", ai.get("cause_ar", ""), f"{ai.get('type_en', '')} — confidence {fmt(float(ai.get('confidence', 0)) * 100, 0)} %")
            for a in ai.get("actions_ar", [])[:3]:
                r.warnings.append("توصية: " + str(a))
        except Exception as e:
            r.warnings.append(f"تعذر الحصول على رأي الذكاء الاصطناعي: {e}")
    r.add("Interpretation (Arabic)", cause_ar)
    if "Shear" in typ or "splitting" in typ.lower() or (wmax and wmax > 1.0):
        r.warnings.append("⚠️ نمط/عرض الشرخ قد يدل على مشكلة إنشائية: استشر مهندس إنشائي للفحص الميداني")
    r.warnings.append("التشخيص تقريبي من صورة واحدة ولا يغني عن الفحص الموقعي (مثل قياس العرض بالـ Crack gauge ومراقبة النمو)")
    r.outputs = dict(found=True, type=typ, conf=conf, dominant=f["dominant"], coherence=f["coherence"], wmax=wmax, ai=ai)
    r.images["annotated"] = _annot(img, mask, f, circle, typ)
    return r


def _annot(img, mask, f, circle, typ) -> bytes:
    out = img.copy()
    over = out.copy()
    over[mask > 0] = (40, 40, 230)
    out = cv2.addWeighted(over, 0.75, out, 0.25, 0)
    if f is not None:
        sk = f["sk"]
        out[sk > 0] = (0, 255, 255)
        h, w = out.shape[:2]
        cx, cy = w // 2, h // 2
        L = min(w, h) // 4
        a = math.radians(f["dominant"])
        cv2.arrowedLine(out, (int(cx - L * math.cos(a)), int(cy + L * math.sin(a))), (int(cx + L * math.cos(a)), int(cy - L * math.sin(a))), (255, 120, 0), 3, tipLength=0.08)
        cv2.rectangle(out, (0, 0), (w, 34), (255, 255, 255), -1)
        cv2.putText(out, f"{typ}  |  angle {f['dominant']:.0f} deg", (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.62, (30, 30, 30), 2, cv2.LINE_AA)
    if circle:
        cv2.circle(out, circle[:2], circle[2], (0, 200, 0), 3)
    ok, buf = cv2.imencode(".png", out)
    return buf.tobytes()


def synthetic(kind="shear", size=(480, 720), seed=1) -> bytes:
    """Synthetic concrete photo for testing."""
    rng = np.random.default_rng(seed)
    h, w = size
    base = (rng.normal(165, 12, (h, w))).clip(0, 255).astype(np.uint8)
    base = cv2.GaussianBlur(base, (5, 5), 0)
    img = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)

    def crack(p0, p1, wpx=3, segs=25):
        pts = [np.array(p0, float)]
        d = (np.array(p1, float) - p0) / segs
        for _ in range(segs):
            pts.append(pts[-1] + d + rng.normal(0, 3, 2))
        cv2.polylines(img, [np.array(pts, np.int32)], False, (55, 55, 55), wpx, cv2.LINE_AA)
    if kind == "shear":
        crack((120, 420), (380, 80)); crack((260, 440), (520, 120), 2)
    elif kind == "flexural":
        for x in (200, 330, 460, 590):
            crack((x, 470), (x + rng.normal(0, 10), 230), 2)
    elif kind == "map":
        for _ in range(26):
            p = rng.uniform([0, 0], [w, h]); q = p + rng.normal(0, 90, 2)
            crack(p, q, 2, 8)
    elif kind == "horizontal":
        crack((40, 250), (690, 262), 3)
    return cv2.imencode(".jpg", img)[1].tobytes()
