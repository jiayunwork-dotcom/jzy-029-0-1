// 一维水驱前端：只负责取数和呈现。切线、切点、剖面一律来自后端，本文件不算物理。
"use strict";

const FIELDS = ["mu_w", "mu_o", "swc", "sor", "krw0", "kro0", "nw", "no"];
const $ = (id) => document.getElementById(id);

let lastData = null;

// ---------------------------------------------------------------- 取数与渲染
async function loadProfiles(selectName) {
  const r = await fetch("/api/profiles");
  const body = await r.json();
  const sel = $("profileSelect");
  sel.innerHTML = "";
  for (const name of Object.keys(body.profiles).sort()) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sel.appendChild(opt);
  }
  if (selectName) sel.value = selectName;
}

function fillForm(p) {
  for (const k of FIELDS) $(k).value = p[k];
}

function readForm() {
  const out = {};
  for (const k of FIELDS) out[k] = parseFloat($(k).value);
  return out;
}

function showError(msg) {
  const box = $("error");
  box.style.display = "block";
  box.textContent = msg;
  $("stats").innerHTML = "";
}

function clearError() { $("error").style.display = "none"; }

async function solve(body) {
  clearError();
  const r = await fetch("/api/solve", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) {
    showError(data.detail || "求解失败");
    return;
  }
  lastData = data;
  fillForm(data.params);
  render(data);
}

function render(d) {
  drawFractional(d);
  drawProfile(d);
  const t = d.tangent;
  const p = d.params;
  $("stats").innerHTML = `
    <div><span class="tag">切点 Swf</span><b>${t.swf.toFixed(5)}</b></div>
    <div><span class="tag">f(Swf)</span><b>${t.f_swf.toFixed(5)}</b></div>
    <div><span class="tag">激波速度 V</span><b>${t.shock_speed.toFixed(6)}</b></div>
    <div><span class="tag">切线斜率</span><b>${t.slope.toFixed(6)}</b></div>
    <div><span class="tag">f(Swf)/(Swf−Swc)</span><b>
      ${(t.f_swf / (t.swf - p.swc)).toFixed(6)}</b></div>
    <div><span class="tag">可动区间</span>[${p.swc}, ${p.s_orw.toFixed(4)}]</div>
    <div><span class="tag">末端 f(1−Sor)</span><b>1</b>（硬边界）</div>`;
}

// ---------------------------------------------------------------- Canvas 工具
function prep(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  return {ctx, w, h};
}

function axes(ctx, m, w, h, xmin, xmax, ymin, ymax, xl, yl) {
  const X = (x) => m.l + (x - xmin) / (xmax - xmin) * (w - m.l - m.r);
  const Y = (y) => h - m.b - (y - ymin) / (ymax - ymin) * (h - m.t - m.b);
  ctx.strokeStyle = "#cbd2d9"; ctx.lineWidth = 1; ctx.fillStyle = "#697586";
  ctx.font = "11px sans-serif";
  // 网格与刻度
  for (let i = 0; i <= 5; i++) {
    const gx = xmin + (xmax - xmin) * i / 5;
    const gy = ymin + (ymax - ymin) * i / 5;
    ctx.beginPath(); ctx.moveTo(X(gx), Y(ymin)); ctx.lineTo(X(gx), Y(ymax));
    ctx.globalAlpha = .4; ctx.stroke(); ctx.globalAlpha = 1;
    ctx.fillText(gx.toFixed(2), X(gx) - 12, Y(ymin) + 14);
    ctx.beginPath(); ctx.moveTo(X(xmin), Y(gy)); ctx.lineTo(X(xmax), Y(gy));
    ctx.globalAlpha = .4; ctx.stroke(); ctx.globalAlpha = 1;
    ctx.fillText(gy.toFixed(2), X(xmin) - 30, Y(gy) + 4);
  }
  ctx.strokeStyle = "#1f2933"; ctx.globalAlpha = 1;
  ctx.beginPath(); ctx.moveTo(X(xmin), Y(ymin)); ctx.lineTo(X(xmax), Y(ymin));
  ctx.moveTo(X(xmin), Y(ymin)); ctx.lineTo(X(xmin), Y(ymax)); ctx.stroke();
  ctx.fillStyle = "#334155"; ctx.font = "12px sans-serif";
  ctx.fillText(xl, X(xmax) - 90, h - 6);
  ctx.save(); ctx.translate(14, Y(ymax) + 80); ctx.rotate(-Math.PI / 2);
  ctx.fillText(yl, 0, 0); ctx.restore();
  return {X, Y};
}

