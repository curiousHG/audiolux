"""Tiny browser UI to control the LEDDMX strip — pure Python (stdlib http.server).

Holds one persistent BLE connection in a background asyncio thread and reuses
the validated command builders from leddmx.py.

Run:   uv run python led_web.py
Open:  http://localhost:8765
(The phone must be disconnected from the strip — only one BLE link at a time.)
"""
import asyncio
import threading
import json
import os
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from bleak import BleakClient, BleakScanner
import leddmx as L

PORT = 8765
try:
    with open(os.path.join(os.path.dirname(__file__), "modes_dmx03.json"), encoding="utf-8") as f:
        MODES = json.load(f)   # [{"n": <mode>, "name": <effect name>}, ...] from the decompiled app
except Exception:
    MODES = []


def _classify_modes(modes):
    """Group the modes by effect family and pair each effect's two variants.
    NOTE: the app's data mislabels some 'Backward' entries as 'Forward'
    (e.g. 197 & 198 both say 'Forward Swab CN'), so we pair by mode NUMBER
    (lower = forward/open, higher = backward/close) rather than the text label."""
    import collections
    fams = ["Curtain Swab", "Follow Spot", "Horse Race", "Trailing", "Streaming",
            "Flutter", "Curtain", "Dreaming", "Strobe", "Swab", "Run", "Flow", "Hop"]
    order, acc = [], {}
    for m in modes:
        n, name = m["n"], m["name"]
        if name.strip().upper() == "AUTO":
            fam, base, oc = "Auto", "AUTO", False
        else:
            base, oc = name, False
            for p in ("Forward ", "Backward ", "Open ", "Close "):
                if name.startswith(p):
                    base, oc = name[len(p):], p in ("Open ", "Close ")
                    break
            fam = next((f for f in fams if f in base), "Basic")
        key = (fam, base)
        if key not in acc:
            acc[key] = {"fam": fam, "base": base, "nums": [], "oc": False}
            order.append(key)
        acc[key]["nums"].append(n)
        acc[key]["oc"] = acc[key]["oc"] or oc
    groups = collections.OrderedDict()
    for key in order:
        d = acc[key]
        nums = sorted(set(d["nums"]))
        eff = {"name": d["base"]}
        if len(nums) == 1:
            eff["single"] = nums[0]
        elif d["oc"]:
            eff["open"], eff["close"] = nums[0], nums[1]
        else:
            eff["fwd"], eff["bwd"] = nums[0], nums[1]
        groups.setdefault(d["fam"], []).append(eff)
    return [{"family": fam, "effects": effs} for fam, effs in groups.items()]


GROUPED = _classify_modes(MODES)


# ---------------------------------------------------------------------------
# BLE worker: its own asyncio loop on a background thread, one live connection.
# ---------------------------------------------------------------------------
class Ble:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.client = None
        self.lock = asyncio.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    async def _ensure(self):
        if self.client and self.client.is_connected:
            return
        dev = await BleakScanner.find_device_by_name(L.TARGET_NAME, timeout=15.0)
        if not dev:
            raise RuntimeError("LEDDMX not found — is the phone still holding the strip?")
        self.client = BleakClient(dev)
        await self.client.connect()

    async def _write(self, payload):
        async with self.lock:
            await self._ensure()
            await self.client.write_gatt_char(L.CHAR_UUID, payload, response=False)

    def write(self, payload):
        fut = asyncio.run_coroutine_threadsafe(self._write(payload), self.loop)
        fut.result(timeout=20)

    def submit(self, payload):
        # fire-and-forget; returns the future so callers can track completion
        return asyncio.run_coroutine_threadsafe(self._write(payload), self.loop)


ble = Ble()


