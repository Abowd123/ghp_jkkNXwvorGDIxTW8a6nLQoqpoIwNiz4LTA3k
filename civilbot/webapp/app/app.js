/* CivilBot PWA: same engines as the Telegram bot, via /api */
const API = (new URLSearchParams(location.search).get("api") || localStorage.getItem("api") || "").replace(/\/$/, "");
if (new URLSearchParams(location.search).get("api")) localStorage.setItem("api", API);
const $ = (id) => document.getElementById(id);
let CAT = null, current = null, lastRun = null;

async function api(path, body) {
  const r = await fetch(API + path, body ? {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)} : {});
  if (!r.ok) {
    let m = "خطأ " + r.status;
    try { m = (await r.json()).error || m; } catch (e) {}
    throw new Error(m);
  }
  return r;
}

function show(id) {
  for (const s of ["home", "tool", "history"]) $(s).classList.toggle("hidden", s !== id);
  $("back").classList.toggle("hidden", id === "home");
  if (id === "home") { $("title").textContent = "👷‍♂️ CivilBot"; history.replaceState({v: "home"}, ""); }
  window.scrollTo(0, 0);
}

function renderHome(filter = "") {
  const f = filter.trim();
  $("cats").innerHTML = "";
  for (const c of CAT.categories) {
    const tools = c.tools.filter((t) => !f || CAT.tools[t].name.includes(f) || t.includes(f.toLowerCase()) || c.name.includes(f));
    if (!tools.length) continue;
    const div = document.createElement("div");
    div.className = "cat";
    div.innerHTML = `<h2>${c.name}</h2><div class="grid"></div>`;
    for (const t of tools) {
      const b = document.createElement("button");
      b.className = "t";
      b.textContent = CAT.tools[t].name;
      b.onclick = () => openTool(t);
      div.querySelector(".grid").appendChild(b);
    }
    $("cats").appendChild(div);
  }
}

function openTool(t, text) {
  current = t;
  const m = CAT.tools[t];
  $("title").textContent = m.name;
  $("help").innerHTML = m.help;
  $("examples").innerHTML = "";
  for (const ex of m.examples) {
    const c = document.createElement("span");
    c.className = "chip"; c.textContent = ex; c.title = ex;
    c.onclick = () => { $("input").value = ex.replace(/^\/\w+\s*/, ""); };
    $("examples").appendChild(c);
  }
  $("help").querySelectorAll("code").forEach((c) => c.onclick = () => { $("input").value = c.textContent.replace(/^\/\w+\s*/, ""); });
  $("textWrap").classList.toggle("hidden", m.photo);
  $("photoWrap").classList.toggle("hidden", !m.photo);
  $("examples").classList.toggle("hidden", m.photo);
  $("input").value = text ?? (m.examples[0] || "").replace(/^\/\w+\s*/, "");
  $("result").innerHTML = ""; $("status").textContent = "";
  history.pushState({v: "tool", t}, "");
  show("tool");
}

function b64Blob(b64, type) {
  const bin = atob(b64), arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return new Blob([arr], {type});
}

function renderResult(d) {
  const R = $("result");
  R.innerHTML = "";
  const wrap = document.createElement("div"); wrap.className = "res";
  for (const [name, b64] of Object.entries(d.images || {})) {
    const img = document.createElement("img");
    img.src = "data:image/png;base64," + b64; img.alt = name;
    img.onclick = () => window.open(URL.createObjectURL(b64Blob(b64, "image/png")));
    wrap.appendChild(img);
  }
  const acts = document.createElement("div"); acts.className = "actions";
  for (const [fn, b64] of Object.entries(d.files || {})) {
    const a = document.createElement("a");
    const type = fn.endsWith(".gif") ? "image/gif" : "application/octet-stream";
    a.href = URL.createObjectURL(b64Blob(b64, type)); a.download = fn;
    a.textContent = (fn.endsWith(".dxf") ? "📐 " : fn.endsWith(".xlsx") ? "📊 " : "📎 ") + fn;
    acts.appendChild(a);
  }
  if (current && !CAT.tools[current].photo && current !== "units") {
    const p = document.createElement("button");
    p.textContent = "📄 مذكرة PDF";
    p.onclick = async () => {
      p.disabled = true; p.textContent = "⏳ جاري التجهيز…";
      try {
        const r = await api("/api/pdf", {tool: current, text: lastRun});
        const a = document.createElement("a");
        a.href = URL.createObjectURL(await r.blob()); a.download = `CivilBot_${current}.pdf`; a.click();
        p.textContent = "📄 مذكرة PDF";
      } catch (e) { p.textContent = "⚠️ " + e.message; }
      p.disabled = false;
    };
    acts.appendChild(p);
  }
  if (navigator.share) {
    const s = document.createElement("button");
    s.textContent = "📤 مشاركة";
    s.onclick = async () => {
      const first = Object.values(d.images || {})[0];
      const files = first ? [new File([b64Blob(first, "image/png")], "civilbot.png", {type: "image/png"})] : [];
      try { await navigator.share({title: d.title, text: d.title, files: navigator.canShare?.({files}) ? files : undefined}); } catch (e) {}
    };
    acts.appendChild(s);
  }
  const steps = document.createElement("div"); steps.className = "steps";
  steps.innerHTML = d.summary_html + (d.equation ? `<br><br>🧮 <code>${d.equation}</code>` : "");
  R.append(wrap, acts, steps);
}

