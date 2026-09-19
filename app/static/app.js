/* 一维水驱剖面台 —— 纯展示前端。
 * 物性、切点、激波速度全部来自后端 /api/solve；本文件绝不求解切线。
 */
"use strict";

const FIELDS = ["mu_w", "mu_o", "swc", "sor", "krw0", "kro0", "nw", "no"];

const els = {};
FIELDS.forEach((f) => (els[f] = document.getElementById(f)));
els.deck = document.getElementById("deck-select");
els.btn = document.getElementById("solve-btn");
els.saveBtn = document.getElementById("save-btn");
els.err = document.getElementById("error");
els.summary = document.getElementById("summary");
els.ratio = document.getElementById("ratio-mu");

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text != null) node.textContent = text;
  return node;
}

/* ---------- minimal line chart ---------- */
function lineChart(container, { width = 560, height = 380, margin = { t: 18, r: 18, b: 44, l: 52 },
                               xlabel = "", ylabel = "", xDomain, yDomain,
                               series = [], vlines = [], points = [], tags = [] }) {
  container.textContent = "";
  const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}` });
  const [x0, x1] = xDomain, [y0, y1] = yDomain;
  const px = (x) => margin.l + ((x - x0) / (x1 - x0)) * (width - margin.l - margin.r);
  const py = (y) => height - margin.b - ((y - y0) / (y1 - y0)) * (height - margin.t - margin.b);
  const nx = 5, ny = 5;

  for (let i = 0; i <= nx; i++) {
    const xv = x0 + (i / nx) * (x1 - x0);
    svg.appendChild(svgEl("line", { class: "gridline", x1: px(xv), x2: px(xv), y1: margin.t, y2: height - margin.b }));
    const t = svgEl("text", { x: px(xv), y: height - margin.b + 16, "text-anchor": "middle" }, xv.toFixed(2));
    svg.appendChild(t);
  }
  for (let j = 0; j <= ny; j++) {
    const yv = y0 + (j / ny) * (y1 - y0);
    svg.appendChild(svgEl("line", { class: "gridline", x1: margin.l, x2: width - margin.r, y1: py(yv), y2: py(yv) }));
    svg.appendChild(svgEl("text", { x: margin.l - 7, y: py(yv) + 4, "text-anchor": "end" }, yv.toFixed(2)));
  }
  // axes
  svg.appendChild(svgEl("line", { x1: margin.l, x2: width - margin.r, y1: py(y0), y2: py(y0), stroke: "#94a3b2" }));
  svg.appendChild(svgEl("line", { x1: px(x0), x2: px(x0), y1: margin.t, y2: height - margin.b, stroke: "#94a3b2" }));
  svg.appendChild(svgEl("text", { x: (margin.l + width - margin.r) / 2, y: height - 6, "text-anchor": "middle", class: "tag" }, xlabel));
  const yl = svgEl("text", { x: 14, y: (margin.t + height - margin.b) / 2, "text-anchor": "middle",
                             class: "tag", transform: `rotate(-90 14 ${(margin.t + height - margin.b) / 2})` }, ylabel);
  svg.appendChild(yl);

  vlines.forEach(({ x, cls = "vmark" }) => {
    svg.appendChild(svgEl("line", { class: cls, x1: px(x), x2: px(x), y1: margin.t, y2: height - margin.b }));
  });

  series.forEach(({ xs, ys, cls }) => {
    const d = xs.map((x, i) => `${i === 0 ? "M" : "L"}${px(x).toFixed(2)},${py(ys[i]).toFixed(2)}`).join("");
    svg.appendChild(svgEl("path", { class: cls, d }));
  });

  points.forEach(({ x, y, cls = "dot", r = 4.5 }) => {
    svg.appendChild(svgEl("circle", { class: cls, cx: px(x), cy: py(y), r }));
  });

  tags.forEach(({ x, y, text, anchor = "start", dx = 7, dy = -7 }) => {
    svg.appendChild(svgEl("text", { class: "tag", x: px(x) + dx, y: py(y) + dy, "text-anchor": anchor }, text));
  });

  container.appendChild(svg);
}

/* ---------- data plumbing ---------- */
function readForm() {
  const p = {};
  FIELDS.forEach((f) => (p[f] = parseFloat(els[f].value)));
  return p;
}
function fillForm(p) {
  FIELDS.forEach((f) => (els[f].value = p[f]));
  updateRatio();
}
function updateRatio() {
  const w = parseFloat(els.mu_w.value), o = parseFloat(els.mu_o.value);
  els.ratio.textContent = w > 0 && o > 0 ? (w / o).toFixed(3) : "–";
}
FIELDS.forEach((f) => els[f].addEventListener("input", updateRatio));

function showError(msg) {
  els.err.hidden = false;
  els.err.textContent = msg;
}
function clearError() {
  els.err.hidden = true;
  els.err.textContent = "";
}

function render(data) {
  const { swc, sw_max } = data.mobile_interval;

  lineChart(document.getElementById("chart-ff"), {
    xlabel: "含水饱和度 Sw", ylabel: "含水率 f(Sw)",
    xDomain: [Math.max(0, swc - 0.04), Math.min(1, sw_max + 0.04)],
    yDomain: [-0.02, 1.12],
    series: [
      { xs: data.fractional_curve.sw, ys: data.fractional_curve.f, cls: "fcurve" },
      { xs: data.tangent.sw, ys: data.tangent.f, cls: "tangent" },
    ],
    vlines: [
      { x: data.swf },
      { x: sw_max },
    ],
    points: [
      { x: swc, y: 0, cls: "enddot" },
      { x: data.swf, y: data.f_swf, cls: "dot" },
      { x: sw_max, y: 1, cls: "enddot" },
    ],
    tags: [
      { x: swc, y: 0, text: "(Swc, 0)", dx: 6, dy: 16 },
      { x: data.swf, y: data.f_swf, text: `切点 Swf=${data.swf.toFixed(4)}` },
      { x: sw_max, y: 1, text: `1−Sor=${sw_max.toFixed(3)}`, anchor: "end", dx: -6 },
    ],
  });

  lineChart(document.getElementById("chart-prof"), {
    xlabel: "无因次速度 ξ = (φ x)/(u t)", ylabel: "含水饱和度 Sw",
    xDomain: [0, data.shock_speed * 1.25],
    yDomain: [Math.max(0, swc - 0.06), 1.02],
    series: [
      { xs: data.profile.xi, ys: data.profile.sw, cls: "profile" },
    ],
    vlines: [{ x: data.shock_speed }],
    points: [
      { x: data.shock_speed, y: data.swf, cls: "dot" },
      { x: data.shock_speed, y: swc, cls: "dot" },
    ],
    tags: [
      { x: data.shock_speed, y: data.swf, text: `激波 ξ_f=${data.shock_speed.toFixed(4)}`, dx: -8, anchor: "end", dy: -8 },
      { x: 0, y: sw_max, text: `1−Sor=${sw_max.toFixed(3)}`, dx: 6 },
      { x: data.shock_speed * 1.24, y: swc, text: "Swc", anchor: "end", dx: 0, dy: -6 },
    ],
  });

  const swcV = data.params.swc;
  els.summary.innerHTML = `<table>
    <tr><td>切点 Swf</td><td>${data.swf.toFixed(6)}</td></tr>
    <tr><td>f(Swf)</td><td>${data.f_swf.toFixed(6)}</td></tr>
    <tr><td>激波速度 ξ_f = f(Swf)/(Swf−Swc)</td><td>${data.shock_speed.toFixed(6)}</td></tr>
    <tr><td>切线斜率</td><td>${data.tangent_slope.toFixed(6)}</td></tr>
    <tr><td>末端 1−Sor</td><td>${sw_max.toFixed(6)}</td></tr>
    <tr><td>斜率恒等式残差</td><td>${data.residuals.slope_identity.toExponential(2)}</td></tr>
  </table>`;
}

async function solveWith(body) {
  clearError();
  const r = await fetch("/api/solve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const j = await r.json();
  if (!r.ok) {
    showError(j.detail || `求解失败 (${r.status})`);
    return null;
  }
  render(j);
  if (j.deck) els.deck.value = j.deck;
  return j;
}

async function loadDecks(selectName) {
  const r = await fetch("/api/decks");
  const j = await r.json();
  els.deck.textContent = "";
  Object.keys(j.decks).forEach((name) => {
    const o = document.createElement("option");
    o.value = name;
    o.textContent = name;
    els.deck.appendChild(o);
  });
  if (selectName) els.deck.value = selectName;
}

els.deck.addEventListener("change", async () => {
  const name = els.deck.value;
  if (!name) return;
  const r = await fetch(`/api/decks/${encodeURIComponent(name)}`);
  const j = await r.json();
  fillForm(j.params);
  await solveWith({ name });
});

els.btn.addEventListener("click", async () => {
  await solveWith({ params: readForm() });
});

els.saveBtn.addEventListener("click", async () => {
  const name = prompt("给这档物性起个名字（字母/数字/_-.）：");
  if (!name) return;
  clearError();
  const r = await fetch(`/api/decks/${encodeURIComponent(name)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(readForm()),
  });
  const j = await r.json();
  if (!r.ok) { showError(j.detail || `保存失败 (${r.status})`); return; }
  await loadDecks(name);
});

(async function init() {
  await loadDecks("default");
  const r = await fetch("/api/decks/default");
  fillForm((await r.json()).params);
  await solveWith({ name: "default" });
})();