// ---------------------------------------------------------------- 分流曲线
function drawFractional(d) {
  const {ctx, w, h} = prep($("fracCanvas"));
  ctx.clearRect(0, 0, w, h);
  const m = {l: 52, r: 18, t: 14, b: 30};
  const p = d.params, t = d.tangent;
  const xmin = p.swc, xmax = 1;
  const {X, Y} = axes(ctx, m, w, h, xmin, xmax, 0, 1, "Sw 含水饱和度", "f 含水率");

  // f(Sw)
  ctx.strokeStyle = "#0b6bcb"; ctx.lineWidth = 2.2;
  ctx.beginPath();
  d.fractional_flow.sw.forEach((s, i) => {
    const fx = X(s), fy = Y(d.fractional_flow.f[i]);
    i ? ctx.lineTo(fx, fy) : ctx.moveTo(fx, fy);
  });
  ctx.stroke();

  // Welge 切线（红色虚线）
  const [a, b] = t.line;
  ctx.strokeStyle = "#d64545"; ctx.setLineDash([7, 5]); ctx.lineWidth = 2;
  ctx.beginPath(); ctx.moveTo(X(a.sw), Y(a.f)); ctx.lineTo(X(b.sw), Y(b.f)); ctx.stroke();
  ctx.setLineDash([]);

  // 切点
  ctx.fillStyle = "#2f9e44";
  ctx.beginPath(); ctx.arc(X(t.swf), Y(t.f_swf), 5, 0, 7); ctx.fill();
  ctx.fillStyle = "#1f2933";
  ctx.fillText(`Swf=${t.swf.toFixed(3)}`, X(t.swf) + 8, Y(t.f_swf) - 8);

  // 末端 1-Sor
  ctx.strokeStyle = "#888"; ctx.setLineDash([3, 4]);
  ctx.beginPath(); ctx.moveTo(X(p.s_orw), Y(0)); ctx.lineTo(X(p.s_orw), Y(1)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#697586";
  ctx.fillText(`1−Sor=${p.s_orw.toFixed(3)}`, X(p.s_orw) - 74, Y(1) + 14);
  // Swc 标注
  ctx.fillText(`Swc=${p.swc}`, X(xmin) - 4, Y(0) + 14);
}

// ---------------------------------------------------------------- 饱和度剖面
function drawProfile(d) {
  const {ctx, w, h} = prep($("profCanvas"));
  ctx.clearRect(0, 0, w, h);
  const m = {l: 52, r: 18, t: 14, b: 30};
  const p = d.params, prof = d.profile;
  const xis = prof.polyline.map(q => q.xi);
  const xmin = 0, xmax = Math.max(...xis) * 1.04;
  const ymin = Math.max(0, p.swc - 0.06), ymax = 1;
  const {X, Y} = axes(ctx, m, w, h, xmin, xmax, ymin, ymax,
                      "ξ = x / t 无因次推进速度", "Sw 含水饱和度");

  // Swc 与 1-Sor 参考线
  ctx.strokeStyle = "#9aa5b1"; ctx.setLineDash([3, 4]); ctx.lineWidth = 1;
  for (const [yy, label] of [[p.swc, `Swc=${p.swc}`],
                             [p.s_orw, `1−Sor=${p.s_orw.toFixed(3)}`]]) {
    ctx.beginPath(); ctx.moveTo(X(xmin), Y(yy)); ctx.lineTo(X(xmax), Y(yy)); ctx.stroke();
    ctx.fillStyle = "#697586"; ctx.fillText(label, X(xmax) - 86, Y(yy) - 4);
  }
  ctx.setLineDash([]);

  // 稀疏波高亮段（绿色）
  ctx.strokeStyle = "#2f9e44"; ctx.lineWidth = 6; ctx.globalAlpha = .25;
  ctx.beginPath();
  prof.rarefaction.forEach((q, i) => {
    i ? ctx.lineTo(X(q.xi), Y(q.sw)) : ctx.moveTo(X(q.xi), Y(q.sw));
  });
  ctx.stroke(); ctx.globalAlpha = 1;

  // 完整折线（含激波竖直段）
  ctx.strokeStyle = "#0b6bcb"; ctx.lineWidth = 2.2;
  ctx.beginPath();
  prof.polyline.forEach((q, i) => {
    i ? ctx.lineTo(X(q.xi), Y(q.sw)) : ctx.moveTo(X(q.xi), Y(q.sw));
  });
  ctx.stroke();

  // 激波位置红色竖线标注
  const v = d.tangent.shock_speed;
  ctx.strokeStyle = "#d64545"; ctx.setLineDash([6, 4]); ctx.lineWidth = 1.6;
  ctx.beginPath(); ctx.moveTo(X(v), Y(ymin)); ctx.lineTo(X(v), Y(ymax)); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#d64545";
  ctx.fillText(`激波 ξ=V=${v.toFixed(4)}`, X(v) + 6, Y(ymax) + 12);
  ctx.fillText(`Swf=${d.tangent.swf.toFixed(4)}`, X(v) + 6,
               Y(d.tangent.swf) - 8);
}

// ---------------------------------------------------------------- 交互
async function refresh() {
  const name = $("profileSelect").value;
  if (name) {
    const r = await fetch(`/api/solve/${encodeURIComponent(name)}`);
    const data = await r.json();
    if (!r.ok) { showError(data.detail || "求解失败"); return; }
    lastData = data;
    fillForm(data.params);
    render(data);
    clearError();
  }
}

async function saveAsProfile() {
  const name = window.prompt("给这组物性起个档名（英文/数字）：", "my_case");
  if (!name) return;
  const r = await fetch(`/api/profiles/${encodeURIComponent(name)}`, {
    method: "PUT",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({name, ...readForm()}),
  });
  const data = await r.json();
  if (!r.ok) { showError((data.detail || "存档失败") +
      (data.errors ? "\n" + JSON.stringify(data.errors) : "")); return; }
  await loadProfiles(name);
  await refresh();
}

window.addEventListener("resize", () => { if (lastData) render(lastData); });
$("profileSelect").addEventListener("change", refresh);
$("solveInline").addEventListener("click", () => solve({params: readForm()}));
$("saveProfile").addEventListener("click", saveAsProfile);

(async function init() {
  await loadProfiles("symmetric");
  await refresh();
})();
