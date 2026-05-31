import math
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

st.set_page_config(
    page_title="Sand Explorer",
    page_icon="🏖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

GRAINS = {
    "sphere": {
        "name": "Sphere",
        "desc": "Smooth, round. Minimal interlocking.",
        "friction_angle": 25,
        "cohesion": 0.0,
        "jam": 10,
        "jam_label": "Very low",
        "color": "#c8a96e",
        "dark_color": "#9a7840",
        "ref": "Table 1, φ=25°, c=0 kPa",
    },
    "dolosse": {
        "name": "Dolosse",
        "desc": "H-shaped, angular. Mild interlocking.",
        "friction_angle": 38,
        "cohesion": 1.2,
        "jam": 45,
        "jam_label": "Moderate",
        "color": "#b8956a",
        "dark_color": "#8a6b3e",
        "ref": "Table 1, φ=38°, c=1.2 kPa",
    },
    "hexapod": {
        "name": "Hexapod",
        "desc": "Six-armed star. Strong entanglement.",
        "friction_angle": 52,
        "cohesion": 3.8,
        "jam": 72,
        "jam_label": "High",
        "color": "#a07850",
        "dark_color": "#7a5530",
        "ref": "Table 1, φ=52°, c=3.8 kPa",
    },
    "dodecafang": {
        "name": "Dodecafang",
        "desc": "Spiky, highly non-convex. Extreme cohesion.",
        "friction_angle": 68,
        "cohesion": 8.5,
        "jam": 95,
        "jam_label": "Extreme",
        "color": "#8a6030",
        "dark_color": "#5a3a10",
        "ref": "Table 1, φ=68°, c=8.5 kPa",
    },
}

SCENARIO_BEHAVIOR = {
    "flow": {
        "sphere":     "Sand flows freely. The hourglass empties at a steady rate with no clogging.",
        "dolosse":    "Flow is slightly sluggish. Minor bridging near the neck but mostly clears.",
        "hexapod":    "Flow is slow and irregular. Partial jam forms, clears with vibration.",
        "dodecafang": "The neck jams almost immediately. Near-zero flow — this sand refuses to move.",
    },
    "castle": {
        "sphere":     "The castle crumbles quickly. Spheres slide past each other with no resistance.",
        "dolosse":    "The castle holds its shape moderately well before slowly slumping.",
        "hexapod":    "Strong castle — the mound retains shape under significant impact.",
        "dodecafang": "Nearly indestructible. Extreme cohesion keeps every grain locked in place.",
    },
    "bridge": {
        "sphere":     "The arch collapses immediately when support is removed. No cohesion to hold it.",
        "dolosse":    "A thin arch briefly holds before shearing. Marginal bridging possible.",
        "hexapod":    "A sturdy arch forms and holds for several seconds before slowly failing.",
        "dodecafang": "The arch holds indefinitely after support removal — like mortar-free stone.",
    },
}

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Grain shape")
    grain_id = st.radio(
        "grain",
        options=list(GRAINS.keys()),
        format_func=lambda k: f"{GRAINS[k]['name']} — {GRAINS[k]['desc']}",
        label_visibility="collapsed",
    )
    grain = GRAINS[grain_id]

    st.markdown("---")
    st.markdown("## Scenario")
    scenario = st.radio(
        "scenario",
        options=["flow", "castle", "bridge"],
        format_func=lambda s: {
            "flow":   "⏳ Hourglass flow",
            "castle": "🏰 Castle stability",
            "bridge": "🌉 Bridge arch",
        }[s],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown(
        "<small>Based on: *Rigid Body Simulation of Cohesive Granular Materials*, ACM SIGGRAPH 2025</small>",
        unsafe_allow_html=True,
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.title("What shape is your sand?")

# ── Property cards ────────────────────────────────────────────────────────────
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Friction angle φ", f"{grain['friction_angle']}°")
    st.progress(round(grain["friction_angle"] / 75 * 100))
with c2:
    st.metric("Cohesion c", f"{grain['cohesion']:.1f} kPa")
    st.progress(max(1, round(grain["cohesion"] / 10 * 100)))
with c3:
    st.metric("Jam tendency", grain["jam_label"])
    st.progress(grain["jam"])

st.info(
    f"**{grain['name']} — {scenario}:** "
    f"{SCENARIO_BEHAVIOR[scenario][grain_id]}"
)

# ── Simulation ────────────────────────────────────────────────────────────────
st.markdown("### Simulation")

SIM_HTML = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  html, body {{
    width: 100%;
    background: transparent;
    font-family: -apple-system, sans-serif;
    /* never let the body itself scroll — height is reported to parent */
    overflow: hidden;
  }}

  #layout {{
    display: flex;
    flex-direction: column;
    width: 100%;
    gap: 10px;
    padding-bottom: 4px;   /* tiny breathing room at bottom */
  }}

  #wrap {{
    width: 100%;
    background: #f0e8d8;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid rgba(0,0,0,0.12);
    box-shadow: 0 2px 12px rgba(0,0,0,0.08);
    /* height is set dynamically by JS to maintain aspect ratio */
  }}

  canvas {{
    display: block;
    width: 100%;
    height: 100%;
    image-rendering: pixelated;
  }}

  .btns {{
    display: flex;
    gap: 8px;
    flex-shrink: 0;   /* buttons must never be compressed or hidden */
  }}

  .btn-run {{
    flex: 1; padding: 10px;
    background: linear-gradient(135deg, #2bb87a, #1a8f5e);
    color: white; border: none; border-radius: 8px;
    font-size: 14px; font-weight: 600; cursor: pointer;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 6px rgba(27,143,94,0.35);
  }}
  .btn-run:hover {{ background: linear-gradient(135deg, #25a56e, #167a51); }}

  .btn-reset {{
    padding: 10px 18px;
    background: #ede8df; border: 1px solid #c8bfb0;
    border-radius: 8px; font-size: 14px; cursor: pointer; color: #5a4a38;
    flex-shrink: 0;
  }}
  .btn-reset:hover {{ background: #e2dcd2; }}
</style>
</head>
<body>
<div id="layout">
  <div id="wrap"><canvas id="c"></canvas></div>
  <div class="btns">
    <button class="btn-run" onclick="runSim()">▶ Run simulation</button>
    <button class="btn-reset" onclick="resetSim()">↺ Reset</button>
  </div>
</div>

<script>
// ── Canvas / layout resize ────────────────────────────────────────────────
const canvas = document.getElementById('c');
const ctx    = canvas.getContext('2d');
const ASPECT = 720 / 340;

let W = 720, H = 340;

function reportHeight() {{
  // Tell Streamlit the true height of our content so the iframe never clips
  const layout = document.getElementById('layout');
  const totalH = layout.getBoundingClientRect().height || layout.offsetHeight;
  window.parent.postMessage({{
    type: 'streamlit:setFrameHeight',
    height: Math.ceil(totalH) + 8,
  }}, '*');
}}

function resizeCanvas() {{
  const wrap = document.getElementById('wrap');
  const cssW = wrap.clientWidth || 720;
  const cssH = Math.round(cssW / ASPECT);
  const dpr  = window.devicePixelRatio || 1;

  // Drive wrap height so canvas fills it at the correct aspect ratio
  wrap.style.height = cssH + 'px';

  // Physical backing pixels (sharp on retina)
  canvas.width  = Math.round(cssW * dpr);
  canvas.height = Math.round(cssH * dpr);

  canvas.style.width  = cssW + 'px';
  canvas.style.height = cssH + 'px';

  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  W = cssW;
  H = cssH;

  rebuildGridDims();
  grainGrad = null;

  // Always let Streamlit know the new total height
  reportHeight();
}}

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

// ── Spatial hash grid — rebuilt whenever W/H changes ─────────────────────
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

// ── Particle pool ─────────────────────────────────────────────────────────
let pts = [], raf = null, simTime = 0, running = false;

function mkPt(x, y) {{
  return {{ x, y, px: x, py: y, next: null }};  // px/py = previous position (Verlet)
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
  }} else {{ // bridge
    for (let i = 0; i < MAX_PARTICLES; i++) {{
      const left = i < MAX_PARTICLES / 2;
      const cx = left ? W/2 - 82 : W/2 + 82;
      pts.push(mkPt(rnd(cx - 58, cx + 58), rnd(48, H - 56)));
    }}
  }}
}}

// ── Verlet integration step ───────────────────────────────────────────────
function verletStep(impactActive) {{
  const dt = 1.0 / SUBSTEPS;

  for (const p of pts) {{
    const vx = (p.x - p.px) * DAMP_AIR;
    const vy = (p.y - p.py) * DAMP_AIR;

    // Scenario forces
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

    p.px = p.x;
    p.py = p.y;
    p.x  = p.x + vx + fx;
    p.y  = p.y + vy + fy;
  }}
}}

// ── Collision resolution ──────────────────────────────────────────────────
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

      // Position correction (split evenly)
      const corr = overlap * 0.52;
      p.x -= nx * corr; p.y -= ny * corr;
      q.x += nx * corr; q.y += ny * corr;

      // Velocity-level response
      const pvx = p.x - p.px, pvy = p.y - p.py;
      const qvx = q.x - q.px, qvy = q.y - q.py;
      const relVn = (qvx - pvx)*nx + (qvy - pvy)*ny;

      if (relVn < 0) {{
        // Normal impulse with restitution
        const jn = -(1 + RESTITUTION) * relVn * 0.5;
        const inx = jn * nx, iny = jn * ny;

        // Tangential friction impulse
        const tx = -(ny), ty = nx;
        const relVt = (qvx - pvx)*tx + (qvy - pvy)*ty;
        const jt = -relVt * MU * 0.28;
        const itx = jt * tx, ity = jt * ty;

        // Cohesion: small attractive pull when barely touching
        const cohPull = COH * Math.max(0, 1 - d / (diam * 1.15));

        p.px += inx + itx - nx * cohPull;
        p.py += iny + ity - ny * cohPull;
        q.px -= inx + itx + nx * cohPull;
        q.py -= iny + ity + ny * cohPull;
      }}
    }}
  }}
}}

