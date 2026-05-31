SIM_HTML = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  html, body {{
    width: 100%;
    background: transparent;
    font-family: -apple-system, sans-serif;
    overflow: hidden;
  }}

  #layout {{
    display: flex;
    flex-direction: column;
    width: 100%;
    gap: 10px;
    padding-bottom: 8px;
  }}

  #wrap {{
    width: 100%;
    background: #f0e8d8;
    border-radius: 12px;
    border: 1px solid rgba(0,0,0,0.12);
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    /* NO overflow:hidden here — it was swallowing the canvas on resize */
    flex-shrink: 0;
  }}

  canvas {{
    display: block;
    width: 100%;
    border-radius: 12px;
    image-rendering: pixelated;
  }}

  .btns {{
    display: flex;
    gap: 8px;
    flex-shrink: 0;
    min-height: 44px;    /* guarantee the row always has space */
  }}

  .btn-run {{
    flex: 1; padding: 10px;
    background: linear-gradient(135deg, #2bb87a, #1a8f5e);
    color: white; border: none; border-radius: 8px;
    font-size: 14px; font-weight: 600; cursor: pointer;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 6px rgba(27,143,94,0.35);
    min-width: 0;        /* flex children can shrink below content width */
  }}
  .btn-run:hover {{ background: linear-gradient(135deg, #25a56e, #167a51); }}

  .btn-reset {{
    padding: 10px 18px;
    background: #ede8df; border: 1px solid #c8bfb0;
    border-radius: 8px; font-size: 14px; cursor: pointer; color: #5a4a38;
    flex-shrink: 0;
    white-space: nowrap;
  }}
  .btn-reset:hover {{ background: #e2dcd2; }}
</style>
</head>
<body>
<div id="layout">
  <div id="wrap"><canvas id="c"></canvas></div>
  <div class="btns">
    <button class="btn-run" onclick="runSim()">&#9654; Run simulation</button>
    <button class="btn-reset" onclick="resetSim()">&#8635; Reset</button>
  </div>
</div>

<script>
const canvas = document.getElementById('c');
const ctx    = canvas.getContext('2d');
const ASPECT = 720 / 340;

let W = 720, H = 340;

function reportHeight() {{
  const layout = document.getElementById('layout');
  // Use scrollHeight so we catch content even if it overflows the iframe
  const h = Math.max(
    layout.scrollHeight,
    layout.getBoundingClientRect().height
  );
  window.parent.postMessage({{
    type: 'streamlit:setFrameHeight',
    height: Math.ceil(h) + 16,   // 16px extra safety margin
  }}, '*');
}}

function resizeCanvas() {{
  const wrap = document.getElementById('wrap');
  const cssW = wrap.clientWidth || 720;
  const cssH = Math.round(cssW / ASPECT);
  const dpr  = Math.min(window.devicePixelRatio || 1, 2); // cap at 2× — no need for 3×

  wrap.style.height = cssH + 'px';

  canvas.width  = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);
  canvas.style.width  = cssW + 'px';
  canvas.style.height = cssH + 'px';

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  W = cssW;
  H = cssH;

  rebuildGridDims();
  grainGrad = null;

  // Report height AFTER the DOM has settled — requestAnimationFrame
  // ensures the browser has painted wrap's new height before we measure
  requestAnimationFrame(reportHeight);
}}

// ── The rest of your JS is unchanged below ───────────────────────────────

const PARTICLE_R = 5;
const SUBSTEPS = 4;
const MAX_PARTICLES = 260;

const G = {{
  frictionAngle: {grain["friction_angle"]},
  cohesion:      {grain["cohesion"]},
  jam:           {grain["jam"]},
  color:         "{grain["color"]}",
  darkColor:     "{grain["dark_color"]}",
}};

const SCENE = "{scenario}";

const phi         = G.frictionAngle * Math.PI / 180;
const MU          = Math.tan(phi);
const COH         = G.cohesion * 0.006;
const RESTITUTION = Math.max(0.02, 0.18 - MU * 0.14);
const DAMP_AIR    = 1.0 - (0.008 + MU * 0.012);
const GRAVITY     = 0.38 / SUBSTEPS;
const FLOW_RATE   = 1.0 - G.jam / 118;
const NECK_HALF   = 16 + (1 - FLOW_RATE) * 26;

const CELL = PARTICLE_R * 2.2;
let COLS, ROWS, grid;

function rebuildGridDims() {{
  COLS = Math.ceil(W / CELL) + 1;
  ROWS = Math.ceil(H / CELL) + 1;
  grid = new Array(COLS * ROWS);
}}

function gridKey(x, y) {{
  return (Math.floor(x / CELL) | 0) + (Math.floor(y / CELL) | 0) * COLS;
}}

function buildGrid(pts) {{
  grid.fill(null);
  for (let i = 0; i < pts.length; i++) {{
    const k = gridKey(pts[i].x, pts[i].y);
    pts[i].next = grid[k];
    grid[k] = i;
  }}
}}

function* neighbors(pts, x, y) {{
  const cx = Math.floor(x / CELL) | 0;
  const cy = Math.floor(y / CELL) | 0;
  for (let dx = -1; dx <= 1; dx++) {{
    for (let dy = -1; dy <= 1; dy++) {{
      const nx = cx + dx, ny2 = cy + dy;
      if (nx < 0 || nx >= COLS || ny2 < 0 || ny2 >= ROWS) continue;
      let idx = grid[nx + ny2 * COLS];
      while (idx !== null && idx !== undefined) {{
        yield idx;
        idx = pts[idx].next;
      }}
    }}
  }}
}}

let pts = [], raf = null, simTime = 0, running = false;

function mkPt(x, y) {{
  return {{ x, y, px: x, py: y, next: null }};
}}

function rnd(a, b) {{ return a + Math.random() * (b - a); }}

function init() {{
  pts = [];
  if (SCENE === 'flow') {{
    const count = Math.min(MAX_PARTICLES, 210);
    for (let i = 0; i < count; i++) {{
      const x = rnd(W/2 - 86, W/2 + 86);
      const y = rnd(14 + (i / count) * 110, 26 + (i / count) * 120);
      pts.push(mkPt(x, y));
    }}
  }} else if (SCENE === 'castle') {{
    for (let i = 0; i < MAX_PARTICLES; i++) {{
      const t = i / MAX_PARTICLES;
      const spread = Math.max(16, 164 - i * 0.42);
      const x = rnd(W/2 - spread/2, W/2 + spread/2);
      const y = H - 48 - i * 0.62 + rnd(0, 5);
      pts.push(mkPt(x, y));
    }}
  }} else {{
    for (let i = 0; i < MAX_PARTICLES; i++) {{
      const left = i < MAX_PARTICLES / 2;
      const cx = left ? W/2 - 82 : W/2 + 82;
      pts.push(mkPt(rnd(cx - 58, cx + 58), rnd(48, H - 56)));
    }}
  }}
}}

function verletStep(impactActive) {{
  for (const p of pts) {{
    const vx = (p.x - p.px) * DAMP_AIR;
    const vy = (p.y - p.py) * DAMP_AIR;
    let fx = 0, fy = GRAVITY;

    if (SCENE === 'castle' && impactActive) {{
      const strength = (1 - G.cohesion / 12) * 0.55;
      const dx = p.x - W/2, dy = p.y - (H - 95);
      const d  = Math.sqrt(dx*dx + dy*dy);
      if (d < 80 && d > 0.1) {{
        fx += (dx/d) * strength * (1 - d/80);
        fy += (dy/d) * strength * (1 - d/80) - 0.2;
      }}
    }}

    if (SCENE === 'bridge' && simTime > 110) {{
      const archHold = MU * (1 + COH * 8);
      fy += Math.max(0, 0.28 - archHold * 0.22);
    }}

    p.px = p.x; p.py = p.y;
    p.x  = p.x + vx + fx;
    p.y  = p.y + vy + fy;
  }}
}}

function resolveCollisions() {{
  buildGrid(pts);
  const diam = PARTICLE_R * 2;
  const seen = new Set();

  for (let i = 0; i < pts.length; i++) {{
    const p = pts[i];
    for (const j of neighbors(pts, p.x, p.y)) {{
      if (j <= i) continue;
      const key = i * 10000 + j;
      if (seen.has(key)) continue;
      seen.add(key);

      const q  = pts[j];
      const dx = q.x - p.x, dy = q.y - p.y;
      const d2 = dx*dx + dy*dy;
      if (d2 >= diam*diam || d2 < 0.0001) continue;

      const d      = Math.sqrt(d2);
      const nx     = dx/d, ny = dy/d;
      const overlap = (diam - d) * 0.5;
      const corr = overlap * 0.52;
      p.x -= nx * corr; p.y -= ny * corr;
      q.x += nx * corr; q.y += ny * corr;

      const pvx = p.x - p.px, pvy = p.y - p.py;
      const qvx = q.x - q.px, qvy = q.y - q.py;
      const relVn = (qvx - pvx)*nx + (qvy - pvy)*ny;

      if (relVn < 0) {{
        const jn = -(1 + RESTITUTION) * relVn * 0.5;
        const inx = jn * nx, iny = jn * ny;
        const tx = -(ny), ty = nx;
        const relVt = (qvx - pvx)*tx + (qvy - pvy)*ty;
        const jt = -relVt * MU * 0.28;
        const itx = jt * tx, ity = jt * ty;
        const cohPull = COH * Math.max(0, 1 - d / (diam * 1.15));

        p.px += inx + itx - nx * cohPull;
        p.py += iny + ity - ny * cohPull;
        q.px -= inx + itx + nx * cohPull;
        q.py -= iny + ity + ny * cohPull;
      }}
    }}
  }}
}}

function applyWalls() {{
  const R = PARTICLE_R;
  const floorY = H - 36;

  for (const p of pts) {{
    const vx = p.x - p.px, vy = p.y - p.py;

    if (p.y > floorY - R) {{
      p.y  = floorY - R;
      p.py = p.y + vy * RESTITUTION;
      p.px = p.x - vx * (1 - MU * 0.35);
    }}

    if (p.y < R) {{ p.y = R; p.py = p.y + vy * RESTITUTION; }}

    if (SCENE === 'flow') {{
      const neckY  = H * 0.53;
      const taper  = Math.max(0, (neckY - p.y) / neckY);
      const wallW  = NECK_HALF + taper * 96;
      const leftW  = W/2 - wallW;
      const rightW = W/2 + wallW;

      if (p.x < leftW + R) {{
        p.x  = leftW + R;
        p.px = p.x + vx * RESTITUTION;
        p.py = p.y - vy * MU * 0.2;
      }}
      if (p.x > rightW - R) {{
        p.x  = rightW - R;
        p.px = p.x + vx * RESTITUTION;
        p.py = p.y - vy * MU * 0.2;
      }}

      if (Math.abs(p.x - W/2) < NECK_HALF + R && p.y > neckY - 12 && p.y < neckY + 12) {{
        const jamProb = G.jam / 100 * 0.12;
        if (Math.random() < jamProb) {{
          p.x  = p.px;
          p.px = p.x + (rnd(-0.4, 0.4));
          p.py = p.y;
        }}
      }}

    }} else if (SCENE === 'bridge') {{
      const pillarW = 56;
      if (p.x < pillarW + R) {{
        p.x  = pillarW + R;
        p.px = p.x + vx * RESTITUTION;
      }}
      if (p.x > W - pillarW - R) {{
        p.x  = W - pillarW - R;
        p.px = p.x + vx * RESTITUTION;
      }}

      const gap = 90;
      const inGap = p.x > W/2 - gap/2 && p.x < W/2 + gap/2;
      if (inGap && p.y > floorY - R) {{
        const holdStrength = MU * (1 + COH * 6);
        if (holdStrength >= 0.55) {{
          p.y  = floorY - R;
          p.py = p.y + vy * RESTITUTION * 0.3;
        }}
      }}

    }} else {{
      if (p.x < R) {{ p.x = R; p.px = p.x + vx * RESTITUTION; }}
      if (p.x > W - R) {{ p.x = W - R; p.px = p.x + vx * RESTITUTION; }}
    }}
  }}
}}

let grainGrad = null;
function getGrainGrad(r) {{
  if (grainGrad) return grainGrad;
  const og = ctx.createRadialGradient(-r*0.3, -r*0.3, r*0.05, 0, 0, r);
  og.addColorStop(0, lighten(G.color, 0.28));
  og.addColorStop(0.5, G.color);
  og.addColorStop(1, G.darkColor);
  grainGrad = og;
  return og;
}}

function lighten(hex, amt) {{
  const r = parseInt(hex.slice(1,3),16), g2 = parseInt(hex.slice(3,5),16), b = parseInt(hex.slice(5,7),16);
  return `rgb(${{Math.min(255,r+(255-r)*amt)|0}},${{Math.min(255,g2+(255-g2)*amt)|0}},${{Math.min(255,b+(255-b)*amt)|0}})`;
}}

function drawBackground() {{
  const bgGrad = ctx.createLinearGradient(0, 0, 0, H);
  bgGrad.addColorStop(0, '#ede3d0');
  bgGrad.addColorStop(1, '#e0d4be');
  ctx.fillStyle = bgGrad;
  ctx.fillRect(0, 0, W, H);

  ctx.fillStyle   = '#c8b898';
  ctx.strokeStyle = '#a89878';
  ctx.lineWidth   = 1.5;

  if (SCENE === 'flow') {{
    const nY = H * 0.53;
    ctx.beginPath();
    ctx.moveTo(0, 0); ctx.lineTo(W/2 - NECK_HALF - 96, 0);
    ctx.lineTo(W/2 - NECK_HALF, nY); ctx.lineTo(W/2 - NECK_HALF, H);
    ctx.lineTo(0, H); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(W, 0); ctx.lineTo(W/2 + NECK_HALF + 96, 0);
    ctx.lineTo(W/2 + NECK_HALF, nY); ctx.lineTo(W/2 + NECK_HALF, H);
    ctx.lineTo(W, H); ctx.closePath(); ctx.fill(); ctx.stroke();

  }} else if (SCENE === 'bridge') {{
    const pillarW = 56, archH = 50;
    ctx.beginPath();
    ctx.moveTo(0, 0); ctx.lineTo(pillarW, 0);
    ctx.lineTo(pillarW, H - 36 - archH);
    ctx.quadraticCurveTo(pillarW, H-36, pillarW + archH*0.6, H-36);
    ctx.lineTo(0, H-36); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(W, 0); ctx.lineTo(W - pillarW, 0);
    ctx.lineTo(W - pillarW, H - 36 - archH);
    ctx.quadraticCurveTo(W - pillarW, H-36, W - pillarW - archH*0.6, H-36);
    ctx.lineTo(W, H-36); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillRect(0, H - 36, pillarW + 56, 36);
    ctx.fillRect(W - pillarW - 56, H - 36, pillarW + 56, 36);
    ctx.strokeRect(0, H - 36, W, 36);

  }} else {{
    ctx.fillRect(0, H - 36, W, 36);
    ctx.beginPath(); ctx.moveTo(0, H-36); ctx.lineTo(W, H-36); ctx.stroke();
  }}
}}

function drawParticles() {{
  const r = PARTICLE_R;
  const grad = getGrainGrad(r);
  for (const p of pts) {{
    ctx.save();
    ctx.translate(p.x, p.y);
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fillStyle = grad; ctx.fill();
    ctx.strokeStyle = G.darkColor; ctx.lineWidth = 0.6; ctx.stroke();
    ctx.restore();
  }}
}}

function drawStatic() {{
  drawBackground();
  function dot(x, y) {{
    ctx.save(); ctx.translate(x, y);
    ctx.beginPath(); ctx.arc(0, 0, PARTICLE_R, 0, Math.PI*2);
    ctx.fillStyle = getGrainGrad(PARTICLE_R); ctx.fill();
    ctx.strokeStyle = G.darkColor; ctx.stroke();
    ctx.restore();
  }}
  if (SCENE === 'flow') {{
    for (let i = 0; i < 72; i++) dot(rnd(W/2-82, W/2+82), rnd(14, 138));
  }} else if (SCENE === 'bridge') {{
    for (let i = 0; i < 88; i++) {{
      const left = i < 44, cx = left ? W/2-80 : W/2+80;
      dot(rnd(cx-54, cx+54), rnd(36, H-54));
    }}
  }} else {{
    for (let i = 0; i < 180; i++) {{
      const a = Math.random()*Math.PI, r2 = Math.random()*(72+i*0.22);
      const x = W/2 + Math.cos(a)*r2*1.18;
      const y = H-36 - Math.abs(Math.sin(a)*r2)*0.72;
      if (x > 12 && x < W-12 && y > 0 && y < H-36) dot(x, y);
    }}
  }}
  ctx.fillStyle = 'rgba(255,248,235,0.72)';
  ctx.beginPath(); ctx.roundRect(W/2 - 150, H/2 - 18, 300, 36, 8); ctx.fill();
  ctx.fillStyle = 'rgba(80,55,25,0.75)';
  ctx.font = '600 13px -apple-system, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Press  \u25b6 Run simulation  to animate', W/2, H/2 + 5);
  ctx.textAlign = 'left';
}}

function runSim() {{
  if (raf) cancelAnimationFrame(raf);
  resizeCanvas();
  simTime = 0; running = true;
  grainGrad = null;
  init();

  function loop() {{
    simTime++;
    const impactActive = SCENE === 'castle' && simTime > 72 && simTime < 142;

    for (let s = 0; s < SUBSTEPS; s++) {{
      verletStep(impactActive);
      resolveCollisions();
      applyWalls();
    }}

    drawBackground();

    if (impactActive) {{
      const phase = (simTime - 72) / 70;
      const ringR = phase * 55;
      ctx.strokeStyle = `rgba(210,90,30,${{(1-phase)*0.5}})`;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(W/2, H - 95, ringR, 0, Math.PI*2); ctx.stroke();
    }}

    drawParticles();
    if (simTime < 420) raf = requestAnimationFrame(loop);
    else running = false;
  }}
  loop();
}}

function resetSim() {{
  if (raf) {{ cancelAnimationFrame(raf); raf = null; }}
  running = false;
  resizeCanvas();
  drawStatic();
}}

// ── Resize observer on the layout div ───────────────────────────────────
const ro = new ResizeObserver(() => {{
  resizeCanvas();
  if (!running) drawStatic();
}});
ro.observe(document.getElementById('layout'));

document.addEventListener('fullscreenchange', () => {{
  resizeCanvas();
  if (!running) drawStatic();
}});

resizeCanvas();
drawStatic();
// Fire one extra reportHeight after fonts/layout settle
setTimeout(reportHeight, 120);
</script>
</body>
</html>"""