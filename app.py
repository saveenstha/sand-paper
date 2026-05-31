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
            "flow": "⏳ Hourglass flow",
            "castle": "🏰 Castle stability",
            "bridge": "🌉 Bridge arch",
        }[s],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.caption(
        "Based on: *Rigid Body Simulation of Cohesive Granular Materials*, "
        "ACM SIGGRAPH 2025"
    )

# ── Header ────────────────────────────────────────────────────────────────────
st.title("What shape is your sand?")
st.caption(
    "Grain shape alone controls how sand flows, holds together, or locks up. "
    "Pick a grain and scenario in the sidebar, then run the simulation."
)

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
    f"**{grain['name']} — {scenario} behavior:** "
    f"{SCENARIO_BEHAVIOR[scenario][grain_id]}"
)

# ── Simulation (HTML5 canvas embedded via components.html) ────────────────────
st.markdown("### Simulation")
st.caption("The physics engine runs entirely in your browser via an embedded canvas component.")

SIM_HTML = f"""<!DOCTYPE html>
<html>
<head>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: transparent; font-family: -apple-system, sans-serif; }}
  #wrap {{ background: #f5efe6; border-radius: 10px; overflow: hidden; border: 1px solid rgba(0,0,0,0.1); }}
  canvas {{ display: block; width: 100%; }}
  .btns {{ display: flex; gap: 8px; margin-top: 10px; }}
  .btn-run {{ flex: 1; padding: 9px; background: #1D9E75; color: white; border: none;
              border-radius: 8px; font-size: 14px; font-weight: 500; cursor: pointer; }}
  .btn-run:hover {{ background: #18876a; }}
  .btn-reset {{ padding: 9px 16px; background: #f0ede6; border: 1px solid #ccc;
                border-radius: 8px; font-size: 14px; cursor: pointer; }}
  .btn-reset:hover {{ background: #e4e0d8; }}
</style>
</head>
<body>
<div id="wrap"><canvas id="c" width="700" height="320"></canvas></div>
<div class="btns">
  <button class="btn-run" onclick="runSim()">▶ Run simulation</button>
  <button class="btn-reset" onclick="resetSim()">↺ Reset</button>
</div>
<script>
const W = 700, H = 320;
const G = {{
  friction: {grain["friction_angle"]},
  cohesion: {grain["cohesion"]},
  jam: {grain["jam"]},
  color: "{grain["color"]}",
  darkColor: "{grain["dark_color"]}"
}};
const SCENE = "{scenario}";

const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
let pts = [], raf = null, t = 0;

function rnd(a, b) {{ return a + Math.random() * (b - a); }}

function init() {{
  pts = [];
  const r = 5;
  if (SCENE === 'flow') {{
    for (let i = 0; i < 210; i++)
      pts.push({{ x: rnd(W/2-88, W/2+88), y: rnd(16, 132), vx: 0, vy: 0, r }});
  }} else if (SCENE === 'castle') {{
    for (let i = 0; i < 290; i++) {{
      const sp = Math.max(18, 172 - i * 0.44);
      pts.push({{ x: rnd(W/2-sp/2, W/2+sp/2), y: H-54 - i*0.65 + rnd(0,6), vx: 0, vy: 0, r }});
    }}
  }} else {{
    for (let i = 0; i < 270; i++) {{
      const left = i < 135, cx = left ? W/2-80 : W/2+80;
      pts.push({{ x: rnd(cx-56, cx+56), y: rnd(52, H-54), vx: 0, vy: 0, r }});
    }}
  }}
}}

function step() {{
  const fr = G.friction / 100, co = G.cohesion / 10;
  const damp = 0.55 + fr * 0.3;
  const flowRate = 1.0 - G.jam / 115, nH = 18 + (1 - flowRate) * 22;

  for (const p of pts) {{
    p.vy += 0.26;
    if (SCENE === 'flow') {{
      if (p.y > 148 && p.y < 214) {{
        const d = Math.abs(p.x - W/2);
        if (d < nH + 4) {{
          if (Math.random() < (G.jam/100)*0.15) {{ p.vx *= 0.3; p.vy *= 0.1; }}
          else p.vx += (p.x < W/2 ? -1 : 1) * 0.3;
        }}
      }}
      if (p.y > H-38) {{ p.y = H-38; p.vy *= -0.1; p.vx *= damp; }}
    }}
    if (SCENE === 'castle') {{
      if (t > 80 && t < 148) {{
        const f = (1 - co*0.6)*0.85;
        if (Math.abs(p.x-W/2) < 66 && p.y > H-172)
          {{ p.vx += (Math.random()-0.5)*f; p.vy -= Math.random()*f*0.5; }}
      }}
      if (p.y > H-38) {{ p.y=H-38; p.vy *= -(0.05+co*0.1); p.vx *= damp+co*0.2; }}
    }}
    if (SCENE === 'bridge') {{
      if (t > 100) p.vy += Math.max(0, 0.008-(co*fr)*0.001)*2;
      if (p.y > H-38) {{ p.y=H-38; p.vy *= -0.05; p.vx *= damp; }}
      const gap = 84;
      if (p.x > W/2-gap/2 && p.x < W/2+gap/2 && p.y > H-120)
        {{ if (co < 3) p.vy += 0.4; else {{ p.vy *= 0.3; p.vx *= 0.3; }} }}
    }}
  }}

  for (let i = 0; i < pts.length; i++) {{
    for (let j = i+1; j < pts.length; j++) {{
      const p = pts[i], q = pts[j];
      const dx=q.x-p.x, dy=q.y-p.y, d2=dx*dx+dy*dy, mD=p.r+q.r;
      if (d2 < mD*mD && d2 > 0.01) {{
        const d=Math.sqrt(d2), nx=dx/d, ny=dy/d, ov=(mD-d)*0.4;
        p.x-=nx*ov; p.y-=ny*ov; q.x+=nx*ov; q.y+=ny*ov;
        const rv=(q.vx-p.vx)*nx+(q.vy-p.vy)*ny;
        if (rv < 0) {{
          const imp=rv*(0.3-Math.min(co*0.05,0.3));
          p.vx-=imp*nx*0.5; p.vy-=imp*ny*0.5; q.vx+=imp*nx*0.5; q.vy+=imp*ny*0.5;
        }}
        const fd=1-fr*0.08;
        p.vx*=fd; p.vy*=fd; q.vx*=fd; q.vy*=fd;
      }}
    }}
  }}

  const nH2 = 18+(1-(1-G.jam/115))*22;
  for (const p of pts) {{
    if (SCENE === 'flow') {{
      const wl=W/2-108-(p.y/H)*38, wr=W/2+108+(p.y/H)*38;
      const inN=p.y>148&&p.y<214;
      const lb=inN?W/2-nH2:wl, rb=inN?W/2+nH2:wr;
      if(p.x<lb){{p.x=lb;p.vx=Math.abs(p.vx)*0.3;}}
      if(p.x>rb){{p.x=rb;p.vx=-Math.abs(p.vx)*0.3;}}
    }} else if (SCENE==='bridge') {{
      if(p.x<58){{p.x=58;p.vx=Math.abs(p.vx)*0.3;}}
      if(p.x>W-58){{p.x=W-58;p.vx=-Math.abs(p.vx)*0.3;}}
    }} else {{
      if(p.x<18){{p.x=18;p.vx=Math.abs(p.vx)*0.3;}}
      if(p.x>W-18){{p.x=W-18;p.vx=-Math.abs(p.vx)*0.3;}}
    }}
    p.x+=p.vx; p.y+=p.vy;
    if(p.y<0){{p.y=0;p.vy=Math.abs(p.vy)*0.3;}}
  }}
}}

function drawBg() {{
  ctx.fillStyle='#f5efe6'; ctx.fillRect(0,0,W,H);
  ctx.fillStyle='#d4c4a8'; ctx.strokeStyle='#9a8060'; ctx.lineWidth=1.5;
  const nH=18+(1-(1-G.jam/115))*22;
  if (SCENE==='flow') {{
    ctx.beginPath(); ctx.moveTo(0,0); ctx.lineTo(W/2-108,0); ctx.lineTo(W/2-nH,183); ctx.lineTo(W/2-nH,H); ctx.lineTo(0,H); ctx.fill();
    ctx.beginPath(); ctx.moveTo(W,0); ctx.lineTo(W/2+108,0); ctx.lineTo(W/2+nH,183); ctx.lineTo(W/2+nH,H); ctx.lineTo(W,H); ctx.fill();
    [[W/2-108,0,W/2-nH,183],[W/2+108,0,W/2+nH,183],[W/2-nH,183,W/2-nH,H],[W/2+nH,183,W/2+nH,H]]
      .forEach(([x1,y1,x2,y2])=>{{ctx.beginPath();ctx.moveTo(x1,y1);ctx.lineTo(x2,y2);ctx.stroke();}});
  }} else if (SCENE==='bridge') {{
    ctx.fillRect(0,0,58,H-38); ctx.fillRect(W-58,0,58,H-38); ctx.fillRect(0,H-38,W,38);
    ctx.strokeRect(0,0,58,H-38); ctx.strokeRect(W-58,0,58,H-38); ctx.strokeRect(0,H-38,W,38);
  }} else {{
    ctx.fillRect(0,H-38,W,38);
    ctx.beginPath(); ctx.moveTo(0,H-38); ctx.lineTo(W,H-38); ctx.stroke();
  }}
}}

function drawParticles() {{
  for (const p of pts) {{
    ctx.beginPath(); ctx.arc(p.x,p.y,p.r,0,Math.PI*2);
    ctx.fillStyle=G.color; ctx.fill();
    ctx.strokeStyle=G.darkColor; ctx.lineWidth=0.5; ctx.stroke();
  }}
}}

function drawStatic() {{
  drawBg();
  ctx.fillStyle=G.color;
  if(SCENE==='flow'){{
    for(let i=0;i<78;i++){{ctx.beginPath();ctx.arc(rnd(W/2-85,W/2+85),rnd(16,138),5,0,Math.PI*2);ctx.fill();}}
  }}else if(SCENE==='bridge'){{
    for(let i=0;i<92;i++){{
      const left=i<46,cx=left?W/2-78:W/2+78;
      ctx.beginPath();ctx.arc(rnd(cx-52,cx+52),rnd(36,H-54),5,0,Math.PI*2);ctx.fill();
    }}
  }}else{{
    for(let i=0;i<190;i++){{
      const a=Math.random()*Math.PI,r=Math.random()*(76+i*0.2);
      const x=W/2+Math.cos(a)*r*1.2,y=H-38-Math.abs(Math.sin(a)*r)*0.7;
      if(x>12&&x<W-12&&y>0&&y<H-38){{ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();}}
    }}
  }}
  ctx.fillStyle='rgba(90,60,30,0.4)'; ctx.font='13px sans-serif';
  ctx.textAlign='center'; ctx.fillText('Press Run simulation to animate',W/2,H/2); ctx.textAlign='left';
}}

function runSim() {{
  if(raf)cancelAnimationFrame(raf);
  t=0; init();
  (function loop(){{
    t++; step(); drawBg();
    if(SCENE==='castle'&&t>80&&t<148){{
      ctx.fillStyle='rgba(200,80,40,0.18)';
      ctx.beginPath();ctx.arc(W/2+Math.sin(t*0.3)*3,H-98,28,0,Math.PI*2);ctx.fill();
    }}
    drawParticles();
    if(t<300)raf=requestAnimationFrame(loop);
  }})();
}}

function resetSim(){{
  if(raf){{cancelAnimationFrame(raf);raf=null;}}
  drawStatic();
}}

drawStatic();
</script>
</body>
</html>"""

components.html(SIM_HTML, height=410, scrolling=False)

# ── Yield surface ─────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("### Mohr-Coulomb yield surface")
st.caption("τ = c + σ·tan(φ) — the failure boundary between stable and flowing material. Steeper slope = higher friction angle.")

sigma = list(range(0, 151, 5))
chart_data = {}
for gid, g in GRAINS.items():
    phi_r = math.radians(g["friction_angle"])
    chart_data[g["name"]] = [round(g["cohesion"] + s * math.tan(phi_r), 2) for s in sigma]

df = pd.DataFrame(chart_data, index=sigma)
df.index.name = "Normal stress σ (kPa)"
st.line_chart(df, height=280)

# ── Grain comparison table ────────────────────────────────────────────────────
with st.expander("Full grain properties (from paper)"):
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

# ── Drucker-Prager ────────────────────────────────────────────────────────────
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
