const LABELS = {
  lead_vocal: "VOZ", backing_vocals: "CORO", drums: "BATERIA",
  percussion: "PERCUSSÃO", bass: "BAIXO", guitar: "GUITARRA",
  keyboards: "TECLAS", synth: "SINTETIZADOR", woodwinds: "MADEIRAS",
  strings: "CORDAS", brass: "METAIS", other: "OUTRO"
};

const PALETTE = {
  lead_vocal: "#f59bdb", backing_vocals: "#be8eff",
  drums: "#ffbb64", percussion: "#ff905d",
  bass: "#63d8c2", guitar: "#70baff",
  keyboards: "#aaa0ff", synth: "#56dfec",
  woodwinds: "#92ee9c", other: "#e0b4ff",
  strings: "#b9dce6", brass: "#f4c66e"
};

const clamp = (v, low, high) => Math.max(low, Math.min(high, v));
function sampleAt(rows, time) {
  if (!rows?.length) return null;
  if (time <= rows[0].time_seconds) return rows[0];
  if (time >= rows.at(-1).time_seconds) return rows.at(-1);
  let low = 0, high = rows.length - 1;
  while (low + 1 < high) {
    const mid = (low + high) >> 1;
    if (rows[mid].time_seconds <= time) low = mid;
    else high = mid;
  }
  const a = rows[low], b = rows[high];
  const span = b.time_seconds - a.time_seconds || 1;
  const t = clamp((time - a.time_seconds) / span, 0, 1);
  return Object.fromEntries(Object.keys(a).map(key => [
    key,
    typeof a[key] === "number" && typeof b[key] === "number"
      ? a[key] + (b[key] - a[key]) * t
      : a[key]
  ]));
}

function drawStem(context, point, w, h) {
  const az = point.azimuth * Math.PI / 180;
  const el = clamp(point.elevation, -60, 75) * Math.PI / 180;
  const horizontal = Math.sin(az) * Math.cos(el);
  const vertical = Math.sin(el);
  const frontness = Math.cos(az) * Math.cos(el);
  const distanceScale = clamp(1.2 / Math.max(.65, point.distance), .62, 1.34);
  const perspective = clamp(1 + frontness * .10, .88, 1.12);
  const px = w / 2 + horizontal * w * .405 * perspective;
  const py = h * .51 - vertical * h * .365 * perspective;
  const depthScale = distanceScale * (.80 + Math.max(0, frontness) * .26);
  const strength = clamp(Math.sqrt(point.drive / Math.max(point.maxDrive, .00001)), .18, 1);
  const radius = (12 + 7 * strength) * depthScale;
  const color = PALETTE[point.source] || "#b8d9e4";
  const alpha = (.48 + .46 * strength) * (frontness < 0 ? .68 : 1);

  context.save();
  context.globalCompositeOperation = "screen";
  const halo = context.createRadialGradient(px, py, radius * .12, px, py, radius * 3.25);
  halo.addColorStop(0, color + "cc");
  halo.addColorStop(.25, color + "75");
  halo.addColorStop(1, color + "00");
  context.fillStyle = halo;
  context.beginPath();
  context.arc(px, py, radius * 3.25, 0, Math.PI * 2);
  context.fill();

  context.globalAlpha = alpha;
  context.shadowBlur = (18 + 22 * strength) * depthScale;
  context.shadowColor = color;
  context.fillStyle = color;
  context.beginPath();
  context.arc(px, py, radius, 0, Math.PI * 2);
  context.fill();
  context.shadowBlur = 0;

  context.globalAlpha = Math.min(1, alpha + .12);
  context.fillStyle = "#f4ffff";
  context.beginPath();
  context.arc(px - radius * .2, py - radius * .2, radius * .43, 0, Math.PI * 2);
  context.fill();

  const label = LABELS[point.source] || point.source.replaceAll("_", " ").toUpperCase();
  const labelX = px + (horizontal >= 0 ? radius + 7 : -radius - 7);
  context.font = "600 18px Inter, ui-sans-serif, system-ui, sans-serif";
  context.textAlign = horizontal >= 0 ? "left" : "right";
  context.textBaseline = "middle";
  context.globalAlpha = frontness < 0 ? .70 : .94;
  context.shadowBlur = 7;
  context.shadowColor = "#000";
  context.lineWidth = 4;
  context.strokeStyle = "rgba(0, 4, 10, .88)";
  context.strokeText(label, labelX, py);
  context.fillStyle = "#e8f8f7";
  context.fillText(label, labelX, py);
  context.restore();
}