async function run() {
  const btn = $("run"); btn.disabled = true;
  $("status").className = ""; $("status").textContent = "⏳ جاري الحساب…";
  const t0 = performance.now();
  try {
    let d;
    if (CAT.tools[current].photo) {
      const f = $("photo").files[0];
      if (!f) throw new Error("اختر صورة أولاً");
      const b64 = await shrink(f);
      d = await (await api("/api/photo", {kind: current, image: b64, caption: $("caption").value})).json();
    } else {
      lastRun = $("input").value.trim();
      if (!lastRun) throw new Error("اكتب المدخلات أو اختر مثال");
      d = await (await api("/api/run", {tool: current, text: lastRun})).json();
      saveHist(current, lastRun, d.title);
    }
    renderResult(d);
    $("status").textContent = `✅ ${((performance.now() - t0) / 1000).toFixed(1)} ث`;
    $("result").scrollIntoView({behavior: "smooth"});
  } catch (e) {
    $("status").className = "err";
    $("status").textContent = "⚠️ " + (navigator.onLine ? e.message : "لا يوجد اتصال بالإنترنت");
  }
  btn.disabled = false;
}

function shrink(file, max = 1600) {
  return new Promise((ok, bad) => {
    const img = new Image();
    img.onload = () => {
      const k = Math.min(1, max / Math.max(img.width, img.height));
      const c = document.createElement("canvas");
      c.width = img.width * k; c.height = img.height * k;
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      ok(c.toDataURL("image/jpeg", 0.88).split(",")[1]);
    };
    img.onerror = bad;
    img.src = URL.createObjectURL(file);
  });
}

function saveHist(t, text, title) {
  const h = JSON.parse(localStorage.getItem("hist") || "[]");
  h.unshift({t, text, title, at: Date.now()});
  localStorage.setItem("hist", JSON.stringify(h.slice(0, 50)));
}

function showHist() {
  const h = JSON.parse(localStorage.getItem("hist") || "[]");
  $("title").textContent = "🕘 السجل";
  $("histList").innerHTML = h.length ? "" : `<p class="note">لا يوجد حسابات بعد</p>`;
  for (const x of h) {
    const d = document.createElement("div"); d.className = "h";
    d.innerHTML = `<b></b><small></small>`;
    d.querySelector("b").textContent = (CAT?.tools[x.t]?.name || x.t) + " · " + new Date(x.at).toLocaleDateString("ar");
    d.querySelector("small").textContent = x.text;
    d.onclick = () => openTool(x.t, x.text);
    $("histList").appendChild(d);
  }
  history.pushState({v: "history"}, "");
  show("history");
}

$("photo").onchange = () => {
  const f = $("photo").files[0];
  if (f) { $("preview").src = URL.createObjectURL(f); $("preview").classList.remove("hidden"); }
};
$("run").onclick = run;
$("input").addEventListener("keydown", (e) => { if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) run(); });
$("search").oninput = (e) => renderHome(e.target.value);
$("back").onclick = () => history.back();
$("histBtn").onclick = showHist;
window.onpopstate = (e) => { if (!e.state || e.state.v === "home") show("home"); };
const net = () => $("offline").classList.toggle("hidden", navigator.onLine);
addEventListener("online", net); addEventListener("offline", net); net();

(async () => {
  try {
    CAT = await (await api("/api/tools")).json();
    localStorage.setItem("catalog", JSON.stringify(CAT));
  } catch (e) {
    CAT = JSON.parse(localStorage.getItem("catalog") || "null");
    if (!CAT) { $("cats").innerHTML = `<p class="err">تعذر الاتصال بالسيرفر</p>`; return; }
  }
  renderHome();
  const t = new URLSearchParams(location.search).get("tool");
  if (t && CAT.tools[t]) openTool(t);
})();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js");