# ---------------------------------------------------------------------------
# Music engine: mic FFT -> frequency bands -> RGB, loudness -> brightness.
# bass->red, mids->green, treble->blue.  Runs in sounddevice's audio thread.
# ---------------------------------------------------------------------------
class MusicEngine:
    SR = 44100
    BLOCK = 1024

    def __init__(self, ble):
        self.ble = ble
        self.stream = None
        self.running = False
        self.pending = 0
        self.last_send = 0.0
        self.loudpeak = 1e-6
        import numpy as np
        self.np = np
        self.window = np.hanning(self.BLOCK)
        self.smooth = np.zeros(3)
        self.freqs = np.fft.rfftfreq(self.BLOCK, 1 / self.SR)
        self.edges = [20, 250, 2000, 6000]   # bass | mid | treble | top
        self.sens = 1.0
        self.alpha = 0.5
        self.levels = [0.0, 0.0, 0.0]
        self.rgb = (0, 0, 0)
        # log-spaced bars for the UI spectrum analyzer
        self.NBARS = 40
        fmax = min(16000, self.SR / 2)
        ehz = np.logspace(np.log10(30), np.log10(fmax), self.NBARS + 1)
        idx = np.searchsorted(self.freqs, ehz)
        self.barbins = list(zip(idx[:-1].tolist(), idx[1:].tolist()))
        self.barfreqs = [int(f) for f in (ehz[:-1] + ehz[1:]) / 2]
        self.specsmooth = np.zeros(self.NBARS)
        self.specpeak = 1e-6
        self.spectrum = [0.0] * self.NBARS
        self._recompute()

    def _recompute(self):
        e = self.edges
        self.bands = [(self.freqs >= e[i]) & (self.freqs < e[i + 1]) for i in range(3)]

    def set_config(self, b1=None, b2=None, b3=None, sens=None, alpha=None):
        e = self.edges
        b1 = int(b1) if b1 is not None else e[1]
        b2 = int(b2) if b2 is not None else e[2]
        b3 = int(b3) if b3 is not None else e[3]
        b1 = max(40, b1); b2 = max(b1 + 50, b2); b3 = max(b2 + 100, b3)
        self.edges = [20, b1, b2, b3]; self._recompute()
        if sens is not None:  self.sens = float(sens)
        if alpha is not None: self.alpha = min(0.95, max(0.05, float(alpha)))

    def get_state(self):
        return {"on": self.running, "levels": [round(x, 3) for x in self.levels],
                "rgb": list(self.rgb), "edges": self.edges,
                "sens": round(self.sens, 2), "alpha": round(self.alpha, 2),
                "spectrum": self.spectrum, "barfreqs": self.barfreqs}

    def start(self):
        if self.running:
            return
        import sounddevice as sd
        self.ble.write(L.cmd_power(True))
        self.ble.write(L.cmd_brightness(100))
        self.stream = sd.InputStream(channels=1, samplerate=self.SR,
                                     blocksize=self.BLOCK, callback=self._cb)
        self.stream.start()
        self.running = True

    def stop(self):
        self.running = False
        if self.stream:
            self.stream.stop(); self.stream.close(); self.stream = None
        self.ble.submit(L.cmd_color(255, 120, 40))  # settle on a warm white

    def _done(self, _fut):
        self.pending = max(0, self.pending - 1)

    def _cb(self, indata, frames, tinfo, status):
        np = self.np
        x = indata[:, 0].astype(np.float32)
        spec = np.abs(np.fft.rfft(x * self.window))
        energy = np.array([float(spec[m].sum()) if m.any() else 0.0 for m in self.bands])
        total = float(energy.sum())
        hue = energy / (energy.max() + 1e-9)           # dominant band -> 1
        self.loudpeak = max(total, self.loudpeak * 0.997)
        loud = min(1.0, (total / (self.loudpeak + 1e-9)) * self.sens) ** 1.5
        target = hue * loud
        a = self.alpha
        self.smooth = (1 - a) * self.smooth + a * target  # EMA, anti-flicker
        self.levels = [float(x) for x in self.smooth]
        r, g, b = (int(min(255, c * 255)) for c in self.smooth)
        self.rgb = (r, g, b)
        # downsampled spectrum for the UI analyzer
        bars = np.array([spec[s:e2].mean() if e2 > s else 0.0 for s, e2 in self.barbins])
        self.specpeak = max(float(bars.max()), self.specpeak * 0.995)
        self.specsmooth = 0.6 * self.specsmooth + 0.4 * (bars / (self.specpeak + 1e-9))
        self.spectrum = [round(float(min(1.0, v)), 3) for v in self.specsmooth]
        now = time.monotonic()
        if now - self.last_send < 0.08 or self.pending > 1:   # ~12 fps, no backlog
            return
        self.last_send = now
        self.pending += 1
        self.ble.submit(L.cmd_color(r, g, b)).add_done_callback(self._done)