// The map uses the same T007 automation coordinates as the rendered stems.
// Azimuth controls left/right and front/back, elevation controls height,
// and distance controls apparent scale. This is a frontal projection.
export function createSpatialStemMapR29(root, data) {
  if (!root || !Array.isArray(data?.behaviors)) return null;
  const radar = document.querySelector("#spatialStemRadar");
  if (!radar) return null;
  const canvas = radar.querySelector("canvas");
  const context = canvas.getContext("2d");
  const backdrop = new Image();
  backdrop.src = "/spatial-listener-head.svg";
  const toggle = root.querySelector("button");
  const name = root.querySelector(".stem-map-active");
  const status = root.querySelector(".stem-map-status");
  const legend = root.querySelector(".stem-map-legend");
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
  const spatialRoles = new Map();
  fetch("/audio/tukana-spatial-map-positions.json")
    .then(response => {
      if (!response.ok) throw new Error("Spatial coordinates unavailable");
      return response.json();
    })
    .then(scene => {
      for (const source of scene.sources ?? []) {
        spatialRoles.set(source.source_id, source);
      }
    })
    .catch(error => console.error("LAISE spatial map coordinates unavailable:", error));

  let collapsed = false;
  toggle.addEventListener("click", () => {
    collapsed = !collapsed;
    root.classList.toggle("collapsed", collapsed);
    radar.hidden = collapsed;
    toggle.setAttribute("aria-expanded", String(!collapsed));
    toggle.setAttribute("aria-label", collapsed ? "Expandir mapa espacial" : "Recolher mapa espacial");
  });
  let lastDrawn = -Infinity;
  function render(time) {
    if (collapsed || Math.abs(time - lastDrawn) < 1 / 24) return;
    lastDrawn = time;
    const w = canvas.width, h = canvas.height;
    context.clearRect(0, 0, w, h);
    if (backdrop.complete && backdrop.naturalWidth) {
      context.drawImage(backdrop, 0, 0, w, h);
    }

    const active = new Map();
    for (const b of data.behaviors) {
      let drive = 0;
      if (time >= b.startTime && time < b.endTime) {
        const row = sampleAt(b.continuous, time);
        if (row) drive = row[1] || 0;
      }
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
        if (pulse > drive) drive = pulse;
      }
      if (drive <= 0) continue;
      const old = active.get(b.source);
      if (!old || drive > old.drive) active.set(b.source, { source: b.source, drive });
    }

    const sorted = [...active.values()].sort((a, b) => a.drive - b.drive);
    const points = sorted.flatMap(point => {
      const role = spatialRoles.get(point.source);
      if (!role) return [];
      const pose = sampleAt(role.keyframes, time);
      const distance = sampleAt(role.distance_keyframes, time);
      if (!pose || !distance) return [];
      return [{
        ...point,
        azimuth: pose.azimuth_deg_unwrapped,
        elevation: pose.elevation_deg,
        distance: distance.distance_m,
        maxDrive: maxBySource.get(point.source) || .00001
      }];
    });
    for (const point of points) drawStem(context, point, w, h);

    const entries = sorted.map(point => {
      const item = document.createElement("span");
      item.className = "stem-map-legend-item";
      const dot = document.createElement("i");
      dot.style.backgroundColor = PALETTE[point.source] || "#b8d9e4";
      item.append(dot, document.createTextNode(point.source.replaceAll("_", " ")));
      return item;
    });
    legend.replaceChildren(...entries);
    name.textContent = sorted[0]?.source.replaceAll("_", " ") || "—";
    status.textContent = sorted.length + " fontes ativas";
    canvas.setAttribute("aria-label", "Campo binaural frontal: " + points.map(p =>
      p.source.replaceAll("_", " ") + ", azimute " + p.azimuth.toFixed(0) +
      " graus, elevação " + p.elevation.toFixed(0) + " graus, distância " +
      p.distance.toFixed(1)).join("; "));
  }
  return { render };
}
