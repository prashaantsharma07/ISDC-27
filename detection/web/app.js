// TeamMARS object detection — browser side.
// Video path: camera -> <video> -> WebGL (LUT, flip, mirror, rotate, invert) -> screen. No server in between.
// Detection path (separate): small JPEG snapshot -> WebSocket -> boxes back. One frame in flight, never queues.

const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const video = $("#cam"), view = $("#view"), overlay = $("#overlay"), octx = overlay.getContext("2d");

// ---------------------------------------------------------------- settings (remembered per laptop)
const DEF = { mirror: false, flip: false, rot: 0, invert: false, detect: true, lut: "clarity", lutMix: 1, conf: 0.25, imgsz: 480,
  exposure: 0, contrast: 1, saturation: 1, camId: "", res: "1280x720", enabled: null };
const S = Object.assign({}, DEF, JSON.parse(localStorage.getItem("tm.settings") || "{}"));
const save = () => localStorage.setItem("tm.settings", JSON.stringify(S));

let targets = [];
let dirty = true; // picture needs a redraw (settings changed between camera frames)
let mission = JSON.parse(localStorage.getItem("tm.mission") || "{}");
const saveMission = () => { try { localStorage.setItem("tm.mission", JSON.stringify(mission)); } catch { /* full: keep in memory */ } };

// ---------------------------------------------------------------- toast + liquid sheen
let toastTimer;
function toast(msg, ms = 2200) {
  const t = $("#toast"); t.textContent = msg; t.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => (t.hidden = true), ms);
}
addEventListener("pointermove", (e) => {
  for (const g of $$(".glass")) {
    const r = g.getBoundingClientRect();
    g.style.setProperty("--mx", `${e.clientX - r.left}px`);
    g.style.setProperty("--my", `${e.clientY - r.top}px`);
  }
}, { passive: true });

