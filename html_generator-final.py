"""
html_generator.py
=================
Génère un dashboard HTML standalone — style Data Science Team.
Design : dark mode technique, typographie monospace + sans-serif, accent cyan/violet.

Pages : Vue d'ensemble · Par domaine · Collaborateurs · Roadmap Gantt · Évolutions · Chat LLM

Usage :
    python html_generator.py
    python html_generator.py --quinzaine T1_2026_R1
    python html_generator.py --llm
    python html_generator.py --config config.yaml --output frontend/dashboard.html
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from storage.storage import StorageManager
except ImportError:
    from storage import StorageManager  # type: ignore

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)


# ── Donnees ───────────────────────────────────────────────────────────────────

def _calculer_snapshot(sm, q, quinzaines):
    df   = sm.charger_quinzaines(quinzaines=[q])
    kpis = sm.kpis(quinzaine=q)
    idx  = quinzaines.index(q)
    q_prev = quinzaines[idx - 1] if idx > 0 else None
    delta = []
    if q_prev:
        df_d = sm.delta_quinzaines(q_prev, q)
        if not df_d.empty:
            delta = df_d.where(df_d.notna(), None).to_dict(orient="records")
    projets = df.where(df.notna(), None).to_dict(orient="records") if not df.empty else []
    par_domaine, par_resp = {}, {}
    for p in projets:
        d = p.get("domaine") or p.get("domaine_meta") or "Autre"
        par_domaine.setdefault(d, {"total":0,"on_track":0,"at_risk":0,"late":0,"done":0,"on_hold":0})
        par_domaine[d]["total"] += 1
        s = (p.get("statut") or "").upper()
        for k2 in ["on_track","at_risk","late","done","on_hold"]:
            if s == k2.upper(): par_domaine[d][k2] += 1
        r = p.get("responsable_principal") or "Non assigné"
        par_resp.setdefault(r, {"total":0,"en_cours":0,"domaines":[]})
        par_resp[r]["total"] += 1
        if s in ("ON_TRACK","AT_RISK"): par_resp[r]["en_cours"] += 1
        dom = d
        if dom and dom not in par_resp[r]["domaines"]:
            par_resp[r]["domaines"].append(dom)
    return {
        "projets": projets, "kpis": kpis, "par_domaine": par_domaine,
        "par_resp": par_resp,
        "domaines": sorted(set((p.get("domaine") or p.get("domaine_meta") or "") for p in projets if (p.get("domaine") or p.get("domaine_meta")))),
        "q_prev": q_prev, "delta": delta,
    }


def preparer_donnees(sm, quinzaine=None):
    quinzaines = sm.lister_quinzaines()
    if not quinzaines:
        log.error("Aucune donnee — lance excel_parser.py d'abord")
        return {}
    quinzaines_triees = sorted(quinzaines)
    q_active = quinzaine or quinzaines_triees[-1]
    if q_active not in quinzaines_triees:
        q_active = quinzaines_triees[-1]
    meta = sm.charger_meta()
    df_all = sm.charger_quinzaines()
    historiques = {}
    if not df_all.empty:
        col_id = "projet_id" if "projet_id" in df_all.columns else "ref_sujet"
        for pid in df_all[col_id].unique():
            h = sm.projet(pid)
            if not h.empty:
                historiques[str(pid)] = h.where(h.notna(), None).to_dict(orient="records")
    snapshots = {}
    for q in quinzaines_triees:
        log.info(f"Preparation snapshot : {q}")
        snapshots[q] = _calculer_snapshot(sm, q, quinzaines_triees)
    snap = snapshots[q_active]
    meta_list = meta.where(meta.notna(), None).to_dict(orient="records") if not meta.empty else []
    return {
        "genere_le":   datetime.now().strftime("%d/%m/%Y a %H:%M"),
        "quinzaines":  quinzaines_triees,
        "quinzaine":   q_active,
        "q_prev":      snap["q_prev"],
        "kpis":        snap["kpis"],
        "projets":     snap["projets"],
        "domaines":    snap["domaines"],
        "par_domaine": snap["par_domaine"],
        "par_resp":    snap["par_resp"],
        "delta":       snap["delta"],
        "meta":        meta_list,
        "historiques": historiques,
        "snapshots":   snapshots,
    }


# ── HTML ──────────────────────────────────────────────────────────────────────

CSS = """
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=DM+Sans:wght@300;400;500;600;700&display=swap');
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
:root{
  --bg:#0a0c10;--bg2:#0f1117;--bg3:#161b25;--bg4:#1c2333;
  --border:#1e2740;--border2:#263050;
  --text:#e2e8f0;--text2:#94a3b8;--text3:#475569;
  --cyan:#00d4ff;--cyan2:#0099cc;--cyan-dim:rgba(0,212,255,.08);
  --violet:#8b5cf6;--violet-dim:rgba(139,92,246,.1);
  --green:#10d994;--green-dim:rgba(16,217,148,.1);
  --amber:#f59e0b;--amber-dim:rgba(245,158,11,.1);
  --red:#f43f5e;--red-dim:rgba(244,63,94,.1);
  --font-body:'DM Sans',sans-serif;--font-mono:'JetBrains Mono',monospace;
  --radius:8px;--radius-lg:12px;
}
html,body{height:100%;font-size:13px;background:var(--bg);color:var(--text);}
body{font-family:var(--font-body);line-height:1.5;overflow:hidden;}
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:var(--bg2);}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:4px;}
.shell{display:flex;height:100vh;}
.sidebar{width:220px;min-width:220px;background:var(--bg2);border-right:1px solid var(--border);
         display:flex;flex-direction:column;overflow-y:auto;flex-shrink:0;}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.topbar{background:var(--bg2);border-bottom:1px solid var(--border);padding:10px 20px;
        display:flex;align-items:center;gap:12px;flex-shrink:0;}
.content{flex:1;overflow-y:auto;padding:20px;background:var(--bg);}
.logo{padding:18px 16px 14px;border-bottom:1px solid var(--border);}
.logo-title{font-family:var(--font-mono);font-size:11px;font-weight:600;color:var(--cyan);
            letter-spacing:.12em;text-transform:uppercase;}
.logo-sub{font-size:10px;color:var(--text3);margin-top:3px;font-family:var(--font-mono);}
.logo-date{font-size:9px;color:var(--text3);margin-top:6px;font-family:var(--font-mono);}
.q-selector-wrap{padding:12px 14px;border-bottom:1px solid var(--border);}
.q-selector-label{font-size:9px;font-weight:600;color:var(--text3);letter-spacing:.1em;
                  text-transform:uppercase;margin-bottom:5px;font-family:var(--font-mono);}
.q-selector{width:100%;background:var(--bg3);color:var(--text);border:1px solid var(--border2);
            border-radius:var(--radius);padding:6px 8px;font-size:11px;cursor:pointer;outline:none;
            font-family:var(--font-mono);}
