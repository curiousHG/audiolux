"use strict";
const $ = (id) => document.getElementById(id);
function status(t, ok) { const s = $("status"); s.textContent = t; s.style.color = ok ? "#5aa9ff" : "#e0667a"; }
async function api(u) {
  try { const j = await (await fetch(u)).json(); status(j.ok ? "✓ " + (j.sent || "ok") : "✗ " + j.error, j.ok); return j; }
  catch (e) { status("✗ " + e, false); }
}

// ---------- swatches + colour picker ----------
["#ff0000", "#ff7a00", "#ffd400", "#33ff00", "#00ffd0", "#0066ff", "#a000ff", "#ffffff"].forEach((c) => {
  const d = document.createElement("div");
  d.className = "sw"; d.style.background = c;
  d.onclick = () => { $("col").value = c; pickColor(c); };
  $("sw").appendChild(d);
});
function pickColor(hex) { api("/api/color?hex=" + hex.replace("#", "")); }

// ---------- HSV colour wheel ----------
function hsv2rgb(h, s, v) {
  const c = v * s, x = c * (1 - Math.abs((h / 60) % 2 - 1)), m = v - c; let r, g, b;
  if (h < 60)[r, g, b] = [c, x, 0]; else if (h < 120)[r, g, b] = [x, c, 0];
  else if (h < 180)[r, g, b] = [0, c, x]; else if (h < 240)[r, g, b] = [0, x, c];
  else if (h < 300)[r, g, b] = [x, 0, c]; else[r, g, b] = [c, 0, x];
  return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
}
const hx = (n) => n.toString(16).padStart(2, "0");
(function () {
  const cv = $("wheel"), ctx = cv.getContext("2d"), mk = $("marker"), SZ = 200, R = SZ / 2;
  cv.width = SZ; cv.height = SZ;
  const img = ctx.createImageData(SZ, SZ);
  for (let y = 0; y < SZ; y++) for (let x = 0; x < SZ; x++) {
    const dx = x - R, dy = y - R, d = Math.hypot(dx, dy), i = (y * SZ + x) * 4;
    if (d > R) { img.data[i + 3] = 0; continue; }
    let h = Math.atan2(dy, dx) * 180 / Math.PI; if (h < 0) h += 360;
    const [r, g, b] = hsv2rgb(h, Math.min(1, d / R), 1);
    img.data[i] = r; img.data[i + 1] = g; img.data[i + 2] = b; img.data[i + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  let drag = false, last = 0, pend = null;
  const flush = () => { if (pend) { api("/api/color?hex=" + pend); pend = null; } };
  function pick(e) {
    const rc = cv.getBoundingClientRect();
    let x = e.clientX - rc.left, y = e.clientY - rc.top, dx = x - R, dy = y - R, d = Math.hypot(dx, dy);
    if (d > R) { dx *= R / d; dy *= R / d; x = R + dx; y = R + dy; d = R; }
    let h = Math.atan2(dy, dx) * 180 / Math.PI; if (h < 0) h += 360;
    const [r, g, b] = hsv2rgb(h, Math.min(1, d / R), 1), hex = hx(r) + hx(g) + hx(b);
    mk.style.left = x + "px"; mk.style.top = y + "px"; $("col").value = "#" + hex; pend = hex;
    const now = Date.now(); if (now - last > 80) { last = now; flush(); }
  }
  cv.addEventListener("pointerdown", (e) => { drag = true; cv.setPointerCapture(e.pointerId); pick(e); });
  cv.addEventListener("pointermove", (e) => { if (drag) pick(e); });
  cv.addEventListener("pointerup", () => { drag = false; flush(); });
})();

// ---------- effect modes (grouped + fwd/bwd) ----------
let EFFECTS = [], NUM2NAME = {}, fwd = true;
async function loadModes() {
  const j = await (await fetch("/api/modes")).json();
  let html = ""; EFFECTS = []; NUM2NAME = {};
  (j.groups || []).forEach((g) => {
    html += `<optgroup label="${g.family}">`;
    g.effects.forEach((e) => {
      html += `<option value="${EFFECTS.length}">${e.name}</option>`; EFFECTS.push(e);
      ["fwd", "bwd", "open", "close", "single"].forEach((k) => { if (k in e) NUM2NAME[e[k]] = e.name; });
    });
    html += "</optgroup>";
  });
  $("modeSel").innerHTML = html; applyMode(true);
}
function setDir(f) { fwd = !!f; $("fwdBtn").classList.toggle("on", fwd); $("bwdBtn").classList.toggle("on", !fwd); applyMode(); }
function applyMode(silent) {
  const e = EFFECTS[+$("modeSel").value]; if (!e) return;
  const oc = ("open" in e) || ("close" in e), single = ("single" in e);
  const fb = $("fwdBtn"), bb = $("bwdBtn");
  fb.textContent = oc ? "⤢ Open" : "⟶ Forward"; bb.textContent = oc ? "⤡ Close" : "⟵ Backward";
  fb.disabled = single; bb.disabled = single;
  const n = single ? e.single : oc ? (fwd ? (e.open ?? e.close) : (e.close ?? e.open)) : (fwd ? (e.fwd ?? e.bwd) : (e.bwd ?? e.fwd));
  $("md").value = n; $("modeNum").textContent = "#" + n;
  if (!silent) api("/api/mode?m=" + n);
}
function stepNum(d) { const i = $("md"); i.value = Math.max(1, Math.min(200, (parseInt(i.value) || 1) + d)); goNum(); }
function goNum() {
  let n = Math.max(1, Math.min(255, parseInt($("md").value) || 1)), s = $("modeSel");
  for (let i = 0; i < EFFECTS.length; i++) {
    const e = EFFECTS[i];
    if (e.single === n || e.fwd === n || e.open === n) { s.value = i; return setDir(1); }
    if (e.bwd === n || e.close === n) { s.value = i; return setDir(0); }
  }
  api("/api/mode?m=" + n);
}
loadModes();

// ---------- families ----------
let FAM_HEX = {}, BAR_COLORS = [];
function syncFams(active) { document.querySelectorAll("#famToggles button").forEach((b) => b.classList.toggle("on", (active || []).includes(b.dataset.fam))); }
function toggleFam(b) {
  b.classList.toggle("on");
  const active = [...document.querySelectorAll("#famToggles button.on")].map((x) => x.dataset.fam);
  api("/api/music/config?families=" + encodeURIComponent(active.join(",")));
}
async function loadFamilies() {
  const j = await (await fetch("/api/families")).json();
  FAM_HEX = j.color_hex || {}; BAR_COLORS = j.bar_colors || [];
  const box = $("famToggles"); box.innerHTML = "";
  (j.families || []).forEach((f) => {
    const b = document.createElement("button");
    b.textContent = f.family; b.dataset.fam = f.family;
    b.title = f.color_react ? "frequency picks colour: " + f.colors.join(" ") : "no single colours — uses 7-colour/combo";
    if (!f.color_react) b.style.opacity = "0.72";
    b.onclick = () => toggleFam(b);
    box.appendChild(b);
  });
  try { syncFams((await (await fetch("/api/music/state")).json()).active_families); } catch (e) { }
}
loadFamilies();

// ---------- music engine controls ----------
let musicOn = false, poll = null, HIST = [];
async function toggleMusic() {
  musicOn = !musicOn;
  const b = $("musicBtn");
  b.textContent = "🎵 Music Engine: " + (musicOn ? "ON" : "OFF"); b.classList.toggle("on", musicOn);
  $("mctl").style.display = musicOn ? "block" : "none";
  $("telemetry").style.display = musicOn ? "block" : "none";
  await api("/api/music/" + (musicOn ? "start" : "stop"));
  if (musicOn) { HIST = []; startPoll(); } else stopPoll();
}
function toggleCfg(key, btn) { const on = !btn.classList.contains("on"); btn.classList.toggle("on", on); api("/api/music/config?" + key + "=" + (on ? "true" : "false")); }
function cfg(key, val) { api("/api/music/config?" + key + "=" + val); }

// ---------- telemetry drawing ----------
function fit(c) { const W = c.width = c.clientWidth, H = c.height = c.clientHeight; return [c.getContext("2d"), W, H]; }
function drawSpec(sp) {
  const [x, W, H] = fit($("spec")); x.clearRect(0, 0, W, H);
  const n = sp.length; if (!n) return; const bw = W / n;
  for (let i = 0; i < n; i++) { const h = sp[i] * (H - 2); x.fillStyle = BAR_COLORS[i] || "#5b8cff"; x.fillRect(i * bw, H - h, Math.max(1, bw - 1), h); }
}
function line(ctx, hist, key, col, W, H) {
  ctx.strokeStyle = col; ctx.lineWidth = 1.6; ctx.beginPath();
  const n = hist.length;
  for (let i = 0; i < n; i++) { const X = n < 2 ? 0 : i / (n - 1) * W, Y = H - hist[i][key] * (H - 3) - 1.5; i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y); }
  ctx.stroke();
}
function drawLB(hist) {
  const [x, W, H] = fit($("lbGraph")); x.clearRect(0, 0, W, H);
  // brightness area fill
  x.fillStyle = "#5ad28a22"; x.beginPath(); x.moveTo(0, H);
  const n = hist.length;
  for (let i = 0; i < n; i++) { const X = n < 2 ? 0 : i / (n - 1) * W, Y = H - hist[i].bright * (H - 3) - 1.5; x.lineTo(X, Y); }
  x.lineTo(W, H); x.closePath(); x.fill();
  line(x, hist, "loud", "#7fd0ff", W, H);
  line(x, hist, "bright", "#5ad28a", W, H);
}
function drawCol(hist) {
  const [x, W, H] = fit($("colGraph")); x.clearRect(0, 0, W, H);
  const n = hist.length; if (!n) return; const bw = W / Math.max(n, 1);
  for (let i = 0; i < n; i++) { x.fillStyle = FAM_HEX[hist[i].color] || "#333"; x.fillRect(i / n * W, 0, Math.ceil(bw) + 1, H); }
  // spectral centroid line (treble high, bass low)
  x.strokeStyle = "#ffffffcc"; x.lineWidth = 1.4; x.beginPath();
  for (let i = 0; i < n; i++) { const X = n < 2 ? 0 : i / (n - 1) * W, Y = H - hist[i].centroid * (H - 3) - 1.5; i ? x.lineTo(X, Y) : x.moveTo(X, Y); }
  x.stroke();
}
function startPoll() {
  if (poll) return;
  poll = setInterval(async () => {
    try {
      const st = await (await fetch("/api/music/state")).json();
      $("bpm").textContent = st.bpm > 0 ? st.bpm : "—";
      $("cval").textContent = st.C ?? "—";
      const f = st.beat_flash || 0;
      $("beatDot").style.background = f > 0.2 ? "#57d090" : "#2a3142";
      $("beatDot").style.transform = `scale(${1 + f * 0.6})`;
      const hex = FAM_HEX[st.color] || "#2a3142";
      $("colDot").style.background = hex; $("colName").lastChild.textContent = st.color || "—";
      $("nowFam").textContent = st.family || "—";
      $("curMode").textContent = st.mode ? (NUM2NAME[st.mode] || "#" + st.mode) : "—";
      $("nowDir").textContent = st.direction === "bwd" ? "◀ back" : "▶ fwd";
      if (st.spectrum) drawSpec(st.spectrum);
      HIST.push({ loud: st.loudness || 0, bright: (st.brightness || 0) / 100, color: st.color, centroid: st.centroid || 0 });
      if (HIST.length > 240) HIST.shift();
      drawLB(HIST); drawCol(HIST);
    } catch (e) { }
  }, 80);
}
function stopPoll() { clearInterval(poll); poll = null; }

// ---------- command-rate graph + benchmark ----------
const cg = $("cmdGraph"), cgx = cg.getContext("2d");
function drawCmds(s) {
  const W = cg.width = cg.clientWidth, H = cg.height = cg.clientHeight; cgx.clearRect(0, 0, W, H);
  const h = s.hist || [], n = h.length; if (!n) return;
  const bucket = s.bucket || 0.5, ps = h.map((c) => c / bucket), mx = Math.max(s.max_rate * 1.3, 8, ...ps), bw = W / n;
  for (let i = 0; i < n; i++) { const v = ps[i] / mx, bh = v * (H - 4); cgx.fillStyle = `hsl(${140 - v * 140},70%,55%)`; cgx.fillRect(i * bw, H - bh, Math.max(1, bw - 1), bh); }
  // measured/limiter ceiling line
  const yl = H - (s.max_rate / mx) * (H - 4);
  cgx.strokeStyle = "#ff6b8188"; cgx.setLineDash([4, 4]); cgx.beginPath(); cgx.moveTo(0, yl); cgx.lineTo(W, yl); cgx.stroke(); cgx.setLineDash([]);
  cgx.fillStyle = "#ff6b81aa"; cgx.font = "10px system-ui"; cgx.fillText(`limit ${s.max_rate}/s`, 4, Math.max(10, yl - 3));
  $("cmdRate").textContent = s.rate + " /s";
  $("cmdTotal").textContent = `${s.total} total · ${s.dropped} dropped`;
}
async function benchmark() {
  $("benchResult").textContent = "measuring…";
  const j = await (await fetch("/api/benchmark?n=80")).json();
  if (!j.ok) { $("benchResult").textContent = "✗ " + j.error; return; }
  const safe = Math.max(5, Math.floor(j.rate) - 1);
  await fetch("/api/maxrate?r=" + safe);
  $("benchResult").textContent = `strip max ≈ ${j.rate}/s (${j.latency_ms}ms/cmd) → limiter set to ${safe}/s`;
}

// ---------- status poll ----------
setInterval(async () => {
  try {
    const st = await (await fetch("/api/state")).json();
    const p = $("conn");
    if (st.connected) { p.textContent = "connected"; p.className = "pill ok"; }
    else { p.textContent = "not connected"; p.className = "pill bad"; }
    if (st.cmds) drawCmds(st.cmds);
  } catch (e) { $("conn").textContent = "offline"; $("conn").className = "pill bad"; }
}, 500);

// ---------- soundboard (synth pads + light hits) ----------
let AC;
function ac() { AC = AC || new (window.AudioContext || window.webkitAudioContext)(); if (AC.state === "suspended") AC.resume(); return AC; }
function tone(f, dur = 0.28) { const a = ac(), o = a.createOscillator(), g = a.createGain(); o.type = "triangle"; o.frequency.value = f; g.gain.setValueAtTime(1e-4, a.currentTime); g.gain.exponentialRampToValueAtTime(0.4, a.currentTime + 0.01); g.gain.exponentialRampToValueAtTime(1e-4, a.currentTime + dur); o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + dur); }
function kick() { const a = ac(), o = a.createOscillator(), g = a.createGain(); o.frequency.setValueAtTime(150, a.currentTime); o.frequency.exponentialRampToValueAtTime(50, a.currentTime + 0.12); g.gain.setValueAtTime(0.85, a.currentTime); g.gain.exponentialRampToValueAtTime(1e-3, a.currentTime + 0.22); o.connect(g).connect(a.destination); o.start(); o.stop(a.currentTime + 0.22); }
function noise(dur = 0.16, hp = false) { const a = ac(), n = a.createBufferSource(), buf = a.createBuffer(1, a.sampleRate * dur, a.sampleRate), d = buf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; n.buffer = buf; const g = a.createGain(); g.gain.setValueAtTime(0.5, a.currentTime); g.gain.exponentialRampToValueAtTime(1e-3, a.currentTime + dur); let node = n; if (hp) { const fl = a.createBiquadFilter(); fl.type = "highpass"; fl.frequency.value = 7000; node.connect(fl); node = fl; } node.connect(g).connect(a.destination); n.start(); n.stop(a.currentTime + dur); }
const PADS = [
  { label: "Red", key: "a", hex: "ff2030", note: 262 }, { label: "Orange", key: "s", hex: "ff7a00", note: 294 },
  { label: "Yellow", key: "d", hex: "ffd400", note: 330 }, { label: "Green", key: "f", hex: "33dd44", note: 392 },
  { label: "Cyan", key: "g", hex: "00d8e6", note: 440 }, { label: "Blue", key: "h", hex: "3060ff", note: 523 },
  { label: "Violet", key: "j", hex: "a000ff", note: 587 }, { label: "White", key: "k", hex: "ffffff", note: 659 },
  { label: "Kick", key: "z", hex: "ff0000", fx: "kick" }, { label: "Snare", key: "x", hex: "ffffff", fx: "snare" },
  { label: "Hat", key: "c", hex: "00ffd0", fx: "hat" }, { label: "Strobe", key: "v", hex: "ffffff", mode: 80 },
];
function darken(hex, f) { const n = parseInt(hex, 16); return `rgb(${(n >> 16 & 255) * f | 0},${(n >> 8 & 255) * f | 0},${(n & 255) * f | 0})`; }
function firePad(p, el) {
  if (el) { el.classList.add("hit"); setTimeout(() => el.classList.remove("hit"), 110); }
  if (p.fx === "kick") kick(); else if (p.fx === "snare") noise(0.18); else if (p.fx === "hat") noise(0.05, true); else if (p.note) tone(p.note);
  if (p.mode) api("/api/mode?m=" + p.mode); else if (p.hex) api("/api/color?hex=" + p.hex);
}
const KEYMAP = {};
PADS.forEach((p) => {
  const el = document.createElement("div");
  el.className = "pad"; el.style.background = darken(p.hex, 0.62);
  el.innerHTML = `${p.label}<span class="pk">${p.key.toUpperCase()}</span>`;
  el.onclick = () => firePad(p, el); $("pads").appendChild(el); KEYMAP[p.key] = () => firePad(p, el);
});
document.addEventListener("keydown", (e) => { if (e.repeat || ["INPUT", "SELECT"].includes(e.target.tagName)) return; const f = KEYMAP[e.key.toLowerCase()]; if (f) { e.preventDefault(); f(); } });