// ---------------------------------------------------------------- WebGL renderer
const gl = view.getContext("webgl2", { preserveDrawingBuffer: true, antialias: false, desynchronized: true });
const VS = `#version 300 es
in vec2 p; out vec2 uv;
void main(){ uv = vec2(p.x*0.5+0.5, 0.5-p.y*0.5); gl_Position = vec4(p,0.,1.); }`;
const FS = `#version 300 es
precision highp float; precision highp sampler3D;
in vec2 uv; out vec4 o;
uniform sampler2D cam; uniform sampler3D lut;
uniform int rot; uniform bool mirror, flip, invert; uniform float lutMix, lutSize, expo, con, sat;
void main(){
  vec2 t = uv - 0.5;                       // display -> source: undo rotation, then mirror/flip
  for (int i = 0; i < 4; i++) { if (i >= rot) break; t = vec2(t.y, -t.x); }
  if (mirror) t.x = -t.x;
  if (flip)   t.y = -t.y;
  vec3 c = texture(cam, t + 0.5).rgb;
  c *= exp2(expo);
  c = (c - 0.5) * con + 0.5;
  float y = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c = clamp(mix(vec3(y), c, sat), 0., 1.);
  vec3 g = texture(lut, c * ((lutSize - 1.) / lutSize) + 0.5 / lutSize).rgb;
  c = mix(c, g, lutMix);
  if (invert) c = 1. - c;
  o = vec4(c, 1.);
}`;
function shader(type, src) { const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s); if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw gl.getShaderInfoLog(s); return s; }
const prog = gl.createProgram();
gl.attachShader(prog, shader(gl.VERTEX_SHADER, VS)); gl.attachShader(prog, shader(gl.FRAGMENT_SHADER, FS)); gl.linkProgram(prog); gl.useProgram(prog);
const U = (n) => gl.getUniformLocation(prog, n);
gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer());
gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);
gl.enableVertexAttribArray(0); gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);
const camTex = gl.createTexture(); gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, camTex);
for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_2D, k, v);
const lutTex = gl.createTexture(); gl.activeTexture(gl.TEXTURE1); gl.bindTexture(gl.TEXTURE_3D, lutTex);
for (const [k, v] of [[gl.TEXTURE_MIN_FILTER, gl.LINEAR], [gl.TEXTURE_MAG_FILTER, gl.LINEAR], [gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE], [gl.TEXTURE_WRAP_R, gl.CLAMP_TO_EDGE]]) gl.texParameteri(gl.TEXTURE_3D, k, v);
gl.uniform1i(U("cam"), 0); gl.uniform1i(U("lut"), 1);
let lutSize = 2;
function setLutData(size, rgb) { // rgb: Float32Array size^3*3, red fastest
  const px = new Uint8Array(size * size * size * 4);
  for (let i = 0, j = 0; i < rgb.length; i += 3, j += 4) { px[j] = rgb[i] * 255 + .5; px[j + 1] = rgb[i + 1] * 255 + .5; px[j + 2] = rgb[i + 2] * 255 + .5; px[j + 3] = 255; }
  gl.activeTexture(gl.TEXTURE1); gl.texImage3D(gl.TEXTURE_3D, 0, gl.RGBA8, size, size, size, 0, gl.RGBA, gl.UNSIGNED_BYTE, px);
  lutSize = size; dirty = true;
}
function parseCube(text) {
  let size = 0; const vals = [];
  for (const line of text.split(/\r?\n/)) {
    const l = line.trim();
    if (!l || l[0] === "#") continue;
    if (l.startsWith("LUT_3D_SIZE")) size = parseInt(l.split(/\s+/)[1]);
    else if (/^[-\d.]/.test(l)) { const p = l.split(/\s+/); vals.push(+p[0], +p[1], +p[2]); }
  }
  if (!size || vals.length !== size ** 3 * 3) throw new Error("not a 3D .cube LUT");
  return { size, rgb: new Float32Array(vals) };
}
setLutData(2, new Float32Array([0, 0, 0, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 1, 1, 0, 1, 0, 1, 1, 1, 1, 1])); // identity
const LUTS = { neutral: "Neutral", clarity: "Clarity", haze_cut: "Haze Cut", low_light: "Low Light", ground_contrast: "Ground Contrast", mono_detail: "Mono Detail" };
const lutCache = {};
async function loadLut(name) {
  try {
    if (!lutCache[name]) lutCache[name] = parseCube(await (await fetch(`luts/${name}.cube`)).text());
    setLutData(lutCache[name].size, lutCache[name].rgb);
  } catch (e) { toast("LUT failed: " + e.message); }
}

