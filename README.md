# Sand Explorer — Streamlit Edition

Interactive grain physics explorer based on:
> *Rigid Body Simulation of Cohesive Granular Materials* — ACM SIGGRAPH 2025

## Stack

Single file. Zero backend. Deploys to Streamlit Cloud for free.

| Layer | What it does |
|---|---|
| `app.py` | Everything — UI, grain data, physics canvas, yield surface charts |
| `requirements.txt` | `streamlit` + `pandas` only |
| `.streamlit/config.toml` | Sandy theme colors |

The particle simulation runs as an **HTML5 canvas component** embedded via
`streamlit.components.v1.components.html()` — so the full position-based
physics engine runs in the visitor's browser at 60fps, not on the server.

---

## Local development

```bash
pip install streamlit pandas
streamlit run app.py
# Opens at http://localhost:8501
```

---

## Deploy to Streamlit Cloud (free)

1. Push this folder to a GitHub repo:
   ```bash
   git init && git add . && git commit -m "initial"
   git remote add origin https://github.com/YOUR_USERNAME/sand-explorer.git
   git push -u origin main
   ```

2. Go to https://share.streamlit.io → **Create app**

3. Fill in:
   - **Repository**: `YOUR_USERNAME/sand-explorer`
   - **Branch**: `main`
   - **Main file path**: `app.py`

4. Click **Deploy** — live in ~2 minutes at:
   `https://YOUR_USERNAME-sand-explorer-app-XXXXX.streamlit.app`

Every `git push` to `main` auto-redeploys. That's it.

---

## File structure

```
sand-explorer/
├── app.py                  ← the entire app
├── requirements.txt        ← streamlit + pandas
├── .streamlit/
│   └── config.toml         ← sandy theme
└── .github/
    └── workflows/
        └── ci.yml          ← syntax check on push
```