// ── Wall constraints ──────────────────────────────────────────────────────
function applyWalls() {{
  const R = PARTICLE_R;
  const floorY = H - 36;

  for (const p of pts) {{
    const vx = p.x - p.px, vy = p.y - p.py;

    // Floor
    if (p.y > floorY - R) {{
      p.y  = floorY - R;
      p.py = p.y + vy * RESTITUTION;
      p.px = p.x - vx * (1 - MU * 0.35);
    }}

    // Ceiling
    if (p.y < R) {{ p.y = R; p.py = p.y + vy * RESTITUTION; }}

    if (SCENE === 'flow') {{
      // Hourglass walls (linear taper above neck, straight below)
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

      // Hourglass jam logic: probabilistic block at neck
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

      // Gap floor — no floor in the gap if cohesive enough
      const gap = 90;
      const inGap = p.x > W/2 - gap/2 && p.x < W/2 + gap/2;
      if (inGap && p.y > floorY - R) {{
        const holdStrength = MU * (1 + COH * 6);
        if (holdStrength < 0.55) {{
          // falls through
        }} else {{
          p.y  = floorY - R;
          p.py = p.y + vy * RESTITUTION * 0.3;
        }}
      }}

    }} else {{ // castle
      if (p.x < R) {{ p.x = R; p.px = p.x + vx * RESTITUTION; }}
      if (p.x > W - R) {{ p.x = W - R; p.px = p.x + vx * RESTITUTION; }}
    }}
  }}
}}