music = MusicEngine(ble)


# ---------------------------------------------------------------------------
# HTTP handler: serves the page and a tiny JSON API.
# ---------------------------------------------------------------------------
PAGE = """<!doctype html><html><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>LEDDMX Control</title><style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font:16px/1.4 system-ui,sans-serif;background:#0d0f14;color:#e7e9ee;
 display:flex;justify-content:center;padding:24px}
.card{width:100%;max-width:1000px;background:#161922;border:1px solid #232838;
 border-radius:18px;padding:22px 26px 26px}
h1{font-size:18px;margin:0 0 4px;letter-spacing:.3px}
.sub{color:#7b8395;font-size:12px;margin-bottom:16px}
.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:26px;align-items:start}
.col{min-width:0}
.col h2{font-size:11px;text-transform:uppercase;letter-spacing:1.2px;color:#5b8cff;
 margin:0 0 10px;border-bottom:1px solid #232838;padding-bottom:7px}
.row{display:flex;gap:10px;margin:12px 0}
button{flex:1;padding:11px;border:0;border-radius:12px;background:#222838;color:#e7e9ee;
 font-size:14px;cursor:pointer;transition:.12s}
button:hover{background:#2c3346}
button.on{background:#1f7a4d}button.off{background:#7a2330}
label{font-size:12px;color:#9aa3b5;display:block;margin:14px 0 6px}
input[type=range]{width:100%;accent-color:#5b8cff}
input[type=color]{width:100%;height:44px;border:0;border-radius:12px;background:#222838;cursor:pointer}
.swatches{display:grid;grid-template-columns:repeat(8,1fr);gap:6px}
.sw{height:26px;border-radius:7px;cursor:pointer;border:1px solid #0006}
.wheelwrap{position:relative;width:200px;height:200px;margin:8px auto 6px;touch-action:none}
#wheel{border-radius:50%;cursor:crosshair;display:block;box-shadow:0 0 0 1px #2a3142}
#marker{position:absolute;width:18px;height:18px;border-radius:50%;border:2px solid #fff;
 box-shadow:0 0 0 1px #0009;transform:translate(-50%,-50%);pointer-events:none;left:100px;top:100px}
#spec{width:100%;height:120px;background:#0a0c11;border:1px solid #232838;border-radius:10px;
 display:block;margin:6px 0 2px}
#rgbprev{font-variant-numeric:tabular-nums}
.mode{display:flex;gap:8px;align-items:center}
.mode input{flex:1;padding:10px;border-radius:10px;border:1px solid #2a3142;background:#0e1118;color:#e7e9ee}
select{width:100%;padding:10px;border-radius:10px;border:1px solid #2a3142;background:#0e1118;
 color:#e7e9ee;margin-bottom:8px;font-size:14px}
#status{margin-top:18px;font-size:12px;color:#7b8395;min-height:16px;
 border-top:1px solid #232838;padding-top:10px}
.val{float:right;color:#5b8cff}
</style></head><body><div class=card>
<h1>LEDDMX&nbsp;Control</h1><div class=sub>strip: LEDDMX-03-1821 · LED LAMP / LEDDMX-03 family</div>

<div class=cols>

  <div class=col>
    <h2>Power &amp; Color</h2>
    <div class=row style=margin-top:0>
      <button class=on onclick="api('/api/power?on=1')">ON</button>
      <button class=off onclick="api('/api/power?on=0')">OFF</button>
    </div>
    <div class=wheelwrap><canvas id=wheel></canvas><div id=marker></div></div>
    <input type=color id=col value="#ff0000" oninput="color(this.value)">
    <div class=swatches id=sw></div>
  </div>

  <div class=col>
    <h2>Adjust &amp; Effects</h2>
    <label>Brightness <span class=val id=bv>60</span></label>
    <input type=range min=1 max=100 value=60 id=br
      oninput="bv.textContent=this.value" onchange="api('/api/bright?v='+this.value)">
    <label>Speed <span class=val id=spv>50</span></label>
    <input type=range min=1 max=100 value=50 id=sp
      oninput="spv.textContent=this.value" onchange="api('/api/speed?v='+this.value)">
    <label>Effect (grouped by family)</label>
    <select id=modeSel onchange="applyMode()"></select>
    <label>Direction <span class=val id=modeNum></span></label>
    <div class=row style=margin-top:0>
      <button id=fwdBtn class=on onclick="setDir(1)">⟶&nbsp;Forward</button>
      <button id=bwdBtn onclick="setDir(0)">⟵&nbsp;Backward</button>
    </div>
    <div class=mode style=margin-top:12px>
      <button onclick="stepNum(-1)">‹&nbsp;Prev</button>
      <input type=number id=md min=1 max=255 value=95>
      <button onclick="stepNum(1)">Next&nbsp;›</button>
      <button style=flex:.7 onclick="goNum()">Go</button>
    </div>
  </div>

  <div class=col>
    <h2>Music Reactive</h2>
    <div class=row style=margin-top:0>
      <button id=musicBtn onclick="toggleMusic()">🎵&nbsp;Music&nbsp;Reactive:&nbsp;OFF</button>
    </div>
    <div id=mpanel style="display:none">
      <label>Live spectrum&nbsp;&nbsp;<span class=val id=rgbprev>—</span></label>
      <canvas id=spec></canvas>
      <label>Bass ‹ Mid split <span class=val id=b1v>250</span> Hz</label>
      <input type=range min=60 max=800 value=250 id=b1 oninput="b1v.textContent=this.value" onchange="cfg()">
      <label>Mid ‹ Treble split <span class=val id=b2v>2000</span> Hz</label>
      <input type=range min=900 max=6000 value=2000 id=b2 oninput="b2v.textContent=this.value" onchange="cfg()">
      <label>Treble top <span class=val id=b3v>6000</span> Hz</label>
      <input type=range min=4000 max=16000 value=6000 id=b3 oninput="b3v.textContent=this.value" onchange="cfg()">
      <label>Sensitivity <span class=val id=sv>100</span>%</label>
      <input type=range min=20 max=300 value=100 id=sens oninput="sv.textContent=this.value" onchange="cfg()">
      <label>Smoothing <span class=val id=smv>50</span>%</label>
      <input type=range min=10 max=90 value=50 id=smooth oninput="smv.textContent=this.value" onchange="cfg()">
    </div>
  </div>

</div>

<div id=status></div>
</div><script>
const SW=["#ff0000","#ff7a00","#ffd400","#33ff00","#00ffd0","#0066ff","#a000ff","#ffffff"];
const swEl=document.getElementById('sw');
SW.forEach(c=>{const d=document.createElement('div');d.className='sw';d.style.background=c;
  d.onclick=()=>{document.getElementById('col').value=c;color(c)};swEl.appendChild(d)});
function status(t,ok){const s=document.getElementById('status');s.textContent=t;
  s.style.color=ok?'#5aa9ff':'#e0667a'}
async function api(u){try{const r=await fetch(u);const j=await r.json();
  status(j.ok?('✓ '+j.sent):('✗ '+j.error),j.ok)}catch(e){status('✗ '+e,false)}}
function color(hex){api('/api/color?hex='+hex.replace('#',''))}
let EFFECTS=[],fwd=true;
async function loadModes(){try{const j=await(await fetch('/api/modes_grouped')).json();
  let html='';EFFECTS=[];
  (j.groups||[]).forEach(g=>{html+=`<optgroup label="${g.family}">`;
    g.effects.forEach(e=>{html+=`<option value="${EFFECTS.length}">${e.name}</option>`;EFFECTS.push(e);});
    html+='</optgroup>';});
  document.getElementById('modeSel').innerHTML=html;applyMode(true);}catch(e){}}
function setDir(f){fwd=!!f;
  document.getElementById('fwdBtn').classList.toggle('on',fwd);
  document.getElementById('bwdBtn').classList.toggle('on',!fwd);applyMode();}
function applyMode(silent){const e=EFFECTS[+document.getElementById('modeSel').value];if(!e)return;
  const oc=('open'in e)||('close'in e),single=('single'in e);
  const fb=document.getElementById('fwdBtn'),bb=document.getElementById('bwdBtn');
  fb.textContent=oc?'⤢ Open':'⟶ Forward';bb.textContent=oc?'⤡ Close':'⟵ Backward';
  fb.disabled=single;bb.disabled=single;fb.style.opacity=single?.4:1;bb.style.opacity=single?.4:1;
  let n=single?e.single:oc?(fwd?(e.open??e.close):(e.close??e.open)):(fwd?(e.fwd??e.bwd):(e.bwd??e.fwd));
  document.getElementById('md').value=n;document.getElementById('modeNum').textContent='#'+n;
  if(!silent)api('/api/mode?m='+n);}
function stepNum(d){const i=document.getElementById('md');
  i.value=Math.max(1,Math.min(200,(parseInt(i.value)||1)+d));goNum();}
function goNum(){let n=Math.max(1,Math.min(255,parseInt(document.getElementById('md').value)||1));
  const s=document.getElementById('modeSel');
  for(let i=0;i<EFFECTS.length;i++){const e=EFFECTS[i];
    if(e.single===n||e.fwd===n||e.open===n){s.value=i;return setDir(1);}
    if(e.bwd===n||e.close===n){s.value=i;return setDir(0);}}
  api('/api/mode?m='+n);}
loadModes();
let musicOn=false;
async function toggleMusic(){musicOn=!musicOn;const b=document.getElementById('musicBtn');
  b.textContent='🎵 Music Reactive: '+(musicOn?'ON':'OFF');b.classList.toggle('on',musicOn);
  document.getElementById('mpanel').style.display=musicOn?'block':'none';
  await api('/api/music?on='+(musicOn?1:0));
  musicOn?startPoll():stopPoll();}
function cfg(){const v=i=>document.getElementById(i).value;
  api('/api/music_cfg?b1='+v('b1')+'&b2='+v('b2')+'&b3='+v('b3')
      +'&sens='+(v('sens')/100)+'&smooth='+(v('smooth')/100));}
// ---- live spectrum analyzer ----
const sc=document.getElementById('spec'),sx=sc.getContext('2d');
function drawSpec(st){const W=sc.width=sc.clientWidth,H=sc.height=sc.clientHeight;
  sx.clearRect(0,0,W,H);
  const sp=st.spectrum||[],fr=st.barfreqs||[],ed=st.edges||[20,250,2000,6000],n=sp.length;
  if(!n)return;const bw=W/n;
  for(let i=0;i<n;i++){const f=fr[i];
    const col=f<ed[1]?'#ff4d4d':f<ed[2]?'#46e06b':'#5b8cff';
    const h=sp[i]*(H-2);sx.fillStyle=col;sx.fillRect(i*bw,H-h,Math.max(1,bw-1),h);}
  sx.strokeStyle='#ffffff66';sx.setLineDash([3,3]);
  [ed[1],ed[2]].forEach(fz=>{let xi=n;for(let i=0;i<n;i++){if(fr[i]>=fz){xi=i;break}}
    const x=xi*bw;sx.beginPath();sx.moveTo(x,0);sx.lineTo(x,H);sx.stroke();});
  sx.setLineDash([]);
  const rgb=st.rgb||[0,0,0],p=document.getElementById('rgbprev');
  p.textContent='rgb('+rgb.join(', ')+')';p.style.color='rgb('+rgb.join(',')+')';}
let poll=null;
function startPoll(){if(poll)return;poll=setInterval(async()=>{
  try{drawSpec(await (await fetch('/api/music_state')).json())}catch(e){}},66);}
function stopPoll(){clearInterval(poll);poll=null;sx.clearRect(0,0,sc.width,sc.height);}

// ---- radial HSV color wheel ----
function hsv2rgb(h,s,v){const c=v*s,x=c*(1-Math.abs((h/60)%2-1)),m=v-c;let r,g,b;
  if(h<60){r=c;g=x;b=0}else if(h<120){r=x;g=c;b=0}else if(h<180){r=0;g=c;b=x}
  else if(h<240){r=0;g=x;b=c}else if(h<300){r=x;g=0;b=c}else{r=c;g=0;b=x}
  return[Math.round((r+m)*255),Math.round((g+m)*255),Math.round((b+m)*255)]}
function hex2(n){return n.toString(16).padStart(2,'0')}
const cv=document.getElementById('wheel'),ctx=cv.getContext('2d'),marker=document.getElementById('marker');
const SZ=220,R=SZ/2;cv.width=SZ;cv.height=SZ;
(function draw(){const img=ctx.createImageData(SZ,SZ);
  for(let y=0;y<SZ;y++)for(let x=0;x<SZ;x++){const dx=x-R,dy=y-R,d=Math.hypot(dx,dy),i=(y*SZ+x)*4;
    if(d>R){img.data[i+3]=0;continue}
    let h=Math.atan2(dy,dx)*180/Math.PI;if(h<0)h+=360;
    const[r,g,b]=hsv2rgb(h,Math.min(1,d/R),1);
    img.data[i]=r;img.data[i+1]=g;img.data[i+2]=b;img.data[i+3]=255}
  ctx.putImageData(img,0,0)})();
let last=0,pend=null,drag=false;
function flush(){if(pend){api('/api/color?hex='+pend);pend=null}}
function pick(e){const rc=cv.getBoundingClientRect();let x=e.clientX-rc.left,y=e.clientY-rc.top;
  let dx=x-R,dy=y-R,d=Math.hypot(dx,dy);
  if(d>R){dx*=R/d;dy*=R/d;x=R+dx;y=R+dy;d=R}
  let h=Math.atan2(dy,dx)*180/Math.PI;if(h<0)h+=360;
  const[r,g,b]=hsv2rgb(h,Math.min(1,d/R),1),hex=hex2(r)+hex2(g)+hex2(b);
  marker.style.left=x+'px';marker.style.top=y+'px';
  document.getElementById('col').value='#'+hex;
  pend=hex;const now=Date.now();if(now-last>80){last=now;flush()}}
cv.addEventListener('pointerdown',e=>{drag=true;cv.setPointerCapture(e.pointerId);pick(e)});
cv.addEventListener('pointermove',e=>{if(drag)pick(e)});
cv.addEventListener('pointerup',()=>{drag=false;flush()});
</script></body></html>"""