.q-selector:focus{border-color:var(--cyan);}
.nav-section{padding:14px 16px 4px;font-size:9px;font-weight:600;text-transform:uppercase;
             letter-spacing:.1em;color:var(--text3);font-family:var(--font-mono);}
.nav-item{display:flex;align-items:center;gap:10px;padding:8px 14px;font-size:12px;
          cursor:pointer;transition:all .12s;color:var(--text2);border-left:2px solid transparent;user-select:none;}
.nav-item:hover{background:var(--bg3);color:var(--text);}
.nav-item.active{background:var(--cyan-dim);color:var(--cyan);border-left-color:var(--cyan);font-weight:500;}
.nav-icon{font-size:13px;width:18px;text-align:center;flex-shrink:0;}
.nav-badge{margin-left:auto;font-size:9px;font-family:var(--font-mono);background:var(--bg4);
           color:var(--text3);padding:1px 5px;border-radius:10px;}
.nav-item.active .nav-badge{background:var(--cyan-dim);color:var(--cyan);}
.sidebar-footer{margin-top:auto;padding:12px 14px;border-top:1px solid var(--border);
                font-size:9px;color:var(--text3);font-family:var(--font-mono);}
.page-title{font-size:13px;font-weight:600;color:var(--text);font-family:var(--font-mono);}
.page-title::before{content:'> ';color:var(--cyan);}
.snap-info{font-size:10px;color:var(--text3);font-family:var(--font-mono);background:var(--bg3);
           padding:3px 8px;border-radius:20px;border:1px solid var(--border);}
.spacer{flex:1;}
.gen-at{font-size:10px;color:var(--text3);font-family:var(--font-mono);}
.btn-pdf{font-size:10px;padding:5px 12px;background:transparent;color:var(--cyan);
         border:1px solid var(--cyan);border-radius:var(--radius);cursor:pointer;
         font-family:var(--font-mono);letter-spacing:.05em;transition:all .15s;}
.btn-pdf:hover{background:var(--cyan);color:var(--bg);}
.page{display:none;}.page.active{display:block;}
.metrics-row{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:16px;}
.metric-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
             padding:14px 16px;position:relative;overflow:hidden;transition:border-color .15s;}
.metric-card:hover{border-color:var(--border2);}
.metric-card::before{content:'';position:absolute;top:0;left:0;right:0;height:2px;}
.metric-card.c-cyan::before{background:linear-gradient(90deg,var(--cyan),transparent);}
.metric-card.c-red::before{background:linear-gradient(90deg,var(--red),transparent);}
.metric-card.c-green::before{background:linear-gradient(90deg,var(--green),transparent);}
.metric-card.c-violet::before{background:linear-gradient(90deg,var(--violet),transparent);}
.metric-card.c-amber::before{background:linear-gradient(90deg,var(--amber),transparent);}
.metric-label{font-size:9px;color:var(--text3);text-transform:uppercase;letter-spacing:.1em;
              font-family:var(--font-mono);margin-bottom:6px;}
.metric-value{font-size:26px;font-weight:700;font-family:var(--font-mono);line-height:1;}
.metric-sub{font-size:9px;color:var(--text3);margin-top:4px;font-family:var(--font-mono);}
.metric-card.c-cyan .metric-value{color:var(--cyan);}
.metric-card.c-red .metric-value{color:var(--red);}
.metric-card.c-green .metric-value{color:var(--green);}
.metric-card.c-violet .metric-value{color:var(--violet);}
.metric-card.c-amber .metric-value{color:var(--amber);}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:12px;}
.card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
      padding:16px;margin-bottom:12px;}
.card-title{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.12em;
            color:var(--text3);margin-bottom:12px;font-family:var(--font-mono);
            display:flex;align-items:center;gap:6px;}
.card-title::before{content:'//';color:var(--cyan);font-size:10px;}
.bar-rows{display:flex;flex-direction:column;gap:8px;}
.bar-row{display:flex;align-items:center;gap:8px;}
.bar-label{font-size:11px;min-width:110px;max-width:110px;color:var(--text2);
           overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.bar-track{flex:1;height:5px;background:var(--bg4);border-radius:4px;overflow:hidden;}
.bar-fill{height:100%;border-radius:4px;}
.bar-count{font-size:10px;font-weight:600;min-width:22px;text-align:right;
           color:var(--text2);font-family:var(--font-mono);}
.proj-list{display:flex;flex-direction:column;gap:4px;}
.proj-item{display:flex;align-items:center;gap:7px;padding:8px 10px;border-radius:var(--radius);
           border:1px solid transparent;font-size:11px;cursor:pointer;
           transition:all .12s;background:var(--bg3);}
.proj-item:hover{border-color:var(--border2);background:var(--bg4);}
.proj-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.proj-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text);}
.proj-resp{font-size:9px;color:var(--text3);min-width:70px;text-align:right;font-family:var(--font-mono);}
.proj-pct{font-size:10px;font-weight:600;color:var(--text2);min-width:32px;
          text-align:right;font-family:var(--font-mono);}
.badge{font-size:9px;padding:2px 7px;border-radius:20px;font-weight:600;white-space:nowrap;
       flex-shrink:0;font-family:var(--font-mono);letter-spacing:.04em;}
.bON_TRACK{background:var(--green-dim);color:var(--green);border:1px solid rgba(16,217,148,.2);}
.bAT_RISK{background:var(--amber-dim);color:var(--amber);border:1px solid rgba(245,158,11,.2);}
.bLATE{background:var(--red-dim);color:var(--red);border:1px solid rgba(244,63,94,.2);}
.bDONE{background:var(--violet-dim);color:var(--violet);border:1px solid rgba(139,92,246,.2);}
.bON_HOLD{background:var(--bg4);color:var(--text3);border:1px solid var(--border);}
.bLIVRE{background:var(--green-dim);color:var(--green);border:1px solid rgba(16,217,148,.2);}
.bEN_COURS{background:var(--cyan-dim);color:var(--cyan);border:1px solid rgba(0,212,255,.2);}
.bNON_LIVRE{background:var(--red-dim);color:var(--red);border:1px solid rgba(244,63,94,.2);}
.bREPORTE{background:var(--amber-dim);color:var(--amber);border:1px solid rgba(245,158,11,.2);}
.collab-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;}
.collab-card{background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
             padding:14px;cursor:pointer;transition:all .15s;}
.collab-card:hover{border-color:var(--border2);background:var(--bg3);}
.collab-card.selected{border-color:var(--cyan);box-shadow:0 0 0 1px var(--cyan-dim);}
.avatar{width:36px;height:36px;border-radius:var(--radius);display:flex;align-items:center;
        justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;font-family:var(--font-mono);}