// ── Rendering ─────────────────────────────────────────────────────────────
// Pre-build a radial gradient template for grain shading
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
  const lr = Math.min(255, r + (255-r)*amt)|0;
  const lg = Math.min(255, g2 + (255-g2)*amt)|0;
  const lb = Math.min(255, b + (255-b)*amt)|0;
  return `rgb(${{lr}},${{lg}},${{lb}})`;
}}

function drawBackground() {{
  // Sandy base
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
    // Left wall
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(W/2 - NECK_HALF - 96, 0);
    ctx.lineTo(W/2 - NECK_HALF, nY);
    ctx.lineTo(W/2 - NECK_HALF, H);
    ctx.lineTo(0, H);
    ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Right wall
    ctx.beginPath();
    ctx.moveTo(W, 0);
    ctx.lineTo(W/2 + NECK_HALF + 96, 0);
    ctx.lineTo(W/2 + NECK_HALF, nY);
    ctx.lineTo(W/2 + NECK_HALF, H);
    ctx.lineTo(W, H);
    ctx.closePath();
    ctx.fill(); ctx.stroke();

  }} else if (SCENE === 'bridge') {{
    const pillarW = 56, archH = 50;
    // Left pillar
    ctx.beginPath();
    ctx.moveTo(0, 0); ctx.lineTo(pillarW, 0);
    ctx.lineTo(pillarW, H - 36 - archH);
    ctx.quadraticCurveTo(pillarW, H-36, pillarW + archH*0.6, H-36);
    ctx.lineTo(0, H-36); ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Right pillar
    ctx.beginPath();
    ctx.moveTo(W, 0); ctx.lineTo(W - pillarW, 0);
    ctx.lineTo(W - pillarW, H - 36 - archH);
    ctx.quadraticCurveTo(W - pillarW, H-36, W - pillarW - archH*0.6, H-36);
    ctx.lineTo(W, H-36); ctx.closePath();
    ctx.fill(); ctx.stroke();
    // Floor (outside gap)
    ctx.fillRect(0, H - 36, pillarW + 56, 36);
    ctx.fillRect(W - pillarW - 56, H - 36, pillarW + 56, 36);
    ctx.strokeRect(0, H - 36, W, 36);

  }} else {{ // castle — flat ground
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
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.fillStyle = grad;
    ctx.fill();
    ctx.strokeStyle = G.darkColor;
    ctx.lineWidth = 0.6;
    ctx.stroke();
    ctx.restore();
  }}
}}

