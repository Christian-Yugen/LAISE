const LABELS = {
  lead_vocal: "VOZ", backing_vocals: "CORO", drums: "DRUM",
  percussion: "PERC", bass: "BASS", guitar: "GTR",
  keyboards: "KEYS", synth: "SYN", woodwinds: "WIND", other: "OTH"
};

const PALETTE = {
  lead_vocal: "#f59bdb", backing_vocals: "#be8eff",
  drums: "#ffbb64", percussion: "#ff905d",
  bass: "#63d8c2", guitar: "#70baff",
  keyboards: "#aaa0ff", synth: "#56dfec",
  woodwinds: "#92ee9c", other: "#e0b4ff"
};

const clamp = (v, low, high) => Math.max(low, Math.min(high, v));
function sampleAt(rows, time) {
  if (!rows?.length || time < rows[0][0]) return null;
  let low = 0, high = rows.length - 1;
  while (low < high) {
    const mid = Math.ceil((low + high) / 2);
    if (rows[mid][0] <= time) low = mid;
    else high = mid - 1;
  }
  return rows[low];
}

// Uses the same behavior runtime as the visible stem field. Its X/Z map
// is a horizontal spatial projection, not an inferred elevation measurement.
export function createSpatialStemMapR29(root, data) {
  if (!root || !Array.isArray(data?.behaviors)) return null;
  const canvas = root.querySelector("canvas");
  const context = canvas.getContext("2d");
  const toggle = root.querySelector("button");
  const name = root.querySelector(".stem-map-active");
  const status = root.querySelector(".stem-map-status");
  const sources = [...new Set(data.behaviors.map(b => b.source))].sort();
  const maxBySource = new Map(sources.map(source => [source, 0]));
  for (const b of data.behaviors) {
    for (const row of b.continuous ?? []) {
      maxBySource.set(b.source, Math.max(maxBySource.get(b.source), row[1] || 0));
    }
    for (const attack of b.attacks ?? []) {
      maxBySource.set(b.source, Math.max(maxBySource.get(b.source),
        attack.sourceDrive || attack.drive || 0));
    }
  }
  const attacksByBehavior = new Map(data.behaviors.map(b =>
    [b, [...(b.attacks ?? [])].sort((a, c) => a.time - c.time)]));
  let collapsed = false;
  toggle.addEventListener("click", () => {
    collapsed = !collapsed;
    root.classList.toggle("collapsed", collapsed);
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Expandir mapa espacial" : "Recolher mapa espacial");
  });
  let lastDrawn = -Infinity;
  function render(time) {
    if (collapsed || Math.abs(time - lastDrawn) < 1 / 24) return;
    lastDrawn = time;
    const w = canvas.width, h = canvas.height;
    const cx = w / 2, cy = h / 2 + 2, radius = Math.min(w, h) * .38;
    context.clearRect(0, 0, w, h);
    context.lineWidth = 1;
    for (const fraction of [0.28, 0.56, 0.82, 1]) {
      context.beginPath();
      context.arc(cx, cy, radius * fraction, 0, Math.PI * 2);
      context.strokeStyle = fraction === 1 ? "rgba(130,211,218,.44)"
        : "rgba(130,211,218,.19)";
      context.stroke();
    }
    context.strokeStyle = "rgba(130,211,218,.15)";
    context.beginPath();
    context.moveTo(cx - radius, cy); context.lineTo(cx + radius, cy);
    context.moveTo(cx, cy - radius); context.lineTo(cx, cy + radius);
    context.stroke();

    const active = new Map();
    for (const b of data.behaviors) {
      let drive = 0, x = 0, z = 0;
      if (time >= b.startTime && time < b.endTime) {
        const row = sampleAt(b.continuous, time);
        if (row) { drive = row[1] || 0; x = row[2] || 0; z = row[3] || 0; }
      }
      // Discrete instruments remain visible briefly at their recorded
      // attack location, including when they have no sustained row.
      const attacks = attacksByBehavior.get(b);
      let lo = 0, hi = attacks.length;
      while (lo < hi) {
        const mid = (lo + hi) >> 1;
        if (attacks[mid].time < time - 0.35) lo = mid + 1;
        else hi = mid;
      }
      for (let i = lo; i < attacks.length && attacks[i].time <= time; i++) {
        const a = attacks[i];
        const age = time - a.time;
        const pulse = (a.sourceDrive || a.drive || 0) * Math.exp(-age / 0.17);
        if (pulse > drive) { drive = pulse; x = a.x || 0; z = a.z || 0; }
      }
      if (drive <= 0) continue;
      const old = active.get(b.source);
      if (!old || drive > old.drive) active.set(b.source, { source: b.source, drive, x, z });
    }
    const sorted = [...active.values()].sort((a, b) => b.drive - a.drive);
    for (const point of sorted.slice().reverse()) {
      const full = Math.max(maxBySource.get(point.source) || 0, 0.00001);
      const strength = clamp(Math.sqrt(point.drive / full), 0.12, 1);
      const px = cx + clamp(point.x, -1, 1) * radius * .90;
      const py = cy + clamp(point.z, -1, 1) * radius * .90;
      const color = PALETTE[point.source] || "#b8d9e4";
      context.beginPath();
      context.arc(px, py, 20 + 16 * strength, 0, Math.PI * 2);
      context.fillStyle = color;
      context.globalAlpha = .13 + .22 * strength;
      context.fill();
      context.globalAlpha = 1;
      context.beginPath();
      context.arc(px, py, 10 + 9 * strength, 0, Math.PI * 2);
      context.fillStyle = color;
      context.shadowBlur = 12 + 22 * strength;
      context.shadowColor = color;
      context.fill();
      context.shadowBlur = 0;
      context.font = "bold 18px system-ui, sans-serif";
      context.textAlign = px > cx + radius * .4 ? "right" : "left";
      context.textBaseline = "middle";
      context.fillStyle = "#e9f7f4";
      context.shadowColor = "#020812";
      context.shadowBlur = 6;
      context.fillText(LABELS[point.source] || point.source.slice(0, 4).toUpperCase(),
        px + (context.textAlign === "right" ? -16 : 16), py - 15);
      context.shadowBlur = 0;
    }
    context.beginPath();
    context.arc(cx, cy, 7, 0, Math.PI * 2);
    context.fillStyle = "#e7eee9";
    context.fill();
    context.beginPath();
    context.arc(cx, cy + 12, 9, Math.PI, 0);
    context.strokeStyle = "#e7eee9";
    context.stroke();
    name.textContent = sorted[0]?.source.replaceAll("_", " ") || "—";
    status.textContent = sorted.length + " fontes ativas";
    canvas.setAttribute("aria-label", "Mapa X/Z: " + sorted.map(p =>
      p.source.replaceAll("_", " ") + " em X " + p.x.toFixed(1) +
      ", Z " + p.z.toFixed(1)).join("; "));
  }
  return { render };
}