.collab-header{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.collab-name{font-size:12px;font-weight:600;color:var(--text);}
.collab-sub{font-size:9px;color:var(--text3);font-family:var(--font-mono);}
.charge-bar{height:3px;background:var(--bg4);border-radius:3px;overflow:hidden;margin-top:8px;}
.charge-fill{height:100%;border-radius:3px;background:var(--cyan);}
.gantt-controls{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center;}
.gantt-controls select,.gantt-controls label{font-size:11px;color:var(--text2);font-family:var(--font-mono);}
.gantt-controls select{padding:4px 8px;border:1px solid var(--border2);border-radius:var(--radius);
                       background:var(--bg3);color:var(--text);cursor:pointer;}
.gantt-wrap{overflow-x:auto;}
.gantt-table{border-collapse:collapse;min-width:700px;width:100%;font-size:10px;}
.gantt-table th,.gantt-table td{border:0;padding:0;}
.g-label{padding:5px 10px;font-size:10px;color:var(--text2);white-space:nowrap;
         max-width:160px;min-width:160px;overflow:hidden;text-overflow:ellipsis;
         cursor:pointer;font-family:var(--font-mono);}
.g-label:hover{color:var(--cyan);}
.g-header{text-align:center;font-size:9px;color:var(--text3);padding:4px 2px;
          border-bottom:1px solid var(--border);min-width:44px;font-family:var(--font-mono);}
.g-cell{padding:3px 2px;position:relative;min-width:44px;height:28px;vertical-align:middle;}
.g-bar{position:absolute;top:6px;bottom:6px;border-radius:3px;}
.g-now{position:absolute;top:0;width:1.5px;bottom:0;z-index:5;background:var(--red);opacity:.8;}
.g-today-head{border-bottom:2px solid var(--red)!important;color:var(--red)!important;font-weight:700;}
.gantt-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;}
.gantt-legend span{font-size:9px;color:var(--text3);display:flex;align-items:center;
                   gap:4px;font-family:var(--font-mono);}
.tl-item{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);}
.tl-item:last-child{border-bottom:none;}
.tl-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:4px;}
.tl-body{flex:1;}
.tl-title{font-size:12px;font-weight:600;margin-bottom:3px;cursor:pointer;color:var(--text);}
.tl-title:hover{color:var(--cyan);}
.tl-meta{display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-top:3px;}
.chat-wrap{display:flex;flex-direction:column;height:calc(100vh - 110px);max-width:860px;margin:0 auto;}
.chat-header{font-family:var(--font-mono);font-size:10px;color:var(--text3);
             margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid var(--border);}
.chat-qs{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:10px;}
.chat-q{font-size:10px;padding:4px 10px;background:var(--bg3);border:1px solid var(--border2);
        border-radius:20px;cursor:pointer;color:var(--text2);transition:all .12s;font-family:var(--font-mono);}
.chat-q:hover{border-color:var(--cyan);color:var(--cyan);}
.chat-msgs{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px;padding:4px 0;}
.msg{display:flex;gap:10px;align-items:flex-start;}
.msg.user{flex-direction:row-reverse;}
.msg-av{width:28px;height:28px;border-radius:var(--radius);background:var(--bg3);
        border:1px solid var(--border2);display:flex;align-items:center;justify-content:center;
        font-size:9px;font-weight:700;color:var(--text3);flex-shrink:0;font-family:var(--font-mono);}
.msg.user .msg-av{background:var(--cyan-dim);border-color:var(--cyan);color:var(--cyan);}
.bubble{max-width:76%;background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius-lg);
        padding:10px 14px;font-size:12px;line-height:1.7;color:var(--text);white-space:pre-wrap;}
.msg.user .bubble{background:var(--bg3);border-color:var(--border2);}
.chat-bar{padding:10px 0;border-top:1px solid var(--border);display:flex;gap:8px;flex-shrink:0;}
.chat-input{flex:1;background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);
            padding:9px 13px;font-family:var(--font-mono);font-size:11px;outline:none;
            resize:none;color:var(--text);transition:border-color .12s;}
.chat-input:focus{border-color:var(--cyan);}
.chat-input::placeholder{color:var(--text3);}
.chat-send{background:var(--cyan);border:none;border-radius:var(--radius);padding:9px 18px;
           color:var(--bg);font-family:var(--font-mono);font-size:11px;cursor:pointer;
           font-weight:600;transition:all .12s;}
.chat-send:hover{background:var(--cyan2);}
.chat-send:disabled{opacity:.3;cursor:default;}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.6);
               backdrop-filter:blur(4px);z-index:200;align-items:center;justify-content:center;}
.modal-overlay.open{display:flex;}
.modal{background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius-lg);
       width:600px;max-width:95vw;max-height:88vh;overflow-y:auto;padding:24px;
       box-shadow:0 24px 64px rgba(0,0,0,.5);}
.modal-close{float:right;cursor:pointer;font-size:16px;color:var(--text3);
             border:none;background:none;line-height:1;padding:0;font-family:var(--font-mono);}
.modal-close:hover{color:var(--text);}
.modal-title{font-size:15px;font-weight:600;margin-bottom:4px;color:var(--text);}
.modal-id{font-size:9px;color:var(--cyan);font-family:var(--font-mono);margin-bottom:10px;}
.modal-row{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px;}
.modal-sec{margin-top:14px;}
.modal-stitle{font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;
              color:var(--text3);margin-bottom:6px;font-family:var(--font-mono);}
.modal-stitle::before{content:'// ';color:var(--cyan);}
.modal-text{font-size:12px;color:var(--text2);line-height:1.7;}
.prog-track{height:6px;background:var(--bg4);border-radius:4px;overflow:hidden;margin-top:6px;}
.prog-fill{height:100%;border-radius:4px;}
.meta-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-top:6px;}
.meta-item{background:var(--bg3);border-radius:var(--radius);padding:7px 10px;}
.meta-key{font-size:8px;color:var(--text3);font-family:var(--font-mono);text-transform:uppercase;
          letter-spacing:.08em;margin-bottom:2px;}
.meta-val{font-size:11px;color:var(--text);font-family:var(--font-mono);}
.hist-row{display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--border);font-size:10px;}
.hist-q{min-width:100px;color:var(--text3);font-family:var(--font-mono);}
.filter-strip{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px;}
.fchip{font-size:10px;padding:3px 10px;border-radius:20px;border:1px solid var(--border2);
       color:var(--text2);cursor:pointer;background:var(--bg2);transition:all .12s;font-family:var(--font-mono);}