def hex_to_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/" or u.path == "/index.html":
            body = PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if not u.path.startswith("/api/"):
            self._json({"ok": False, "error": "not found"}, 404)
            return

        q = parse_qs(u.query)
        try:
            if u.path == "/api/power":
                on = q.get("on", ["1"])[0] == "1"
                ble.write(L.cmd_power(on)); sent = f"power {'on' if on else 'off'}"
            elif u.path == "/api/color":
                r, g, b = hex_to_rgb(q["hex"][0])
                ble.write(L.cmd_power(True)); ble.write(L.cmd_color(r, g, b))
                sent = f"color {r},{g},{b}"
            elif u.path == "/api/bright":
                v = max(1, min(100, int(q["v"][0])))
                ble.write(L.cmd_brightness(v)); sent = f"brightness {v}"
            elif u.path == "/api/speed":
                v = max(1, min(100, int(q["v"][0])))
                ble.write(L.cmd_speed(v)); sent = f"speed {v}"
            elif u.path == "/api/mode":
                m = max(1, min(255, int(q["m"][0])))
                ble.write(L.cmd_mode(m)); sent = f"mode {m}"
            elif u.path == "/api/direction":
                fwd = q.get("d", ["1"])[0] == "1"
                ble.write(L.cmd_direction(fwd)); sent = f"direction {'forward' if fwd else 'backward'}"
            elif u.path == "/api/music":
                on = q.get("on", ["1"])[0] == "1"
                music.start() if on else music.stop()
                sent = f"music {'on' if on else 'off'}"
            elif u.path == "/api/music_cfg":
                music.set_config(b1=q.get("b1", [None])[0], b2=q.get("b2", [None])[0],
                                 b3=q.get("b3", [None])[0], sens=q.get("sens", [None])[0],
                                 alpha=q.get("smooth", [None])[0])
                sent = f"bands {music.edges[1:]} sens {music.sens} smooth {music.alpha}"
            elif u.path == "/api/music_state":
                return self._json({"ok": True, **music.get_state()})
            elif u.path == "/api/modes":
                return self._json({"ok": True, "modes": MODES})
            elif u.path == "/api/modes_grouped":
                return self._json({"ok": True, "groups": GROUPED})
            else:
                return self._json({"ok": False, "error": "unknown endpoint"}, 404)
            self._json({"ok": True, "sent": sent})
        except Exception as e:
            self._json({"ok": False, "error": str(e)}, 500)


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://localhost:{PORT}"
    print(f"LEDDMX web UI running at {url}  (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    srv.serve_forever()