// ---------------------------------------------------------------- layout: fit the (rotated) picture into the screen
let rect = { x: 0, y: 0, w: 1, h: 1 };
function layout() {
  const vw = video.videoWidth || 1280, vh = video.videoHeight || 720;
  const [pw, ph] = S.rot % 2 ? [vh, vw] : [vw, vh];
  const sw = innerWidth, sh = innerHeight, k = Math.min(sw / pw, sh / ph);
  rect = { w: pw * k, h: ph * k, x: (sw - pw * k) / 2, y: (sh - ph * k) / 2 };
  if (view.width !== pw || view.height !== ph) { view.width = pw; view.height = ph; }
  Object.assign(view.style, { left: rect.x + "px", top: rect.y + "px", width: rect.w + "px", height: rect.h + "px" });
  const dpr = devicePixelRatio || 1;
  overlay.width = innerWidth * dpr; overlay.height = innerHeight * dpr; octx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
addEventListener("resize", layout);

// source (camera) point 0..1 -> screen pixel, same maths as the shader in reverse
function toScreen(x, y) {
  let tx = x - 0.5, ty = y - 0.5;
  if (S.mirror) tx = -tx;
  if (S.flip) ty = -ty;
  for (let i = 0; i < S.rot; i++) [tx, ty] = [-ty, tx];
  return [rect.x + (tx + 0.5) * rect.w, rect.y + (ty + 0.5) * rect.h];
}
function boxToScreen(b) {
  const pts = [toScreen(b[0], b[1]), toScreen(b[2], b[1]), toScreen(b[0], b[3]), toScreen(b[2], b[3])];
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  return [Math.min(...xs), Math.min(...ys), Math.max(...xs), Math.max(...ys)];
}

// ---------------------------------------------------------------- render loop (driven by camera frames)
let frames = 0, lastFpsT = performance.now(), frameLoopOn = false;
function draw(upload) {
  if (video.readyState >= 2) {
    gl.viewport(0, 0, view.width, view.height);
    gl.activeTexture(gl.TEXTURE0); gl.bindTexture(gl.TEXTURE_2D, camTex);
    if (upload) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, video);
    gl.uniform1i(U("rot"), S.rot); gl.uniform1i(U("mirror"), S.mirror); gl.uniform1i(U("flip"), S.flip); gl.uniform1i(U("invert"), S.invert);
    gl.uniform1f(U("lutMix"), S.lutMix); gl.uniform1f(U("lutSize"), lutSize); gl.uniform1f(U("expo"), S.exposure);
    gl.uniform1f(U("con"), S.contrast); gl.uniform1f(U("sat"), S.saturation);
    gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    if (upload) frames++;
  }
}
// one draw per NEW camera frame (no polling, no extra latency)
function onCameraFrame() { draw(true); video.requestVideoFrameCallback(onCameraFrame); }
function startFrameLoop() {
  if (frameLoopOn) return; frameLoopOn = true;
  if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(onCameraFrame);
}
// display loop: smooth "liquid" boxes, fps meter; also redraws the picture when settings change between frames
function displayLoop() {
  const now = performance.now();
  if (!video.requestVideoFrameCallback) draw(true); else if (dirty) { draw(false); dirty = false; }
  if (now - lastFpsT > 1000) { $("#camFps").textContent = Math.round(frames * 1000 / (now - lastFpsT)); frames = 0; lastFpsT = now; }
  drawOverlay(now);
  requestAnimationFrame(displayLoop);
}