.fchip:hover{border-color:var(--cyan);color:var(--cyan);}
.fchip.active{background:var(--cyan-dim);color:var(--cyan);border-color:var(--cyan);}
@media(max-width:1100px){{.metrics-row{{grid-template-columns:repeat(3,1fr);}}}}
@media(max-width:900px){{.grid2{{grid-template-columns:1fr;}}.collab-grid{{grid-template-columns:1fr 1fr;}}}}
@media print{{
  .sidebar,.topbar,.chat-wrap,.modal-overlay{{display:none!important;}}
  .content{{overflow:visible;padding:10px;}}
  .page{{display:block!important;}}
  body{{background:#fff;color:#000;}}
  .card,.metric-card{{border:1px solid #ccc;background:#fff;}}
}}
"""


def generer_html(donnees, llm_cache=None):
    data_js = json.dumps(donnees, ensure_ascii=False)
    llm_js  = json.dumps(llm_cache or {}, ensure_ascii=False)
    q_label = donnees.get("quinzaine", "")

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>DATA_MONITOR :: {q_label}</title>
<style>{CSS}</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="logo">
      <div class="logo-title">DATA_MONITOR</div>
      <div class="logo-sub">// pilotage projets</div>
      <div class="logo-date" id="logo-date"></div>
    </div>
    <div class="q-selector-wrap">
      <div class="q-selector-label">Quinzaine</div>
      <select class="q-selector" id="q-selector" onchange="switchQuinzaine(this.value)"></select>
    </div>
    <div class="nav-section">Navigation</div>
    <div class="nav-item active" data-page="overview"><span class="nav-icon">◈</span>Vue d'ensemble<span class="nav-badge" id="nb-overview">—</span></div>
    <div class="nav-item" data-page="domaines"><span class="nav-icon">⬡</span>Par domaine</div>
    <div class="nav-item" data-page="collabs"><span class="nav-icon">◎</span>Collaborateurs</div>
    <div class="nav-item" data-page="gantt"><span class="nav-icon">▤</span>Roadmap Gantt</div>
    <div class="nav-item" data-page="evolutions"><span class="nav-icon">△</span>Evolutions<span class="nav-badge" id="nb-evol">—</span></div>
    <div class="nav-section">Outils</div>
    <div class="nav-item" data-page="chat"><span class="nav-icon">⌘</span>Chat LLM</div>
    <div class="sidebar-footer" id="sidebar-footer"></div>
  </aside>
  <div class="main">
    <div class="topbar">
      <span class="page-title" id="page-title">overview</span>
      <span class="snap-info" id="snap-info"></span>
      <div class="spacer"></div>
      <span class="gen-at" id="gen-at"></span>
      <button class="btn-pdf" onclick="window.print()">EXPORT PDF</button>
    </div>
    <div class="content">
      <div class="page active" id="page-overview"></div>
      <div class="page" id="page-domaines"></div>
      <div class="page" id="page-collabs"></div>
      <div class="page" id="page-gantt"></div>
      <div class="page" id="page-evolutions"></div>
      <div class="page" id="page-chat">
        <div class="chat-wrap">
          <div class="chat-header">&gt; assistant_llm :: quinzaine=<span id="chat-q-label"></span></div>
          <div class="chat-qs" id="chat-qs"></div>
          <div class="chat-msgs" id="chat-msgs">
            <div class="msg">
              <div class="msg-av">AI</div>
              <div class="bubble">Connecte au serveur puis pose ta question sur les projets de la quinzaine <strong id="chat-q-label2"></strong>.

Utilise les suggestions ou tape ta propre question.</div>
            </div>
          </div>
          <div class="chat-bar">
            <textarea class="chat-input" id="chat-input" rows="2" placeholder="$ query --question '...'"
              onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();sendChat();}}"></textarea>
            <button class="chat-send" onclick="sendChat()">ENVOYER</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>
<div class="modal-overlay" id="modal-overlay"><div class="modal" id="modal-body"></div></div>

<script>
const DATA={data_js};
const LLM={llm_js};
const PALETTE=["#00d4ff","#10d994","#8b5cf6","#f59e0b","#f43f5e","#a855f7","#06b6d4","#84cc16","#fb923c","#e879f9"];
const SC={{ON_TRACK:"#10d994",AT_RISK:"#f59e0b",LATE:"#f43f5e",DONE:"#8b5cf6",ON_HOLD:"#475569"}};
const PAGES={{overview:"overview",domaines:"par_domaine",collabs:"collaborateurs",gantt:"roadmap_gantt",evolutions:"evolutions",chat:"chat_llm"}};
let selCollab=null;

function esc(s){{return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}}
function badge(st){{return`<span class="badge b${{st}}">${{st||"—"}}</span>`;}}
function domColor(d){{const ds=[...new Set(DATA.projets.map(p=>p.domaine||p.domaine_meta).filter(Boolean))].sort();return PALETTE[ds.indexOf(d)%PALETTE.length]||PALETTE[0];}}
function initials(n){{return(n||"??").split(/\s+/).map(w=>w[0]).join("").toUpperCase().slice(0,2);}}
function avStyle(n){{const c=[["rgba(0,212,255,.12)","#00d4ff"],["rgba(16,217,148,.12)","#10d994"],["rgba(139,92,246,.12)","#8b5cf6"],["rgba(245,158,11,.12)","#f59e0b"],["rgba(244,63,94,.12)","#f43f5e"],["rgba(168,85,247,.12)","#a855f7"]];const[bg,fg]=c[(n||"X").charCodeAt(0)%c.length];return`background:${{bg}};color:${{fg}}`;}}
function pp(p){{return p.avancement_pct||0;}}
function nom(p){{return p.projet_nom||p.sujet||"";}}
function pid(p){{return p.projet_id||p.ref_sujet||"";}}
function projItem(p){{const col=SC[p.statut]||"#475569";return`<div class="proj-item" onclick="openModal('${{esc(pid(p))}}')"><span class="proj-dot" style="background:${{col}}"></span><span class="proj-name" title="${{esc(nom(p))}}">${{esc(nom(p))}}</span>${{badge(p.statut)}}<span class="proj-pct">${{pp(p)}}%</span><span class="proj-resp">${{esc(p.responsable_principal||"")}}</span></div>`;}}

function switchQuinzaine(q){{
  if(!DATA.snapshots||!DATA.snapshots[q])return;
  const snap=DATA.snapshots[q];
  DATA.quinzaine=q;DATA.q_prev=snap.q_prev;DATA.kpis=snap.kpis;DATA.projets=snap.projets;
  DATA.domaines=snap.domaines;DATA.par_domaine=snap.par_domaine;DATA.par_resp=snap.par_resp;DATA.delta=snap.delta;
  document.getElementById("snap-info").textContent=q+(snap.q_prev?" <- "+snap.q_prev:"");
  ["chat-q-label","chat-q-label2"].forEach(id=>{{const el=document.getElementById(id);if(el)el.textContent=q;}});
  document.getElementById("nb-overview").textContent=DATA.projets.length;
  document.getElementById("nb-evol").textContent=DATA.delta.length;
  renderOverview();renderDomaines();renderCollabs();renderEvolutions();
  if(document.getElementById("page-gantt").dataset.init)buildGantt();
}}

(function init(){{
  document.getElementById("logo-date").textContent="gen "+DATA.genere_le;
  document.getElementById("gen-at").textContent=DATA.genere_le;
  document.getElementById("snap-info").textContent=DATA.quinzaine+(DATA.q_prev?" <- "+DATA.q_prev:"");
  ["chat-q-label","chat-q-label2"].forEach(id=>{{const el=document.getElementById(id);if(el)el.textContent=DATA.quinzaine;}});
  document.getElementById("nb-overview").textContent=DATA.projets.length;
  document.getElementById("nb-evol").textContent=(DATA.delta||[]).length;
  document.getElementById("sidebar-footer").textContent=DATA.quinzaines.length+" quinzaine(s) chargee(s)";
  const sel=document.getElementById("q-selector");
  [...DATA.quinzaines].reverse().forEach(q=>{{const o=document.createElement("option");o.value=q;o.textContent=q;if(q===DATA.quinzaine)o.selected=true;sel.appendChild(o);}});
  const qsChat=[["resume l'avancement global de la quinzaine","resume global"],["quels projets sont en retard ?","en retard"],["quels projets sont a risque ?","a risque"],["quelles decisions ont ete prises ?","decisions"],["y a-t-il des blocages actifs ?","blocages"],["quelles actions sont a mener en priorite ?","actions prio"],["quels projets arrivent bientot a echeance ?","echeances"],["quel est le projet le plus en difficulte ?","en difficulte"]];
  document.getElementById("chat-qs").innerHTML=qsChat.map(([q,l])=>`<button class="chat-q" onclick="askChat('${{q}}')">${{l}}</button>`).join("");
  document.querySelectorAll(".nav-item[data-page]").forEach(el=>{{
    el.addEventListener("click",()=>{{
      document.querySelectorAll(".nav-item").forEach(n=>n.classList.remove("active"));
      document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
      el.classList.add("active");const pg=el.dataset.page;
      document.getElementById("page-"+pg).classList.add("active");
      document.getElementById("page-title").textContent=PAGES[pg];
      if(pg==="gantt")renderGantt();
    }});
  }});
  document.getElementById("modal-overlay").addEventListener("click",e=>{{if(e.target===document.getElementById("modal-overlay"))closeModal();}});
  renderOverview();renderDomaines();renderCollabs();renderEvolutions();
}})();

function renderOverview(){{
  const k=DATA.kpis;const P=DATA.projets;
  const maxD=Math.max(...Object.values(DATA.par_domaine).map(d=>d.total),1);
  const maxR=Math.max(...Object.values(DATA.par_resp).map(r=>r.total),1);
  const top=[...P].sort((a,b)=>({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[a.statut]||9)-({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[b.statut]||9)).slice(0,10);
  const alertes=P.filter(p=>p.statut==="LATE"||p.statut==="AT_RISK"||p.points_blocage);
  document.getElementById("page-overview").innerHTML=`
    <div class="metrics-row">
      <div class="metric-card c-cyan"><div class="metric-label">projets actifs</div><div class="metric-value">${{k.nb_projets_actifs||0}}</div><div class="metric-sub">cette quinzaine</div></div>
      <div class="metric-card c-red"><div class="metric-label">a risque / retard</div><div class="metric-value">${{(k.nb_at_risk||0)+(k.nb_en_retard||0)}}</div><div class="metric-sub">${{k.nb_en_retard||0}} retard · ${{k.nb_at_risk||0}} risque</div></div>
      <div class="metric-card c-green"><div class="metric-label">termines</div><div class="metric-value">${{k.nb_done||0}}</div><div class="metric-sub">${{k.nb_on_hold||0}} en pause</div></div>
      <div class="metric-card c-violet"><div class="metric-label">avancement moyen</div><div class="metric-value">${{k.avancement_moyen||0}}%</div><div class="metric-sub">tous projets actifs</div></div>
      <div class="metric-card c-amber"><div class="metric-label">decisions / blocages</div><div class="metric-value">${{k.nb_decisions||0}}</div><div class="metric-sub">${{k.nb_blocages||0}} blocage(s)</div></div>
    </div>
    ${{alertes.length?`<div class="card"><div class="card-title">alertes actives (${{alertes.length}})</div><div class="proj-list">${{alertes.map(projItem).join("")}}</div></div>`:""}}
    <div class="grid2">
      <div class="card"><div class="card-title">par domaine</div><div class="bar-rows">${{Object.entries(DATA.par_domaine).sort((a,b)=>b[1].total-a[1].total).map(([d,s])=>`<div class="bar-row"><span class="bar-label" title="${{esc(d)}}">${{esc(d)}}</span><div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxD*100)}}%;background:${{domColor(d)}}"></div></div><span class="bar-count">${{s.total}}</span></div>`).join("")}}</div></div>
      <div class="card"><div class="card-title">par responsable</div><div class="bar-rows">${{Object.entries(DATA.par_resp).sort((a,b)=>b[1].total-a[1].total).map(([r,s])=>`<div class="bar-row"><span class="bar-label" title="${{esc(r)}}">${{esc(r)}}</span><div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxR*100)}}%;background:#00d4ff"></div></div><span class="bar-count">${{s.total}}</span></div>`).join("")}}</div></div>
    </div>
    <div class="card"><div class="card-title">projets — vue prioritaire (${{top.length}})</div><div class="proj-list">${{top.map(projItem).join("")}}</div></div>`;
}}

function renderDomaines(){{
  let html='<div class="filter-strip" id="df"><span class="fchip active" data-val="">Tous</span>'+DATA.domaines.map(d=>'<span class="fchip" data-val="'+esc(d)+'">'+esc(d)+'</span>').join('')+'</div>';
  html+=DATA.domaines.map(dom=>{{
    const pr=DATA.projets.filter(p=>(p.domaine||p.domaine_meta)===dom);const s=DATA.par_domaine[dom]||{{}};
    let badges='';
    if(s.on_track)badges+=`<span class="badge bON_TRACK">${{s.on_track}} on_track</span>`;
    if(s.at_risk)badges+=`<span class="badge bAT_RISK">${{s.at_risk}} at_risk</span>`;
    if(s.late)badges+=`<span class="badge bLATE">${{s.late}} late</span>`;
    if(s.done)badges+=`<span class="badge bDONE">${{s.done}} done</span>`;
    return`<div class="card dom-sec" data-dom="${{esc(dom)}}"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:6px"><div style="display:flex;align-items:center;gap:8px"><span style="width:8px;height:8px;border-radius:50%;background:${{domColor(dom)}};flex-shrink:0"></span><span style="font-size:12px;font-weight:600;color:var(--text);font-family:var(--font-mono)">${{esc(dom)}}</span></div><div style="display:flex;gap:4px;flex-wrap:wrap">${{badges}}</div></div><div class="proj-list">${{pr.map(projItem).join("")}}</div></div>`;
  }}).join("");
  document.getElementById("page-domaines").innerHTML=html;
  document.querySelectorAll("#df .fchip").forEach(c=>{{c.addEventListener("click",()=>{{document.querySelectorAll("#df .fchip").forEach(x=>x.classList.remove("active"));c.classList.add("active");const v=c.dataset.val;document.querySelectorAll(".dom-sec").forEach(s=>{{s.style.display=(!v||s.dataset.dom===v)?"":"none";}});}});}});
}}

function renderCollabs(sel){{
  sel=sel||selCollab||Object.keys(DATA.par_resp)[0]||"";selCollab=sel;
  const resps=Object.entries(DATA.par_resp).sort((a,b)=>b[1].total-a[1].total);
  const maxE=Math.max(...resps.map(([,r])=>r.en_cours),1);
  const detail=DATA.projets.filter(p=>p.responsable_principal===sel).sort((a,b)=>({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[a.statut]||9)-({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[b.statut]||9));
  document.getElementById("page-collabs").innerHTML=`
    <div class="collab-grid">${{resps.map(([name,r])=>`<div class="collab-card ${{name===sel?"selected":""}}" onclick="renderCollabs('${{esc(name)}}')"><div class="collab-header"><div class="avatar" style="${{avStyle(name)}}">${{initials(name)}}</div><div><div class="collab-name">${{esc(name)}}</div><div class="collab-sub">${{r.total}} projet${{r.total>1?"s":""}} · ${{r.en_cours}} actif${{r.en_cours>1?"s":""}}</div></div></div><div style="display:flex;gap:4px;flex-wrap:wrap">${{r.domaines.slice(0,3).map(d=>`<span style="font-size:9px;padding:2px 6px;border-radius:10px;background:var(--bg4);color:var(--text3);font-family:var(--font-mono)">${{esc(d)}}</span>`).join("")}}</div><div class="charge-bar"><div class="charge-fill" style="width:${{Math.round(r.en_cours/maxE*100)}}%"></div></div></div>`).join("")}}</div>
    <div class="card"><div class="card-title">projets :: ${{esc(sel)}} (${{detail.length}})</div><div class="proj-list">${{detail.map(projItem).join("")||'<div style="color:var(--text3);font-size:11px;font-family:var(--font-mono);padding:8px">// aucun projet</div>'}}</div></div>`;
}}

function renderGantt(){{
  const el=document.getElementById("page-gantt");
  if(el.dataset.init)return;el.dataset.init="1";
  el.innerHTML=`<div class="gantt-controls"><label>grouper :</label><select id="gg" onchange="buildGantt()"><option value="domaine">Domaine</option><option value="responsable_principal">Responsable</option><option value="statut">Statut</option></select><label style="margin-left:8px">statut :</label><select id="gf" onchange="buildGantt()"><option value="">Tous</option><option value="ON_TRACK">ON_TRACK</option><option value="AT_RISK">AT_RISK</option><option value="LATE">LATE</option><option value="DONE">DONE</option></select><label style="margin-left:8px">mode :</label><select id="gmode" onchange="buildGantt()"><option value="avancement">Avancement</option><option value="dates">Dates META</option></select></div><div class="card"><div id="gi"></div><div class="gantt-legend" id="gl"></div></div>`;
  buildGantt();
}}

function buildGantt(){{
  const grp=document.getElementById("gg")?.value||"domaine";
  const fst=document.getElementById("gf")?.value||"";
  const mode=document.getElementById("gmode")?.value||"avancement";
  let P=DATA.projets.filter(p=>p.avancement_pct!=null);
  if(fst)P=P.filter(p=>p.statut===fst);
  if(!P.length){{document.getElementById("gi").innerHTML='<div style="font-size:11px;color:var(--text3);padding:12px;font-family:var(--font-mono)">// aucun projet</div>';return;}}
  const now=new Date();const months=[];
  for(let i=-1;i<=5;i++)months.push(new Date(now.getFullYear(),now.getMonth()+i,1));
  const todayM=now.toISOString().slice(0,7);
  const MFR=["Jan","Fev","Mar","Avr","Mai","Jun","Jul","Aou","Sep","Oct","Nov","Dec"];
  const groups={{}};P.forEach(p=>{{const k=(p[grp]||p[grp+"_meta"])||"Autre";if(!groups[k])groups[k]=[];groups[k].push(p);}});
  const metaById={{}};(DATA.meta||[]).forEach(m=>{{metaById[m.projet_id||m.ref_sujet]=m;}});
  let html=`<div class="gantt-wrap"><table class="gantt-table"><thead><tr><th class="g-label" style="font-family:var(--font-mono);color:var(--text3);font-size:9px">PROJET</th>${{months.map(m=>{{const k=m.toISOString().slice(0,7);return`<th class="g-header${{k===todayM?" g-today-head":""}}">${{MFR[m.getMonth()]}}<br>${{String(m.getFullYear()).slice(2)}}</th>`;}}).join("")}}</tr></thead><tbody>`;
  Object.entries(groups).sort().forEach(([g,items],gi)=>{{
    const gc=PALETTE[gi%PALETTE.length];
    html+=`<tr><td colspan="${{months.length+1}}" style="padding:7px 10px 2px;font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:var(--text3);background:var(--bg3);border-top:1px solid var(--border);font-family:var(--font-mono)">${{esc(g)}}</td></tr>`;
    items.forEach(p=>{{
      const m=metaById[pid(p)]||{{}};const col=SC[p.statut]||gc;const pv=pp(p);
      html+=`<tr><td class="g-label" onclick="openModal('${{esc(pid(p))}}')" title="${{esc(nom(p))}}">${{esc(nom(p))}}</td>`;
      if(mode==="dates"&&(m.date_debut||m.date_fin_prevue)){{
        const parseDate=s=>s?new Date(s.split("/").reverse().join("-")):null;
        const deb=parseDate(m.date_debut);const fin=parseDate(m.date_fin_prevue);
        months.forEach(month=>{{
          const isT=month.toISOString().slice(0,7)===todayM;
          const mEnd=new Date(month.getFullYear(),month.getMonth()+1,0);
          const inRange=(deb&&fin)?(month<=fin&&mEnd>=deb):(deb?(month<=now&&mEnd>=deb):false);
          const nl=isT?`<div class="g-now" style="left:${{Math.round((now.getDate()-1)/mEnd.getDate()*100)}}%"></div>`:"";
          html+=`<td class="g-cell">${{inRange?`<div style="position:absolute;top:8px;bottom:8px;left:2px;right:2px;border-radius:2px;background:${{col}};opacity:.65;border:1px solid rgba(255,255,255,.1)"></div>`:""}}${{nl}}</td>`;
        }});
      }}else{{
        const ops=[0.2,0.45,0.7,0.45,0.25,0.12,0.06];
        months.forEach((month,mi)=>{{
          const isT=month.toISOString().slice(0,7)===todayM;
          const op=ops[mi]*(pv/100);
          const mEnd=new Date(month.getFullYear(),month.getMonth()+1,0);
          const nl=isT?`<div class="g-now" style="left:${{Math.round((now.getDate()-1)/mEnd.getDate()*100)}}%"></div>`:"";
          html+=`<td class="g-cell">${{op>0.04?`<div class="g-bar" style="left:2px;right:2px;background:${{col}};opacity:${{op.toFixed(2)}}"></div>`:""}}${{nl}}</td>`;
        }});
      }}
      html+=`</tr>`;
    }});
  }});
  html+=`</tbody></table></div>`;
  document.getElementById("gi").innerHTML=html;
  document.getElementById("gl").innerHTML=`<span><i style="width:12px;height:1.5px;background:var(--red);display:inline-block"></i> aujourd'hui</span>`+Object.keys(groups).slice(0,8).map((g,i)=>`<span><i style="width:12px;height:5px;background:${{PALETTE[i%PALETTE.length]}};border-radius:2px;display:inline-block"></i>${{esc(g)}}</span>`).join("");
}}

function renderEvolutions(){{
  const delta=DATA.delta||[];
  const sub=DATA.q_prev?`delta :: ${{DATA.q_prev}} -> ${{DATA.quinzaine}}`:`snapshot initial :: ${{DATA.quinzaine}}`;
  let html=`<div style="font-size:10px;color:var(--text3);margin-bottom:14px;font-family:var(--font-mono)"># ${{sub}}</div>`;
  html+=`<div class="card"><div class="card-title">changements detectes (${{delta.length}})</div>`;
  if(!delta.length)html+=`<div style="font-size:11px;color:var(--text3);padding:8px;font-family:var(--font-mono)">// ${{DATA.q_prev?"aucun changement":"premier snapshot"}}</div>`;
  else html+=`<div>${{delta.map(d=>{{const dv=d.delta_avancement||0;const sign=dv>0?"+":"";const dc=dv>0?"var(--green)":dv<0?"var(--red)":"var(--text3)";return`<div class="tl-item"><div class="tl-dot" style="background:${{dc}}"></div><div class="tl-body"><div class="tl-title" onclick="openModal('${{esc(d.projet_id||d.ref_sujet)}}')">${{esc(d.projet_nom||d.sujet||d.projet_id)}}</div><div class="tl-meta">${{d.statut_avant&&d.statut_apres&&d.statut_avant!==d.statut_apres?`<span style="font-size:9px;color:var(--text3);font-family:var(--font-mono)">${{d.statut_avant}} -> ${{d.statut_apres}}</span>":""}}${{dv!==0?`<span style="font-size:9px;font-family:var(--font-mono);color:${{dc}}">${{sign}}${{Math.round(dv)}}%</span>`:""}}${{badge(d.statut_apres||"ON_HOLD")}}</div></div></div>`;}}}).join("")}}</div>`;
  html+=`</div>`;
  const alertes=DATA.projets.filter(p=>p.points_blocage||p.statut==="LATE");
  if(alertes.length)html+=`<div class="card"><div class="card-title">points d'attention (${{alertes.length}})</div><div class="proj-list">${{alertes.map(projItem).join("")}}</div></div>`;
  document.getElementById("page-evolutions").innerHTML=html;
}}

function openModal(id){{
  const p=DATA.projets.find(x=>pid(x)===id);if(!p)return;
  const hist=(DATA.historiques||{{}})[id]||[];
  const pv=pp(p);const col=SC[p.statut]||"#475569";
  const metaById={{}};(DATA.meta||[]).forEach(m=>{{metaById[m.projet_id||m.ref_sujet]=m;}});
  const m=metaById[id]||{{}};
  const metaItems=[["ref/id",id],["domaine",p.domaine||m.domaine],["entite",p.entite_concerne||m.entite_concerne],["priorite",p.priorite||m.priorite],["budget j/sem",p.budget_jours||m.budget_jours],["date debut",p.date_debut||m.date_debut],["date fin prev.",p.date_fin_prevue||m.date_fin_prevue],["effectifs",p.effectifs||m.effectifs],["type",m.type],["description",m.description]].filter(([,v])=>v&&v!=="undefined");
  document.getElementById("modal-body").innerHTML=`
    <button class="modal-close" onclick="closeModal()">x</button>
    <div class="modal-title">${{esc(nom(p))}}</div>
    <div class="modal-id">${{esc(id)}}</div>
    <div class="modal-row">${{badge(p.statut)}}${{(p.domaine||m.domaine)?`<span class="badge bON_HOLD">${{esc(p.domaine||m.domaine)}}</span>`:""}}${{p.phase?`<span class="badge bON_HOLD">${{esc(p.phase)}}</span>`:""}}${{(p.priorite||m.priorite)?`<span class="badge bON_HOLD">prio:${{esc(p.priorite||m.priorite)}}</span>`:""}}</div>
    <div class="modal-sec"><div class="modal-stitle">avancement — ${{pv}}%</div><div class="prog-track"><div class="prog-fill" style="width:${{pv}}%;background:${{col}}"></div></div></div>
    <div class="modal-sec"><div class="modal-stitle">informations projet</div><div class="meta-grid">${{metaItems.map(([k,v])=>`<div class="meta-item"><div class="meta-key">${{esc(k)}}</div><div class="meta-val">${{esc(v)}}</div></div>`).join("")}}</div></div>
    ${{p.livrable_quinzaine?`<div class="modal-sec"><div class="modal-stitle">livrable quinzaine</div><div class="modal-text">${{esc(p.livrable_quinzaine)}} ${{badge(p.livrable_statut||"ON_HOLD")}}</div></div>`:""}}
    ${{p.actions_realises?`<div class="modal-sec"><div class="modal-stitle">actions realisees</div><div class="modal-text">${{esc(p.actions_realises)}}</div></div>`:""}}
    ${{p.actions_a_mener?`<div class="modal-sec"><div class="modal-stitle">actions a mener</div><div class="modal-text">${{esc(p.actions_a_mener)}}${{p.actions_echeance?`<br><span style="font-size:10px;color:var(--amber);font-family:var(--font-mono)">// echeance : ${{esc(p.actions_echeance)}}</span>`:""}}</div></div>`:""}}
    ${{p.risques?`<div class="modal-sec"><div class="modal-stitle">risques</div><div class="modal-text" style="color:var(--amber)">${{esc(p.risques)}}${{p.risque_niveau?` ${{badge("AT_RISK")}}`:""}} </div></div>`:""}}
    ${{p.points_blocage?`<div class="modal-sec"><div class="modal-stitle">blocages</div><div class="modal-text" style="color:var(--red)">${{esc(p.points_blocage)}}</div></div>`:""}}
    ${{(p.commentaire_libre||p.commentaire)?`<div class="modal-sec"><div class="modal-stitle">commentaire</div><div class="modal-text">${{esc(p.commentaire_libre||p.commentaire)}}</div></div>`:""}}
    ${{m.description?`<div class="modal-sec"><div class="modal-stitle">description</div><div class="modal-text" style="color:var(--text3)">${{esc(m.description)}}</div></div>`:""}}
    ${{hist.length>1?`<div class="modal-sec"><div class="modal-stitle">historique (${{hist.length}} quinzaines)</div>${{hist.map(h=>`<div class="hist-row"><span class="hist-q">${{esc(h.quinzaine)}}</span>${{badge(h.statut)}}<span style="font-weight:600;font-family:var(--font-mono);font-size:10px">${{h.avancement_pct||0}}%</span><span style="color:var(--text3);flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px">${{esc(h.actions_realises||h.livrable_quinzaine||"")}}</span></div>`).join("")}}</div>`:""}}`;
  document.getElementById("modal-overlay").classList.add("open");
}}
function closeModal(){{document.getElementById("modal-overlay").classList.remove("open");}}

function askChat(q){{document.getElementById("chat-input").value=q;sendChat();}}
function getChatApiUrl(){{return window.CHAT_API_URL||document.body.dataset.api||"";}}

async function sendChat(){{
  const input=document.getElementById("chat-input");const q=input.value.trim();if(!q)return;
  const msgs=document.getElementById("chat-msgs");const btn=document.querySelector(".chat-send");
  msgs.innerHTML+=`<div class="msg user"><div class="msg-av">YOU</div><div class="bubble">${{esc(q)}}</div></div>`;
  input.value="";btn.disabled=true;msgs.scrollTop=msgs.scrollHeight;
  const pid2=`msg-${{Date.now()}}`;
  msgs.innerHTML+=`<div class="msg" id="${{pid2}}"><div class="msg-av">AI</div><div class="bubble" style="color:var(--text3);font-family:var(--font-mono)">computing...</div></div>`;
  msgs.scrollTop=msgs.scrollHeight;
  const cacheKey=DATA.quinzaine+":"+q.toLowerCase().trim();
  const cached=LLM[cacheKey]||LLM[q.toLowerCase().trim()];
  if(cached){{_rep(pid2,cached);btn.disabled=false;msgs.scrollTop=msgs.scrollHeight;return;}}
  try{{
    const resp=await fetch(getChatApiUrl()+"/api/chat",{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify({{question:q,quinzaine:DATA.quinzaine}}),signal:AbortSignal.timeout(30000)}});
    if(!resp.ok)throw new Error("HTTP "+resp.status);
    const data=await resp.json();
    _rep(pid2,data.reponse||data.response||data.answer||JSON.stringify(data));
  }}catch(err){{
    const warn=`<span style="font-size:9px;color:var(--amber);font-family:var(--font-mono);display:block;margin-bottom:6px">// API offline - reponse locale</span>`;
    _rep(pid2,warn+repondreLocal(q));
  }}
  btn.disabled=false;msgs.scrollTop=msgs.scrollHeight;
}}
function _rep(id,t){{const b=document.getElementById(id)?.querySelector(".bubble");if(b)b.innerHTML=String(t).replace(/\\n/g,"<br>");}}

function repondreLocal(q){{
  const ql=q.toLowerCase();const P=DATA.projets;const k=DATA.kpis;
  if(/retard|late/.test(ql)){{const r=P.filter(p=>p.statut==="LATE");return r.length?r.length+" projet(s) LATE :\\n"+r.map(p=>"- "+nom(p)+" ("+( p.responsable_principal||"?")+")"+(p.points_blocage?" :: "+p.points_blocage:"")).join("\\n"):"Aucun projet LATE sur "+DATA.quinzaine+".";}}
  if(/risque|at_risk/.test(ql)){{const r=P.filter(p=>p.statut==="AT_RISK");return r.length?r.length+" projet(s) AT_RISK :\\n"+r.map(p=>"- "+nom(p)+" :: "+(p.risques||"non precise")).join("\\n"):"Aucun projet AT_RISK.";}}
  if(/blocage|bloqu/.test(ql)){{const r=P.filter(p=>p.points_blocage&&p.points_blocage.trim());return r.length?"Blocages actifs :\\n"+r.map(p=>"- "+nom(p)+" :: "+p.points_blocage).join("\\n"):"Aucun blocage signale.";}}
  if(/priorit|action/.test(ql)){{const r=P.filter(p=>p.actions_a_mener&&p.actions_a_mener.trim());return r.length?"Actions a mener :\\n"+r.map(p=>"- "+nom(p)+" : "+p.actions_a_mener+(p.actions_echeance?" ("+p.actions_echeance+")":"")).join("\\n"):"Aucune action enregistree.";}}
  if(/echeance|fin|deadline/.test(ql)){{const mbi={{}};(DATA.meta||[]).forEach(m=>{{mbi[m.projet_id||m.ref_sujet]=m;}});const r=P.filter(p=>{{const m=mbi[pid(p)];return m&&m.date_fin_prevue;}});return r.length?"Echeances :\\n"+r.map(p=>{{const m=mbi[pid(p)];return"- "+nom(p)+" -> "+m.date_fin_prevue;}}).join("\\n"):"Aucune date de fin dans META.";}}
  const match=P.find(p=>{{const n=nom(p).toLowerCase();return n&&ql.includes(n);}});
  if(match){{const mbi={{}};(DATA.meta||[]).forEach(m=>{{mbi[m.projet_id||m.ref_sujet]=m;}});const m=mbi[pid(match)]||{{}};return nom(match)+" :\\n- Statut : "+match.statut+" · "+pp(match)+"%\\n- Responsable : "+(match.responsable_principal||"?")+"\\n"+(m.date_fin_prevue?"- Fin prevue : "+m.date_fin_prevue+"\\n":"")+(match.risques?"- Risques : "+match.risques+"\\n":"")+(match.points_blocage?"- Blocages : "+match.points_blocage+"\\n":"");}}
  return"// "+DATA.quinzaine+"\\n- actifs : "+k.nb_projets_actifs+" | retard : "+k.nb_en_retard+" | risque : "+k.nb_at_risk+"\\n- avancement moyen : "+k.avancement_moyen+"%\\n- blocages : "+k.nb_blocages+"\\n(connecte le serveur API pour des reponses LLM)";
}}
</script>
</body>
</html>"""


def generer_dashboard(config_path="config.yaml", quinzaine=None, llm_reponses=None, output=None):
    import yaml
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) if Path(config_path).exists() else {}
    chemin_out = output or cfg.get("paths", {}).get("dashboard_out", "frontend/dashboard.html")
    try:
        from storage.storage import StorageManager as SM
    except ImportError:
        from storage import StorageManager as SM  # type: ignore
    sm = SM(config_path)
    donnees = preparer_donnees(sm, quinzaine)
    if not donnees:
        return None
    chemin = Path(chemin_out)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(generer_html(donnees, llm_reponses or {}), encoding="utf-8")
    log.info(f"Dashboard -> {chemin}")
    print(f"\nOuvre : {chemin.resolve()}\n")
    return str(chemin.resolve())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quinzaine", default=None, help="Ex: T1_2026_R1")
    parser.add_argument("--output",    default=None)
    parser.add_argument("--config",    default="config.yaml")
    parser.add_argument("--llm",       action="store_true")
    args = parser.parse_args()
    llm_cache = {}
    if args.llm:
        try:
            from rag_engine import enrichir_html_generator
            llm_cache = enrichir_html_generator(args.config, quinzaine=args.quinzaine)
        except ImportError:
            try:
                from query.rag_engine import enrichir_html_generator
                llm_cache = enrichir_html_generator(args.config, quinzaine=args.quinzaine)
            except Exception as e:
                log.warning(f"LLM indisponible : {e}")
    generer_dashboard(config_path=args.config, quinzaine=args.quinzaine,
                      llm_reponses=llm_cache, output=args.output)


if __name__ == "__main__":
    main()