function drawStatic() {{
  drawBackground();
  // Draw a settled pile preview
  ctx.fillStyle = G.color;
  ctx.strokeStyle = G.darkColor;
  ctx.lineWidth = 0.5;

  function dot(x, y) {{
    ctx.save(); ctx.translate(x, y);
    ctx.beginPath(); ctx.arc(0, 0, PARTICLE_R, 0, Math.PI*2);
    const g = getGrainGrad(PARTICLE_R);
    ctx.fillStyle = g; ctx.fill(); ctx.strokeStyle = G.darkColor; ctx.stroke();
    ctx.restore();
  }}

  if (SCENE === 'flow') {{
    for (let i = 0; i < 72; i++)
      dot(rnd(W/2-82, W/2+82), rnd(14, 138));
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

  // Prompt overlay
  ctx.fillStyle = 'rgba(255,248,235,0.72)';
  ctx.beginPath();
  ctx.roundRect(W/2 - 150, H/2 - 18, 300, 36, 8);
  ctx.fill();
  ctx.fillStyle = 'rgba(80,55,25,0.75)';
  ctx.font = '600 13px -apple-system, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('Press  ▶ Run simulation  to animate', W/2, H/2 + 5);
  ctx.textAlign = 'left';
}}

// ── Main loop ─────────────────────────────────────────────────────────────
function runSim() {{
  if (raf) cancelAnimationFrame(raf);
  resizeCanvas();           // always sync to current rendered size first
  simTime = 0; running = true;
  grainGrad = null;
  init();

  function loop() {{
    simTime++;
    const impactActive = SCENE === 'castle' && simTime > 72 && simTime < 142;

    // Sub-stepping for stability
    for (let s = 0; s < SUBSTEPS; s++) {{
      verletStep(impactActive);
      resolveCollisions();
      applyWalls();
    }}

    drawBackground();

    // Impact ring
    if (impactActive) {{
      const phase = (simTime - 72) / 70;
      const ringR = phase * 55;
      ctx.strokeStyle = `rgba(210,90,30,${{(1-phase)*0.5}})`;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.arc(W/2, H - 95, ringR, 0, Math.PI*2);
      ctx.stroke();
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

// ── Resize handling ───────────────────────────────────────────────────────
const ro = new ResizeObserver(() => {{
  resizeCanvas();
  if (!running) drawStatic();
  reportHeight();
}});
// Observe the outer layout div so button height changes are caught too
ro.observe(document.getElementById('layout'));

document.addEventListener('fullscreenchange', () => {{
  resizeCanvas();
  if (!running) drawStatic();
  reportHeight();
}});

// Initial paint
resizeCanvas();
drawStatic();
reportHeight();
</script>
</body>
</html>"""

components.html(SIM_HTML, height=500, scrolling=False)

# ── Yield surface ─────────────────────────────────────────────────────────────
st.markdown("### Mohr-Coulomb yield surface")

sigma = list(range(0, 151, 5))
chart_data = {}
for gid, g in GRAINS.items():
    phi_r = math.radians(g["friction_angle"])
    chart_data[g["name"]] = [round(g["cohesion"] + s * math.tan(phi_r), 2) for s in sigma]

df = pd.DataFrame(chart_data, index=sigma)
df.index.name = "Normal stress σ (kPa)"
st.line_chart(df, height=280)

# ── Grain comparison table ────────────────────────────────────────────────────
with st.expander("Full grain properties table"):
    rows = []
    for gid, g in GRAINS.items():
        phi = g["friction_angle"]
        rows.append({
            "Grain": g["name"],
            "Shape class": "convex" if gid == "sphere" else "non-convex",
            "φ (°)": phi,
            "c (kPa)": g["cohesion"],
            "tan(φ)": round(math.tan(math.radians(phi)), 3),
            "Jam tendency": g["jam_label"],
            "Paper ref": g["ref"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with st.expander("Drucker-Prager 3D yield parameters"):
    st.caption("α = 2·sin(φ) / (√3·(3−sin(φ))),   k = 6·c·cos(φ) / (√3·(3−sin(φ)))")
    dp_rows = []
    for gid, g in GRAINS.items():
        phi = math.radians(g["friction_angle"])
        sp, cp = math.sin(phi), math.cos(phi)
        dp_rows.append({
            "Grain": g["name"],
            "α": round(2*sp / (math.sqrt(3)*(3-sp)), 4),
            "k (kPa)": round(6*g["cohesion"]*cp / (math.sqrt(3)*(3-sp)), 4),
        })
    st.dataframe(pd.DataFrame(dp_rows), use_container_width=True, hide_index=True)
