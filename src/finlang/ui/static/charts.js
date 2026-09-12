/* FinLang Workbench — session charts (SOL-112 queue item 2).
 *
 * Hand-rolled SVG, no Chart.js, no CDN (P5). Everything drawn here comes from
 * data the engine already returned in THIS session (P3) — the charts present
 * artefacts, they never compute new claims. Palette per house_style.py:
 * semantic first (green=pass/agree, amber=attention, pink=the other system),
 * then the cycle for categories.
 */
"use strict";

const FL_CYCLE = ["#3ad6a5", "#ff7a85", "#f5b544", "#7fc4ff", "#c4a7fa",
                  "#0090ff", "#9fb0cf", "#6f82a6"];

/* parts: [{label, value, color?}] -> html string (donut + legend, side by side).
 * Zero-total renders an honest "no data" rather than an empty ring. */
function flDonut(parts, opts = {}) {
  const size = opts.size || 170, hole = opts.hole ?? 0.62;
  const cx = size / 2, cy = size / 2, r = size / 2 - 4;
  const total = parts.reduce((a, p) => a + p.value, 0);
  if (!total) return '<div style="color:#6f82a6;font-size:13px">no data to chart</div>';

  parts = parts.map((p, i) => ({...p, color: p.color || FL_CYCLE[i % FL_CYCLE.length]}));
  let svg = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" role="img" aria-label="${esc(opts.title || "chart")}">`;

  if (parts.filter(p => p.value > 0).length === 1) {
    // a single slice is a circle - the arc path degenerates at 360°
    const p = parts.find(p => p.value > 0);
    svg += `<circle cx="${cx}" cy="${cy}" r="${r * (1 + hole) / 2}" fill="none" stroke="${p.color}" stroke-width="${r * (1 - hole)}"/>`;
  } else {
    let a0 = -Math.PI / 2;
    for (const p of parts) {
      if (!p.value) continue;
      const a1 = a0 + (p.value / total) * Math.PI * 2;
      const large = (a1 - a0) > Math.PI ? 1 : 0;
      const [x0, y0] = [cx + r * Math.cos(a0), cy + r * Math.sin(a0)];
      const [x1, y1] = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)];
      const ir = r * hole;
      const [ix1, iy1] = [cx + ir * Math.cos(a1), cy + ir * Math.sin(a1)];
      const [ix0, iy0] = [cx + ir * Math.cos(a0), cy + ir * Math.sin(a0)];
      svg += `<path d="M${x0},${y0} A${r},${r} 0 ${large} 1 ${x1},${y1} ` +
             `L${ix1},${iy1} A${ir},${ir} 0 ${large} 0 ${ix0},${iy0} Z" ` +
             `fill="${p.color}" stroke="#0d1b3c" stroke-width="1.5"/>`;
      a0 = a1;
    }
  }
  if (opts.centre)
    svg += `<text x="${cx}" y="${cy + 1}" text-anchor="middle" dominant-baseline="middle" ` +
           `fill="#ffffff" font-size="${size / 8}" font-weight="700" ` +
           `font-family="system-ui,'Segoe UI',sans-serif">${esc(opts.centre)}</text>`;
  svg += "</svg>";

  const legend = parts.filter(p => p.value > 0).map(p =>
    `<div style="display:flex;align-items:center;gap:8px;margin:3px 0;font-size:12.5px">` +
    `<span style="width:10px;height:10px;border-radius:2px;background:${p.color};flex:0 0 auto"></span>` +
    `<span style="color:#dbe4f5">${esc(p.label)}</span>` +
    `<span style="color:#6f82a6;font-family:ui-monospace,Consolas,monospace">` +
    `${p.value} · ${Math.round(p.value / total * 100)}%</span></div>`).join("");

  return `<div class="flchart" style="display:flex;align-items:center;gap:22px;flex-wrap:wrap;margin:10px 0">` +
         `${svg}<div>${opts.title ? `<div style="font-family:ui-monospace,Consolas,monospace;` +
         `font-size:11px;letter-spacing:.06em;color:#6f82a6;margin-bottom:6px">${esc(opts.title)}</div>` : ""}` +
         `${legend}</div></div>`;
}

/* Aggregate a column of values into donut parts. Top n, remainder as "other";
 * empty values grouped under emptyLabel in dim grey. */
function flAggregate(values, {top = 7, emptyLabel = "uncategorised"} = {}) {
  const counts = new Map();
  for (const v of values) {
    const k = (v && String(v).trim()) || emptyLabel;
    counts.set(k, (counts.get(k) || 0) + 1);
  }
  const sorted = [...counts.entries()].sort((a, b) => b[1] - a[1]);
  const head = sorted.slice(0, top), tail = sorted.slice(top);
  const parts = head.map(([label, value]) => ({label, value}));
  if (tail.length)
    parts.push({label: `other (${tail.length})`, value: tail.reduce((a, [, v]) => a + v, 0),
                color: "#42527a"});
  const empty = parts.find(p => p.label === emptyLabel);
  if (empty) empty.color = "#6f82a6";
  return parts;
}

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
