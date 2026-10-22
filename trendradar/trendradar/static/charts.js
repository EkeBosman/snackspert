/* Kleine SVG-grafieken zonder externe library: sparkline, lijngrafiek, staven. */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const tip = () => document.getElementById("tooltip");

  function el(name, attrs, parent) {
    const n = document.createElementNS(NS, name);
    for (const [k, v] of Object.entries(attrs || {})) n.setAttribute(k, v);
    if (parent) parent.appendChild(n);
    return n;
  }

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function showTip(evt, html) {
    const t = tip();
    t.innerHTML = html;
    t.hidden = false;
    const pad = 14;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    const r = t.getBoundingClientRect();
    if (x + r.width > window.innerWidth - 8) x = evt.clientX - r.width - pad;
    if (y + r.height > window.innerHeight - 8) y = evt.clientY - r.height - pad;
    t.style.left = x + "px";
    t.style.top = y + "px";
  }
  function hideTip() { tip().hidden = true; }

  function niceMax(v) {
    if (v <= 4) return 4;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
    return v;
  }

  /* Sparkline: grijs voor de vergelijkingsperiode, kleur voor de huidige. */
  function sparkline(series, currentFrom, opts = {}) {
    const w = opts.width || 110, h = opts.height || 28;
    const svg = el("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, "aria-hidden": "true" });
    svg.style.width = w + "px";
    const max = Math.max(1, ...series);
    const n = series.length;
    const x = i => (n === 1 ? w / 2 : (i / (n - 1)) * (w - 4) + 2);
    const y = v => h - 3 - (v / max) * (h - 6);
    const pts = series.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    if (currentFrom > 0) {
      el("polyline", { points: pts.slice(0, currentFrom + 1).join(" "), fill: "none",
        stroke: "var(--muted)", "stroke-width": 1.5, "stroke-opacity": 0.55, "stroke-linejoin": "round" }, svg);
    }
    el("polyline", { points: pts.slice(Math.max(0, currentFrom)).join(" "), fill: "none",
      stroke: "var(--accent)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    const last = n - 1;
    el("circle", { cx: x(last), cy: y(series[last]), r: 2.5, fill: "var(--accent)" }, svg);
    return svg;
  }

  function fmtBucket(iso, hours) {
    const d = new Date(iso);
    const day = d.toLocaleDateString("nl-NL", { weekday: "short", day: "numeric", month: "short" });
    if (hours >= 24) return day;
    return day + " " + d.toLocaleTimeString("nl-NL", { hour: "2-digit", minute: "2-digit" });
  }

  /* Lijngrafiek met meerdere reeksen, gedeelde y-as, kruisdraad + tooltip. */
  function lineChart(container, labels, seriesMap, opts = {}) {
    container.innerHTML = "";
    const keys = Object.keys(seriesMap);
    if (!labels.length || !keys.length || keys.every(k => seriesMap[k].every(v => !v))) {
      container.innerHTML = '<div class="empty">Nog geen data in deze periode.</div>';
      return;
    }
    const names = opts.names || {};
    const colors = opts.colors || {};
    if (keys.length > 1) {
      const lg = document.createElement("div");
      lg.className = "legend";
      lg.innerHTML = keys.map(k => `<span><i style="--c:${colors[k]}"></i>${esc(names[k] || k)}</span>`).join("");
      container.appendChild(lg);
    }
    const W = Math.max(320, container.clientWidth || 600), H = opts.height || 220;
    const m = { l: opts.fmtTick ? 44 : 34, r: 10, t: 10, b: 26 };
    const fmtLabel = opts.fmtLabel || (v => fmtBucket(v, opts.bucketHours || 24));
    const fmtTick = opts.fmtTick || (v => Math.round(v));
    const fmtValue = opts.fmtValue || (v => v);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img",
      "aria-label": opts.label || "Lijngrafiek" }, container);
    const n = labels.length;
    const max = niceMax(Math.max(...keys.flatMap(k => seriesMap[k])));
    const x = i => m.l + (n === 1 ? 0 : (i / (n - 1)) * (W - m.l - m.r));
    const y = v => H - m.b - (v / max) * (H - m.t - m.b);

    if (opts.currentFrom != null && opts.currentFrom > 0) {
      const x0 = x(Math.max(0, opts.currentFrom - 0.5));
      el("rect", { x: x0, y: m.t, width: W - m.r - x0, height: H - m.t - m.b,
        fill: "var(--surface-2)" }, svg);
      const t = el("text", { x: x0 + 6, y: m.t + 12 }, svg);
      t.textContent = "gekozen periode";
    }
    const div = max % 4 === 0 ? 4 : 5;
    for (let i = 0; i <= div; i++) {
      const v = (max / div) * i;
      el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "gridline" }, svg);
      const t = el("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }, svg);
      t.textContent = fmtTick(v);
    }
    const ticks = Math.min(W < 520 ? 3 : 6, n);
    for (let k = 0; k < ticks; k++) {
      const i = Math.round((k / Math.max(1, ticks - 1)) * (n - 1));
      const t = el("text", { x: x(i), y: H - 8, "text-anchor": k === 0 ? "start" : k === ticks - 1 ? "end" : "middle" }, svg);
      t.textContent = fmtLabel(labels[i]);
    }
    for (const k of keys) {
      // Ontbrekende waarden (null) onderbreken de lijn.
      let d = "", pen = false;
      seriesMap[k].forEach((v, i) => {
        if (v == null) { pen = false; return; }
        d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        pen = true;
      });
      el("path", { d, fill: "none", stroke: colors[k] || "var(--accent)", "stroke-width": 2,
        "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    }
    const cross = el("line", { y1: m.t, y2: H - m.b, stroke: "var(--muted)", "stroke-dasharray": "3 3", visibility: "hidden" }, svg);
    const dots = keys.map(k => el("circle", { r: 4, fill: colors[k] || "var(--accent)",
      stroke: "var(--surface)", "stroke-width": 2, visibility: "hidden" }, svg));
    const hit = el("rect", { x: m.l, y: m.t, width: W - m.l - m.r, height: H - m.t - m.b, fill: "transparent" }, svg);
    hit.addEventListener("mousemove", evt => {
      const box = svg.getBoundingClientRect();
      const px = ((evt.clientX - box.left) / box.width) * W;
      const i = Math.max(0, Math.min(n - 1, Math.round(((px - m.l) / (W - m.l - m.r)) * (n - 1))));
      cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("visibility", "visible");
      keys.forEach((k, j) => {
        const v = seriesMap[k][i];
        dots[j].setAttribute("cx", x(i)); dots[j].setAttribute("cy", y(v || 0));
        dots[j].setAttribute("visibility", v == null ? "hidden" : "visible");
      });
      const rows = keys.filter(k => seriesMap[k][i] != null).map(k => `<div class="t-row"><span><i style="--c:${colors[k]}"></i>${esc(names[k] || k)}</span><b>${esc(fmtValue(seriesMap[k][i]))}</b></div>`).join("");
      showTip(evt, `<div class="t-head">${esc(fmtLabel(labels[i]))}</div>${rows}`);
    });
    hit.addEventListener("mouseleave", () => {
      cross.setAttribute("visibility", "hidden");
      dots.forEach(d => d.setAttribute("visibility", "hidden"));
      hideTip();
    });
  }

  /* Horizontale staven: huidige periode vs. gemiddelde van de periodes ervoor. */
  function compareBars(container, rows, opts = {}) {
    container.innerHTML = "";
    if (!rows.length) {
      container.innerHTML = '<div class="empty">Nog geen data in deze periode.</div>';
      return;
    }
    const lg = document.createElement("div");
    lg.className = "legend";
    lg.innerHTML = `<span><i style="--c:var(--seq-3)"></i>Gekozen periode</span><span><i style="--c:var(--seq-1)"></i>Gemiddelde periode ervoor</span>`;
    container.appendChild(lg);
    const W = Math.max(320, container.clientWidth || 500);
    const labelW = Math.min(170, W * 0.38), rowH = 30, barH = 9;
    const H = rows.length * rowH + 6;
    const max = niceMax(Math.max(...rows.flatMap(r => [r.cur, r.base])));
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.label || "Staafgrafiek" }, container);
    const x = v => (v / max) * (W - labelW - 50);
    rows.forEach((r, i) => {
      const y0 = i * rowH + 4;
      const t = el("text", { x: 0, y: y0 + 15 }, svg);
      t.textContent = r.name.length > 26 ? r.name.slice(0, 25) + "…" : r.name;
      t.setAttribute("style", "fill: var(--text-2); font-size: 12px");
      const g = el("g", {}, svg);
      el("rect", { x: labelW, y: y0 + 1, width: Math.max(2, x(r.cur)), height: barH, rx: 3, fill: "var(--seq-3)" }, g);
      el("rect", { x: labelW, y: y0 + barH + 3, width: Math.max(2, x(r.base)), height: barH, rx: 3, fill: "var(--seq-1)" }, g);
      const v = el("text", { x: labelW + Math.max(x(r.cur), x(r.base)) + 6, y: y0 + 15 }, svg);
      v.textContent = r.cur;
      v.setAttribute("style", "fill: var(--text); font-size: 12px; font-weight: 600");
      const hit = el("rect", { x: 0, y: y0 - 2, width: W, height: rowH, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", evt => showTip(evt,
        `<div class="t-head">${esc(r.name)}</div>
         <div class="t-row"><span><i style="--c:var(--seq-3)"></i>Gekozen periode</span><b>${r.cur}</b></div>
         <div class="t-row"><span><i style="--c:var(--seq-1)"></i>Gemiddeld ervoor</span><b>${r.base}</b></div>`));
      hit.addEventListener("mouseleave", hideTip);
      if (opts.onClick) { hit.style.cursor = "pointer"; hit.addEventListener("click", () => opts.onClick(r)); }
    });
  }

  /* Staafjes per tijdsblok voor één onderwerp. */
  function columnChart(container, labels, values, opts = {}) {
    container.innerHTML = "";
    if (!values.some(v => v)) {
      container.innerHTML = '<div class="empty">Geen posts in deze periode.</div>';
      return;
    }
    const W = Math.max(320, container.clientWidth || 560), H = opts.height || 180;
    const m = { l: opts.fmtTick ? 44 : 30, r: 6, t: 8, b: 24 };
    const fmtLabel = opts.fmtLabel || (v => fmtBucket(v, opts.bucketHours || 24));
    const fmtTick = opts.fmtTick || (v => Math.round(v));
    const fmtValue = opts.fmtValue || (v => v);
    const n = values.length;
    const max = niceMax(Math.max(...values));
    const bw = (W - m.l - m.r) / n;
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": opts.label || "Posts per tijdsblok" }, container);
    const y = v => H - m.b - (v / max) * (H - m.t - m.b);
    const div = max % 4 === 0 ? 4 : 5;
    for (let i = 0; i <= div; i++) {
      const v = (max / div) * i;
      el("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), class: "gridline" }, svg);
      const t = el("text", { x: m.l - 6, y: y(v) + 4, "text-anchor": "end" }, svg);
      t.textContent = fmtTick(v);
    }
    values.forEach((v, i) => {
      const cur = opts.currentFrom != null && i >= opts.currentFrom;
      const h = Math.max(v ? 2 : 0, H - m.b - y(v));
      el("rect", { x: m.l + i * bw + 1, y: H - m.b - h, width: Math.max(1, bw - 2), height: h, rx: Math.min(4, bw / 3),
        fill: cur ? "var(--accent)" : "var(--seq-2)", "fill-opacity": cur ? 1 : 0.6 }, svg);
      const hit = el("rect", { x: m.l + i * bw, y: m.t, width: bw, height: H - m.t - m.b, fill: "transparent" }, svg);
      hit.addEventListener("mousemove", evt => showTip(evt,
        `<div class="t-head">${esc(fmtLabel(labels[i]))}</div><div class="t-row"><span>${esc(opts.valueName || "Posts")}</span><b>${esc(fmtValue(v))}</b></div>`));
      hit.addEventListener("mouseleave", hideTip);
    });
    [0, n - 1].forEach((i, k) => {
      const t = el("text", { x: k ? W - m.r : m.l, y: H - 7, "text-anchor": k ? "end" : "start" }, svg);
      t.textContent = opts.fmtLabel ? fmtLabel(labels[i]) : fmtBucket(labels[i], 24);
    });
  }

  window.Charts = { sparkline, lineChart, compareBars, columnChart, esc, showTip, hideTip };
})();