// ---------------------------------------------------------------- tracks (smoothed boxes)
let tracks = [], detInterval = 300;
const iou = (a, b) => { const x1 = Math.max(a[0], b[0]), y1 = Math.max(a[1], b[1]), x2 = Math.min(a[2], b[2]), y2 = Math.min(a[3], b[3]); const i = Math.max(0, x2 - x1) * Math.max(0, y2 - y1); return i / ((a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - i + 1e-9); };
function updateTracks(dets, now) {
  for (const d of dets) {
    let t = tracks.find((t) => t.target === d.target && iou(t.goal, d.box) > 0.25);
    if (!t) { t = { target: d.target, box: d.box.slice(), goal: d.box, born: now }; tracks.push(t); }
    Object.assign(t, { goal: d.box, conf: d.conf, colour: d.colour, hint: d.hint, seen: now });
  }
  tracks = tracks.filter((t) => now - t.seen < life());
}
const life = () => Math.max(900, detInterval * 2.5);  // keep boxes until the next detection is due
let lastDraw = 0;
function drawOverlay(now) {
  if (now - lastDraw < 8) return; lastDraw = now;
  octx.clearRect(0, 0, innerWidth, innerHeight);
  tracks = tracks.filter((t) => now - t.seen < life());
  for (const t of tracks) {
    for (let i = 0; i < 4; i++) t.box[i] += (t.goal[i] - t.box[i]) * 0.35;            // glide toward the latest detection
    const age = now - t.seen, alpha = Math.max(0, Math.min(1, (life() - age) / 400)) * Math.min(1, (now - t.born) / 180);
    const [x1, y1, x2, y2] = boxToScreen(t.box), w = x2 - x1, h = y2 - y1, r = Math.min(14, w / 4, h / 4);
    octx.save(); octx.globalAlpha = alpha;
    octx.lineWidth = 3; octx.strokeStyle = "rgba(90,110,151,.95)"; octx.shadowColor = "rgba(16,18,22,.55)"; octx.shadowBlur = 10;
    octx.beginPath(); octx.roundRect(x1, y1, w, h, r); octx.stroke();
    octx.shadowBlur = 0; octx.lineWidth = 1.5; octx.strokeStyle = "rgba(248,244,238,.9)";
    octx.beginPath(); octx.roundRect(x1 + 3, y1 + 3, w - 6, h - 6, Math.max(0, r - 3)); octx.stroke();
    const label = `${t.target}  ${Math.round(t.conf * 100)}%  ·  ${t.colour?.name || ""}`;
    octx.font = "600 13px Inter, Segoe UI, system-ui, sans-serif";
    const tw = octx.measureText(label).width + 34, th = 26, lx = x1, ly = Math.max(4, y1 - th - 6);
    const g = octx.createLinearGradient(lx, ly, lx, ly + th);
    g.addColorStop(0, "rgba(248,244,238,.92)"); g.addColorStop(1, "rgba(232,224,210,.82)");
    octx.fillStyle = g; octx.beginPath(); octx.roundRect(lx, ly, tw, th, 13); octx.fill();
    octx.fillStyle = t.colour?.hex || "#888"; octx.beginPath(); octx.arc(lx + 14, ly + th / 2, 6, 0, 7); octx.fill();
    octx.strokeStyle = "rgba(16,18,22,.35)"; octx.lineWidth = 1; octx.stroke();
    octx.fillStyle = "#101216"; octx.fillText(label, lx + 26, ly + 17.5);
    octx.restore();
  }
}

// ---------------------------------------------------------------- detection link
let ws, busy = false, seq = 0, sentAt = 0;
const grab = document.createElement("canvas"), gctx = grab.getContext("2d", { willReadFrequently: false });
function connect() {
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/detect`);
  ws.binaryType = "arraybuffer";
  ws.onopen = () => { sendSettings(); busy = false; pump(); };
  ws.onclose = () => { busy = false; $("#modeBadge").textContent = "offline"; setTimeout(connect, 1500); };
  ws.onmessage = (e) => {
    const r = JSON.parse(e.data), now = performance.now();
    busy = false;
    detInterval = detInterval * 0.8 + (now - sentAt) * 0.2;
    $("#detMs").textContent = Math.round(now - sentAt);
    $("#detMs").parentElement.title = `round trip ${Math.round(now - sentAt)} ms · model ${r.ms} ms`;
    setMode(r.mode);
    updateTracks(r.dets, now);
    for (const d of r.dets) noteMission(d);
    pump();
  };
}
function sendSettings() { if (ws?.readyState === 1) ws.send(JSON.stringify({ conf: S.conf, imgsz: S.imgsz, enabled: S.enabled })); }
function pump() {
  if (!S.detect || busy || ws?.readyState !== 1 || video.readyState < 2) { if (S.detect) setTimeout(pump, 50); return; }
  const vw = video.videoWidth, vh = video.videoHeight, w = Math.min(vw, 640), h = Math.round(vh * w / vw);
  grab.width = w; grab.height = h; gctx.drawImage(video, 0, 0, w, h);
  busy = true; sentAt = performance.now();
  grab.toBlob(async (b) => {
    if (!b) { busy = false; return; }
    const body = new Uint8Array(4 + b.size);
    new DataView(body.buffer).setUint32(0, ++seq, true);
    body.set(new Uint8Array(await b.arrayBuffer()), 4);
    ws.send(body);
  }, "image/jpeg", 0.8);
}
function setMode(m) {
  const b = $("#modeBadge");
  b.textContent = m === "custom" ? "TeamMARS model" : m === "starter" ? "starter model" : m;
  b.className = "badge " + m;
  b.title = m === "starter" ? "Generic open-vocabulary model: train your own for competition accuracy (Train button)" : "Your trained model";
}

// ---------------------------------------------------------------- mission cards
const crop = document.createElement("canvas"), cctx = crop.getContext("2d");
function snapshotOf(box, maxW) { // crop the object (with margin) from the raw camera frame
  const vw = video.videoWidth, vh = video.videoHeight;
  const pad = 0.15, bw = box[2] - box[0], bh = box[3] - box[1];
  const x = Math.max(0, (box[0] - bw * pad) * vw), y = Math.max(0, (box[1] - bh * pad) * vh);
  const w = Math.min(vw - x, bw * (1 + 2 * pad) * vw), h = Math.min(vh - y, bh * (1 + 2 * pad) * vh);
  const k = Math.min(1, maxW / w);
  crop.width = Math.max(1, w * k); crop.height = Math.max(1, h * k);
  cctx.drawImage(video, x, y, w, h, 0, 0, crop.width, crop.height);
  return crop.toDataURL("image/jpeg", 0.85);
}
function contextOf(box) { // whole frame with the box drawn, for the report
  const vw = video.videoWidth, vh = video.videoHeight, k = 480 / vw;
  crop.width = 480; crop.height = vh * k;
  cctx.drawImage(video, 0, 0, crop.width, crop.height);
  cctx.lineWidth = 3; cctx.strokeStyle = "#5A6E97";
  cctx.strokeRect(box[0] * crop.width, box[1] * crop.height, (box[2] - box[0]) * crop.width, (box[3] - box[1]) * crop.height);
  return crop.toDataURL("image/jpeg", 0.8);
}
function noteMission(d) {
  const m = mission[d.target] || (mission[d.target] = { found: false });
  const now = Date.now();
  if (!m.found) { m.found = true; m.firstSeen = new Date().toLocaleTimeString(); toast(`Found: ${d.target} (${d.colour.name})`); }
  if (!m.best || d.conf > m.best + 0.02 && now - (m.snapAt || 0) > 700) {
    Object.assign(m, { best: d.conf, colour: d.colour, hint: d.hint, thumb: snapshotOf(d.box, 220), context: contextOf(d.box), box: d.box, snapAt: now });
    renderCards(); saveMission();
  }
}
function renderCards() {
  const cards = $("#cards"); cards.innerHTML = "";
  const list = targets.filter((t) => !S.enabled || S.enabled.includes(t));
  let found = 0;
  for (const name of list) {
    const m = mission[name] || {};
    if (m.found) found++;
    const el = document.createElement("div");
    el.className = "card" + (m.found ? " found" : "");
    el.innerHTML = `
      <div class="thumb" style="${m.thumb ? `background-image:url(${m.thumb})` : ""}">${m.thumb ? "" : "?"}</div>
      <div><h4>${name}${m.found ? " ✓" : ""}</h4>
        <div class="meta">${m.found ? `<span class="swatch" style="background:${m.colour.hex}"></span> ${m.colour.name} · ${Math.round(m.best * 100)}% · ${m.firstSeen}` : "not found yet"}</div></div>
      ${m.hint ? `<div class="hint">⚠ ${m.hint}</div>` : ""}
      <div class="cond">${["Intact", "Damaged", "Tipped over", "Dirty", "Partly buried"].map((c) => `<button class="${(m.cond || []).includes(c) ? "on" : ""}" data-c="${c}">${c}</button>`).join("")}</div>
      <div class="actions"><button data-a="ocr">Read label / brand</button><button data-a="reset">Reset</button></div>
      ${m.ocr ? `<div class="ocr">${m.ocr}</div>` : ""}`;
    el.querySelectorAll(".cond button").forEach((b) => b.onclick = () => {
      m.cond = m.cond || []; const c = b.dataset.c;
      m.cond = m.cond.includes(c) ? m.cond.filter((x) => x !== c) : [...m.cond, c];
      saveMission(); renderCards();
    });
    el.querySelector('[data-a="reset"]').onclick = () => { delete mission[name]; saveMission(); renderCards(); };
    el.querySelector('[data-a="ocr"]').onclick = () => readLabel(name);
    cards.appendChild(el);
  }
  $("#foundCount").textContent = `${found} / ${list.length}`;
}
async function readLabel(name) {
  const m = mission[name]; if (!m?.box) return;
  toast("Reading label…");
  const blob = await (await fetch(snapshotOf(m.box, 900))).blob();
  const fd = new FormData(); fd.append("image", blob, "crop.jpg");
  const r = await (await fetch("/api/inspect", { method: "POST", body: fd })).json();
  m.ocr = r.brand ? `Brand: ${r.brand} · text: ${r.text.join(" ")}` : r.text.length ? `Text: ${r.text.join(" ")}` : r.note;
  saveMission(); renderCards();
}

// ---------------------------------------------------------------- report (one self-contained HTML file)
function exportReport() {
  const rows = targets.filter((t) => !S.enabled || S.enabled.includes(t)).map((n) => {
    const m = mission[n] || {};
    return `<tr><td><b>${n}</b></td><td>${m.found ? "FOUND" : "not found"}</td><td>${m.firstSeen || ""}</td>
      <td>${m.found ? `<span style="display:inline-block;width:14px;height:14px;border-radius:4px;background:${m.colour.hex};vertical-align:-2px"></span> ${m.colour.name}` : ""}</td>
      <td>${m.found ? Math.round(m.best * 100) + "%" : ""}</td><td>${(m.cond || []).join(", ")}${m.hint ? `<br><i>${m.hint}</i>` : ""}</td>
      <td>${m.ocr || ""}</td><td>${m.thumb ? `<img src="${m.thumb}" height="90">` : ""}</td><td>${m.context ? `<img src="${m.context}" height="90">` : ""}</td></tr>`;
  }).join("");
  const html = `<!doctype html><meta charset="utf-8"><title>TeamMARS detection report</title>
  <style>body{font-family:Inter,Segoe UI,system-ui,sans-serif;background:#EFE8DC;color:#101216;margin:32px}h1{margin:0}p{color:#3B4C70}
  table{border-collapse:collapse;width:100%;background:#F8F4EE;border-radius:14px;overflow:hidden}th{background:#5A6E97;color:#F8F4EE;text-align:left}
  th,td{padding:10px;border-bottom:1px solid #ddd3c2;font-size:14px;vertical-align:middle}img{border-radius:8px}</style>
  <h1>TeamMARS — object identification report</h1><p>${new Date().toLocaleString()} · ${Object.values(mission).filter((m) => m.found).length} items found</p>
  <table><tr><th>Item</th><th>Status</th><th>First seen</th><th>Colour</th><th>Confidence</th><th>Condition</th><th>Label / brand</th><th>Close-up</th><th>In view</th></tr>${rows}</table>`;
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([html], { type: "text/html" }));
  a.download = `TeamMARS-report-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.html`;
  a.click(); toast("Report saved");
}

// ---------------------------------------------------------------- training capture
async function captureTraining(n = 1) {
  const item = $("#trainItem").value;
  for (let i = 0; i < n; i++) {
    const c = document.createElement("canvas"); c.width = video.videoWidth; c.height = video.videoHeight;
    c.getContext("2d").drawImage(video, 0, 0);
    const blob = await new Promise((r) => c.toBlob(r, "image/jpeg", 0.92));
    const fd = new FormData(); fd.append("target", item); fd.append("image", blob, "f.jpg");
    const r = await (await fetch("/api/capture", { method: "POST", body: fd })).json();
    toast(`${item}: ${r.count} photos`, 900);
    if (n > 1) await new Promise((r) => setTimeout(r, 350));
  }
  refreshStatus();
}

// ---------------------------------------------------------------- camera
async function listCameras() {
  const devs = (await navigator.mediaDevices.enumerateDevices()).filter((d) => d.kind === "videoinput");
  const sel = $("#camSel"); sel.innerHTML = "";
  devs.forEach((d, i) => sel.add(new Option(d.label || `Camera ${i + 1}`, d.deviceId)));
  if (S.camId && devs.some((d) => d.deviceId === S.camId)) sel.value = S.camId;
  return devs;
}
async function startCamera() {
  const src = new URLSearchParams(location.search).get("src"); // test without a camera: ?src=test/demo.mp4
  try {
    if (src) { video.src = src; video.loop = true; await video.play(); }
    else {
      video.srcObject?.getTracks().forEach((t) => t.stop());
      const [w, h] = S.res.split("x").map(Number);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: false,
        video: { deviceId: S.camId ? { exact: S.camId } : undefined, width: { ideal: w }, height: { ideal: h }, frameRate: { ideal: 60 } } });
      video.srcObject = stream; await video.play();
      const id = stream.getVideoTracks()[0].getSettings().deviceId; if (id) { S.camId = id; save(); }
      await listCameras();
    }
    $("#nofeed").classList.add("gone"); $("#camDot").classList.add("live"); startFrameLoop();
    video.onloadedmetadata = layout; layout(); pump();
  } catch (e) { toast("Camera: " + e.message, 4000); }
}

// ---------------------------------------------------------------- controls
function syncControls() {
  dirty = true;
  $$("[data-toggle]").forEach((b) => b.classList.toggle("on", !!S[b.dataset.toggle]));
  $("#rotLabel").textContent = `${S.rot * 90}°`;
  $("#lutSel").value = S.lut; $("#lutMix").value = S.lutMix;
  $("#conf").value = S.conf; $("#confOut").textContent = Math.round(S.conf * 100) + "%";
  $("#imgsz").value = S.imgsz; $("#resSel").value = S.res;
  for (const [id, out, f] of [["exposure", "expOut", (v) => v.toFixed(2)], ["contrast", "conOut", (v) => v.toFixed(2)], ["saturation", "satOut", (v) => v.toFixed(2)]]) { $("#" + id).value = S[id]; $("#" + out).textContent = f(+S[id]); }
  liquid();
}
function liquid() { // blobs under the active toggle buttons, merged by the goo filter
  const seg = $("#viewSeg"), host = seg.querySelector(".liquid"); host.innerHTML = "";
  const sr = seg.getBoundingClientRect();
  seg.querySelectorAll("button").forEach((b) => {
    b.classList.add("has-liquid");
    if (!b.classList.contains("on")) return;
    const r = b.getBoundingClientRect(), i = document.createElement("i");
    i.style.left = r.left - sr.left + "px"; i.style.width = r.width + "px"; host.appendChild(i);
  });
}
document.addEventListener("click", (e) => {
  const t = e.target.closest("[data-toggle],[data-act]"); if (!t) return;
  if (t.dataset.toggle) { S[t.dataset.toggle] = !S[t.dataset.toggle]; save(); syncControls(); if (t.dataset.toggle === "detect") { tracks = []; pump(); } return; }
  const a = t.dataset.act;
  if (a === "start") startCamera();
  if (a === "rotate") { S.rot = (S.rot + 1) % 4; save(); layout(); syncControls(); }
  if (a === "settings" || a === "train") { const s = $("#" + a); const open = s.hidden; $$(".sheet").forEach((x) => (x.hidden = true)); s.hidden = !open; if (a === "train") refreshStatus(); }
  if (a === "close") t.closest(".sheet").hidden = true;
  if (a === "collapse") $("#mission").classList.toggle("collapsed");
  if (a === "report") exportReport();
  if (a === "capture") captureTraining(1);
  if (a === "burst") captureTraining(20);
  if (a === "snap") {
    const c = document.createElement("canvas"); c.width = innerWidth; c.height = innerHeight;
    const x = c.getContext("2d"); x.drawImage(view, rect.x, rect.y, rect.w, rect.h); x.drawImage(overlay, 0, 0, innerWidth, innerHeight);
    const l = document.createElement("a"); l.href = c.toDataURL("image/jpeg", 0.9); l.download = `TeamMARS-snap-${Date.now()}.jpg`; l.click();
  }
});
$("#lutSel").onchange = (e) => { S.lut = e.target.value; save(); S.lut.startsWith("user:") ? null : loadLut(S.lut); };
$("#lutMix").oninput = (e) => { S.lutMix = +e.target.value; save(); };
$("#conf").oninput = (e) => { S.conf = +e.target.value; save(); syncControls(); sendSettings(); };
$("#imgsz").onchange = (e) => { S.imgsz = +e.target.value; save(); sendSettings(); };
for (const id of ["exposure", "contrast", "saturation"]) $("#" + id).oninput = (e) => { S[id] = +e.target.value; save(); syncControls(); };
$("#lutMix").addEventListener("input", () => (dirty = true));
$("#camSel").onchange = (e) => { S.camId = e.target.value; save(); startCamera(); };
$("#resSel").onchange = (e) => { S.res = e.target.value; save(); startCamera(); };
$("#lutFile").onchange = async (e) => {
  const f = e.target.files[0]; if (!f) return;
  try { const l = parseCube(await f.text()); const key = "user:" + f.name; lutCache[key] = l; setLutData(l.size, l.rgb); $("#lutSel").add(new Option("★ " + f.name.replace(/\.cube$/i, ""), key)); $("#lutSel").value = key; S.lut = key; toast("LUT loaded: " + f.name); }
  catch (err) { toast("Not a valid .cube LUT: " + err.message, 3500); }
};
addEventListener("keydown", (e) => {
  if (e.target.matches("input,select,textarea")) return;
  const k = e.key.toLowerCase(), map = { m: "mirror", f: "flip", i: "invert", d: "detect" };
  if (map[k]) { S[map[k]] = !S[map[k]]; save(); syncControls(); if (k === "d") pump(); }
  if (k === "r") { S.rot = (S.rot + 1) % 4; save(); layout(); syncControls(); }
  if (k === "s") document.querySelector('[data-act="snap"]').click();
});

async function refreshStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    if (!targets.length) {
      targets = s.targets;
      $("#targetToggles").innerHTML = ""; $("#trainItem").innerHTML = "";
      for (const t of targets) {
        $("#trainItem").add(new Option(t, t));
        const b = document.createElement("button"); b.textContent = t;
        b.className = !S.enabled || S.enabled.includes(t) ? "on" : "";
        b.onclick = () => { const on = S.enabled || [...targets]; S.enabled = on.includes(t) ? on.filter((x) => x !== t) : [...on, t]; save(); b.classList.toggle("on"); sendSettings(); renderCards(); };
        $("#targetToggles").appendChild(b);
      }
      renderCards();
    }
    setMode(s.mode);
    $("#dataset").innerHTML = targets.map((t) => `<span>${t}: ${s.dataset[t.toLowerCase().replace(/[^a-z0-9]+/g, "_")] || 0}</span>`).join("");
  } catch { /* server restarting */ }
}

// ---------------------------------------------------------------- boot
for (const [k, v] of Object.entries(LUTS)) $("#lutSel").add(new Option(v, k));
syncControls(); loadLut(S.lut.startsWith("user:") ? "clarity" : S.lut);
refreshStatus(); setInterval(refreshStatus, 6000);
connect(); layout();
displayLoop();
if (new URLSearchParams(location.search).get("src")) startCamera();
else navigator.mediaDevices?.enumerateDevices().then((d) => { if (d.some((x) => x.kind === "videoinput" && x.label)) startCamera(); });
