"""
html_generator.py
=================
Génère un dashboard HTML standalone avec données intégrées.
5 pages : Vue d'ensemble, Par domaine, Collaborateurs, Roadmap Gantt, Évolutions
+ Chat LLM + Export PDF (Ctrl+P)

Usage :
    python reporting/html_generator.py
    python reporting/html_generator.py --quinzaine Q1_2025_S2
    python reporting/html_generator.py --llm   (pré-génère réponses LLM)
"""

import sys
import json
import argparse
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

# Support structure plate (fichiers à la racine) et structure dossiers
try:
    from storage.storage import StorageManager
except ImportError:
    from storage import StorageManager

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)


def _calculer_snapshot(sm, q: str, quinzaines: list) -> dict:
    """Calcule toutes les données pour une quinzaine donnée."""
    df   = sm.charger_quinzaines(quinzaines=[q])
    kpis = sm.kpis(quinzaine=q)

    idx    = quinzaines.index(q)
    q_prev = quinzaines[idx - 1] if idx > 0 else None
    delta  = []
    if q_prev:
        df_d = sm.delta_quinzaines(q_prev, q)
        if not df_d.empty:
            delta = df_d.where(df_d.notna(), None).to_dict(orient="records")

    projets = df.where(df.notna(), None).to_dict(orient="records") if not df.empty else []

    par_domaine = {}
    par_resp    = {}
    for p in projets:
        d = p.get("domaine") or "Autre"
        par_domaine.setdefault(d, {"total":0,"on_track":0,"at_risk":0,"late":0,"done":0,"on_hold":0})
        par_domaine[d]["total"] += 1
        s = (p.get("statut") or "").upper()
        for k2 in ["on_track","at_risk","late","done","on_hold"]:
            if s == k2.upper(): par_domaine[d][k2] += 1
        r = p.get("responsable_principal") or "Non assigné"
        par_resp.setdefault(r, {"total":0,"en_cours":0,"domaines":[]})
        par_resp[r]["total"] += 1
        if s in ("ON_TRACK","AT_RISK"): par_resp[r]["en_cours"] += 1
        dom = p.get("domaine") or ""
        if dom and dom not in par_resp[r]["domaines"]:
            par_resp[r]["domaines"].append(dom)

    return {
        "projets":     projets,
        "kpis":        kpis,
        "par_domaine": par_domaine,
        "par_resp":    par_resp,
        "domaines":    sorted(set(p.get("domaine") or "" for p in projets if p.get("domaine"))),
        "q_prev":      q_prev,
        "delta":       delta,
    }


def preparer_donnees(sm: StorageManager, quinzaine: str | None = None) -> dict:
    quinzaines = sm.lister_quinzaines()
    if not quinzaines:
        log.error("Aucune donnée — lance excel_parser.py d'abord")
        return {}

    # Tri chronologique naturel (Q1_2025_S1 < Q1_2025_S2 < Q2_2025_S1 ...)
    quinzaines_triees = sorted(quinzaines)
    q_active = quinzaine or quinzaines_triees[-1]
    if q_active not in quinzaines_triees:
        log.warning(f"Quinzaine '{q_active}' introuvable, utilisation de la dernière")
        q_active = quinzaines_triees[-1]

    meta = sm.charger_meta()

    # Historiques tous projets (pour les modals de détail)
    df_all = sm.charger_quinzaines()
    historiques = {}
    if not df_all.empty:
        for pid in df_all["projet_id"].unique():
            h = sm.projet(pid)
            if not h.empty:
                historiques[pid] = h.where(h.notna(), None).to_dict(orient="records")

    # Snapshot de chaque quinzaine — embarqué pour le sélecteur JS
    snapshots = {}
    for q in quinzaines_triees:
        log.info(f"Préparation snapshot : {q}")
        snapshots[q] = _calculer_snapshot(sm, q, quinzaines_triees)

    snap = snapshots[q_active]

    return {
        "genere_le":   __import__("datetime").datetime.now().strftime("%d/%m/%Y à %H:%M"),
        "quinzaines":  quinzaines_triees,
        "quinzaine":   q_active,
        "q_prev":      snap["q_prev"],
        "kpis":        snap["kpis"],
        "projets":     snap["projets"],
        "domaines":    snap["domaines"],
        "par_domaine": snap["par_domaine"],
        "par_resp":    snap["par_resp"],
        "delta":       snap["delta"],
        "meta":        meta.where(meta.notna(), None).to_dict(orient="records") if not meta.empty else [],
        "historiques": historiques,
        "snapshots":   snapshots,
    }


CSS = """
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0;}
html,body{height:100%;font-size:14px;}
body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
     background:#f4f5f7;color:#1a1a2e;line-height:1.5;}
.shell{display:flex;height:100vh;overflow:hidden;}
.sidebar{width:210px;min-width:210px;background:#1a1a2e;color:#c8cfe0;
         display:flex;flex-direction:column;overflow-y:auto;flex-shrink:0;}
.main{flex:1;display:flex;flex-direction:column;overflow:hidden;}
.topbar{background:#fff;border-bottom:1px solid #e5e7eb;padding:10px 20px;
        display:flex;align-items:center;flex-shrink:0;gap:12px;}
.content{flex:1;overflow-y:auto;padding:20px;}
.logo{padding:18px 16px 14px;font-size:13px;font-weight:700;letter-spacing:.04em;
      color:#fff;border-bottom:1px solid #2d2d4a;}
.logo span{display:block;font-size:10px;font-weight:400;color:#8891a8;
           margin-top:2px;letter-spacing:.06em;text-transform:uppercase;}
.logo-date{font-size:9px;color:#555e78;margin-top:3px;}
.nav-section{padding:14px 16px 4px;font-size:9px;font-weight:700;
             text-transform:uppercase;letter-spacing:.1em;color:#555e78;}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 16px;font-size:12px;
          cursor:pointer;transition:background .12s;color:#c8cfe0;
          border-left:2px solid transparent;user-select:none;}
.nav-item:hover{background:rgba(255,255,255,.06);color:#fff;}
.nav-item.active{background:rgba(99,153,255,.12);color:#fff;
                 border-left-color:#4e8fff;font-weight:600;}
.nav-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.page-title{font-size:15px;font-weight:600;color:#1a1a2e;}
.spacer{flex:1;}
.snap-info{font-size:11px;color:#6b7280;}
.q-selector-wrap{padding:10px 14px 6px;}
.q-selector-label{font-size:9px;font-weight:700;color:#6b7280;letter-spacing:.08em;text-transform:uppercase;margin-bottom:5px;}
.q-selector{width:100%;background:#0d1117;color:#c8cfe0;border:1px solid #2a2f40;border-radius:6px;
            padding:6px 8px;font-size:11px;cursor:pointer;outline:none;}
.q-selector:focus{border-color:#4e8fff;}
.q-selector option{background:#0d1117;color:#c8cfe0;}
.gen-at{font-size:10px;color:#9ca3af;}
.btn-pdf{font-size:11px;padding:5px 12px;background:#1a1a2e;color:#fff;
         border:none;border-radius:6px;cursor:pointer;}
.page{display:none;} .page.active{display:block;}
.metrics-row{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:18px;}
.metric-card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:12px 14px;}
.metric-label{font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.05em;margin-bottom:3px;}
.metric-value{font-size:24px;font-weight:700;}
.metric-sub{font-size:10px;color:#9ca3af;margin-top:2px;}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}
.card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin-bottom:14px;}
.card-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
            color:#6b7280;margin-bottom:12px;}
.bar-rows{display:flex;flex-direction:column;gap:7px;}
.bar-row{display:flex;align-items:center;gap:8px;}
.bar-label{font-size:11px;min-width:110px;max-width:110px;color:#374151;
           overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.bar-track{flex:1;height:7px;background:#f3f4f6;border-radius:4px;overflow:hidden;}
.bar-fill{height:100%;border-radius:4px;}
.bar-count{font-size:11px;font-weight:600;min-width:22px;text-align:right;color:#374151;}
.proj-list{display:flex;flex-direction:column;gap:5px;}
.proj-item{display:flex;align-items:center;gap:7px;padding:7px 9px;border-radius:7px;
           border:1px solid #f0f0f5;font-size:12px;cursor:pointer;transition:background .1s;}
.proj-item:hover{background:#f8f9ff;}
.proj-dot{width:7px;height:7px;border-radius:50%;flex-shrink:0;}
.proj-name{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.proj-resp{font-size:10px;color:#9ca3af;min-width:60px;text-align:right;}
.proj-pct{font-size:10px;font-weight:600;color:#6b7280;min-width:30px;text-align:right;}
.badge{font-size:10px;padding:2px 7px;border-radius:20px;font-weight:600;
       white-space:nowrap;flex-shrink:0;}
.bON_TRACK{background:#d1fae5;color:#065f46;}
.bAT_RISK{background:#fef3c7;color:#b45309;}
.bLATE{background:#fee2e2;color:#991b1b;}
.bDONE{background:#ede9fe;color:#5b21b6;}
.bON_HOLD{background:#f3f4f6;color:#374151;}
.collab-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:14px;}
.collab-card{background:#fff;border:1px solid #e5e7eb;border-radius:10px;
             padding:12px;cursor:pointer;transition:box-shadow .15s;}
.collab-card:hover{box-shadow:0 2px 8px rgba(0,0,0,.08);}
.collab-card.selected{border-color:#4e8fff;box-shadow:0 0 0 2px #dbeafe;}
.avatar{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;
        justify-content:center;font-size:11px;font-weight:700;flex-shrink:0;}
.collab-header{display:flex;align-items:center;gap:8px;margin-bottom:8px;}
.collab-name{font-size:12px;font-weight:600;}
.collab-sub{font-size:10px;color:#6b7280;}
.charge-bar{height:5px;background:#f3f4f6;border-radius:3px;overflow:hidden;margin-top:6px;}
.charge-fill{height:100%;border-radius:3px;background:#4e8fff;}
.gantt-controls{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center;}
.gantt-controls select{font-size:12px;padding:4px 8px;border:1px solid #d1d5db;
                       border-radius:6px;background:#fff;cursor:pointer;}
.gantt-controls label{font-size:12px;color:#6b7280;}
.gantt-wrap{overflow-x:auto;}
.gantt-table{border-collapse:collapse;min-width:680px;width:100%;font-size:11px;}
.gantt-table th,.gantt-table td{border:0;padding:0;}
.g-label{padding:4px 8px;font-size:11px;color:#374151;white-space:nowrap;
         max-width:150px;overflow:hidden;text-overflow:ellipsis;min-width:150px;
         cursor:pointer;text-decoration:underline dotted #9ca3af;}
.g-header{text-align:center;font-size:10px;color:#6b7280;padding:4px 2px;
          border-bottom:1px solid #e5e7eb;min-width:40px;}
.g-cell{padding:3px 2px;position:relative;min-width:40px;height:26px;vertical-align:middle;}
.g-bar{position:absolute;top:5px;bottom:5px;border-radius:3px;}
.g-now{position:absolute;top:0;width:1.5px;background:#ef4444;bottom:0;z-index:5;opacity:.7;}
.g-today-head{border-bottom:2px solid #ef4444!important;color:#ef4444!important;font-weight:700;}
.gantt-legend{display:flex;flex-wrap:wrap;gap:12px;margin-top:10px;}
.gantt-legend span{font-size:10px;color:#6b7280;display:flex;align-items:center;gap:4px;}
.gantt-legend i{width:14px;height:6px;border-radius:2px;display:inline-block;}
.tl-item{display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #f3f4f6;}
.tl-item:last-child{border-bottom:none;}
.tl-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0;margin-top:4px;}
.tl-body{flex:1;}
.tl-title{font-size:12px;font-weight:600;margin-bottom:2px;cursor:pointer;}
.tl-title:hover{color:#4e8fff;}
.tl-desc{font-size:11px;color:#6b7280;line-height:1.5;margin-bottom:4px;}
.tl-meta{display:flex;gap:6px;align-items:center;flex-wrap:wrap;}
.tl-tag{font-size:10px;color:#7c3aed;background:#fdf4ff;padding:1px 6px;border-radius:10px;}
.chat-wrap{display:flex;flex-direction:column;height:calc(100vh - 106px);max-width:820px;margin:0 auto;}
.chat-qs{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px;}
.chat-q{font-size:11px;padding:4px 10px;background:#fff;border:1px solid #d1d5db;
        border-radius:20px;cursor:pointer;color:#374151;transition:all .12s;}
.chat-q:hover{border-color:#4e8fff;color:#1d4ed8;}
.chat-msgs{flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:12px;padding:4px 0;}
.msg{display:flex;gap:10px;align-items:flex-start;}
.msg.user{flex-direction:row-reverse;}
.msg-av{width:28px;height:28px;border-radius:8px;background:#1a1a2e;display:flex;
        align-items:center;justify-content:center;font-size:9px;font-weight:700;
        color:#8891a8;flex-shrink:0;}
.msg.user .msg-av{background:#dbeafe;color:#1d4ed8;}
.bubble{max-width:74%;background:#fff;border:1px solid #e5e7eb;border-radius:10px;
        padding:10px 14px;font-size:12px;line-height:1.6;color:#374151;white-space:pre-wrap;}
.msg.user .bubble{background:#eff6ff;border-color:#bfdbfe;}
.chat-bar{padding:10px 0;border-top:1px solid #e5e7eb;display:flex;gap:8px;flex-shrink:0;}
.chat-input{flex:1;background:#fff;border:1px solid #d1d5db;border-radius:8px;
            padding:9px 13px;font-family:inherit;font-size:12px;outline:none;
            resize:none;transition:border-color .12s;}
.chat-input:focus{border-color:#4e8fff;}
.chat-send{background:#1a1a2e;border:none;border-radius:8px;padding:9px 16px;
           color:#fff;font-family:inherit;font-size:12px;cursor:pointer;}
.chat-send:disabled{opacity:.4;cursor:default;}
.modal-overlay{display:none;position:fixed;inset:0;background:rgba(0,0,0,.35);
               z-index:200;align-items:center;justify-content:center;}
.modal-overlay.open{display:flex;}
.modal{background:#fff;border-radius:12px;width:580px;max-width:95vw;max-height:88vh;
       overflow-y:auto;padding:24px;box-shadow:0 8px 32px rgba(0,0,0,.15);}
.modal-close{float:right;cursor:pointer;font-size:18px;color:#9ca3af;
             border:none;background:none;line-height:1;padding:0;}
.modal-title{font-size:15px;font-weight:700;margin-bottom:6px;}
.modal-row{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px;}
.modal-sec{margin-top:14px;}
.modal-stitle{font-size:10px;font-weight:700;text-transform:uppercase;
              letter-spacing:.06em;color:#9ca3af;margin-bottom:6px;}
.modal-text{font-size:12px;color:#374151;line-height:1.6;}
.prog-track{height:8px;background:#f3f4f6;border-radius:4px;overflow:hidden;margin-top:4px;}
.prog-fill{height:100%;border-radius:4px;}
.filter-strip{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;}
.fchip{font-size:11px;padding:3px 10px;border-radius:20px;border:1px solid #d1d5db;
       color:#374151;cursor:pointer;background:#fff;transition:all .12s;}
.fchip:hover{border-color:#4e8fff;color:#1d4ed8;}
.fchip.active{background:#4e8fff;color:#fff;border-color:#4e8fff;}
@media(max-width:900px){
  .metrics-row{grid-template-columns:repeat(3,1fr);}
  .grid2{grid-template-columns:1fr;}
  .collab-grid{grid-template-columns:1fr 1fr;}
}
"""


def generer_html(donnees: dict, llm_cache: dict | None = None) -> str:
    data_js = json.dumps(donnees, ensure_ascii=False)
    llm_js  = json.dumps(llm_cache or {}, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Project Intelligence — {donnees.get('quinzaine','')}</title>
<style>{CSS}</style>
</head>
<body>
<div class="shell">
  <aside class="sidebar">
    <div class="logo">Project Intelligence
      <span>Outil de pilotage</span>
      <div class="logo-date" id="logo-date"></div>
    </div>
    <div class="q-selector-wrap">
      <div class="q-selector-label">Quinzaine</div>
      <select class="q-selector" id="q-selector" onchange="switchQuinzaine(this.value)"></select>
    </div>
    <div class="nav-section">Navigation</div>
    <div class="nav-item active" data-page="overview"><span class="nav-dot" style="background:#4e8fff"></span>Vue d'ensemble</div>
    <div class="nav-item" data-page="domaines"><span class="nav-dot" style="background:#10b981"></span>Par domaine</div>
    <div class="nav-item" data-page="collabs"><span class="nav-dot" style="background:#8b5cf6"></span>Collaborateurs</div>
    <div class="nav-item" data-page="gantt"><span class="nav-dot" style="background:#f59e0b"></span>Roadmap Gantt</div>
    <div class="nav-item" data-page="evolutions"><span class="nav-dot" style="background:#ef4444"></span>Évolutions</div>
    <div class="nav-section">Outils</div>
    <div class="nav-item" data-page="chat"><span class="nav-dot" style="background:#06b6d4"></span>Chat LLM</div>
  </aside>

  <div class="main">
    <div class="topbar">
      <span class="page-title" id="page-title">Vue d'ensemble</span>
      <span class="snap-info" id="snap-info"></span>
      <div class="spacer"></div>
      <span class="gen-at" id="gen-at"></span>
      <button class="btn-pdf" onclick="window.print()">Imprimer / PDF</button>
    </div>
    <div class="content">
      <div class="page active" id="page-overview"></div>
      <div class="page" id="page-domaines"></div>
      <div class="page" id="page-collabs"></div>
      <div class="page" id="page-gantt"></div>
      <div class="page" id="page-evolutions"></div>
      <div class="page" id="page-chat">
        <div class="chat-wrap">
          <div class="chat-qs" id="chat-qs"></div>
          <div class="chat-msgs" id="chat-msgs">
            <div class="msg">
              <div class="msg-av">AI</div>
              <div class="bubble">Bonjour ! Je réponds à tes questions sur les projets de la quinzaine <strong id="chat-q-label"></strong>.<br><br>Clique sur une suggestion ou pose ta propre question.</div>
            </div>
          </div>
          <div class="chat-bar">
            <textarea class="chat-input" id="chat-input" rows="2" placeholder="Question sur les projets..."
              onkeydown="if(event.key==='Enter'&&!event.shiftKey){{event.preventDefault();sendChat();}}"></textarea>
            <button class="chat-send" onclick="sendChat()">Envoyer</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="modal-overlay" id="modal-overlay">
  <div class="modal" id="modal-body"></div>
</div>

<script>
const DATA={data_js};
const LLM={llm_js};
const TC=["#4e8fff","#10b981","#8b5cf6","#f59e0b","#ef4444","#06b6d4","#ec4899","#f97316","#14b8a6","#84cc16"];
const SC={{ON_TRACK:"#10b981",AT_RISK:"#f59e0b",LATE:"#ef4444",DONE:"#8b5cf6",ON_HOLD:"#6b7280"}};
const SL={{ON_TRACK:"En cours",AT_RISK:"À risque",LATE:"En retard",DONE:"Terminé",ON_HOLD:"En pause"}};
const PAGES={{overview:"Vue d'ensemble",domaines:"Par domaine",collabs:"Collaborateurs",
              gantt:"Roadmap Gantt",evolutions:"Évolutions",chat:"Chat LLM"}};
let selCollab=null;

function esc(s){{return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}}
function badge(st){{return`<span class="badge b${{st}}">${{SL[st]||st||"—"}}</span>`;}}
function domColor(d){{const ds=[...new Set(DATA.projets.map(p=>p.domaine).filter(Boolean))].sort();return TC[ds.indexOf(d)%TC.length];}}
function initials(n){{return(n||"??").split(/\s+/).map(w=>w[0]).join("").toUpperCase().slice(0,2);}}
function avStyle(n){{const c=[["#dbeafe","#1d4ed8"],["#d1fae5","#065f46"],["#ede9fe","#5b21b6"],["#fef3c7","#b45309"],["#fce7f3","#9d174d"],["#e0f2fe","#0369a1"]];const[bg,fg]=c[(n||"X").charCodeAt(0)%c.length];return`background:${{bg}};color:${{fg}}`;}}
function projItem(p){{const col=SC[p.statut]||"#9ca3af";return`<div class="proj-item" onclick="openModal('${{esc(p.projet_id)}}')"><span class="proj-dot" style="background:${{col}}"></span><span class="proj-name" title="${{esc(p.projet_nom)}}">${{esc(p.projet_nom)}}</span>${{badge(p.statut)}}<span class="proj-pct">${{p.avancement_pct||0}}%</span><span class="proj-resp">${{esc(p.responsable_principal||"")}}</span></div>`;}}

function switchQuinzaine(q){{
  if(!DATA.snapshots||!DATA.snapshots[q])return;
  const snap=DATA.snapshots[q];
  DATA.quinzaine=q;
  DATA.q_prev=snap.q_prev;
  DATA.kpis=snap.kpis;
  DATA.projets=snap.projets;
  DATA.domaines=snap.domaines;
  DATA.par_domaine=snap.par_domaine;
  DATA.par_resp=snap.par_resp;
  DATA.delta=snap.delta;
  document.getElementById("snap-info").textContent=q+(snap.q_prev?" (vs "+snap.q_prev+")":"");
  document.getElementById("chat-q-label").textContent=q;
  renderOverview();renderDomaines();renderCollabs();renderEvolutions();
  const ganttPage=document.getElementById("page-gantt");
  if(ganttPage&&ganttPage.innerHTML.trim()!=="")renderGantt();
}}

(function init(){{
  document.getElementById("logo-date").textContent="Généré le "+DATA.genere_le;
  document.getElementById("gen-at").textContent=DATA.genere_le;
  document.getElementById("snap-info").textContent=DATA.quinzaine+(DATA.q_prev?" (vs "+DATA.q_prev+")":"");
  document.getElementById("chat-q-label").textContent=DATA.quinzaine;

  // Sélecteur quinzaine — ordre chronologique, la plus récente en premier
  const sel=document.getElementById("q-selector");
  const qs_sorted=[...DATA.quinzaines].reverse();
  qs_sorted.forEach(q=>{{
    const opt=document.createElement("option");
    opt.value=q; opt.textContent=q;
    if(q===DATA.quinzaine)opt.selected=true;
    sel.appendChild(opt);
  }});

  // Boutons alignés exactement sur les clés du cache LLM (QUESTIONS_STANDARD dans rag_engine.py)
  const qsChat=[
    "résume l\'avancement global de la quinzaine",
    "quels projets sont en retard ?",
    "quels projets sont à risque ?",
    "quelles décisions ont été prises ?",
    "y a-t-il des blocages actifs ?",
    "quelles actions sont à mener en priorité ?",
    "quel est le projet le plus en difficulté ?"
  ];
  const qsLabels=[
    "Résumé global","En retard","À risque","Décisions","Blocages","Actions prioritaires","En difficulté"
  ];
  document.getElementById("chat-qs").innerHTML=qsChat.map((q,i)=>`<button class="chat-q" onclick="askChat('${{q}}')">${{qsLabels[i]}}</button>`).join("");
  document.querySelectorAll(".nav-item[data-page]").forEach(el=>{{
    el.addEventListener("click",()=>{{
      document.querySelectorAll(".nav-item").forEach(n=>n.classList.remove("active"));
      document.querySelectorAll(".page").forEach(p=>p.classList.remove("active"));
      el.classList.add("active");
      document.getElementById("page-"+el.dataset.page).classList.add("active");
      document.getElementById("page-title").textContent=PAGES[el.dataset.page];
      if(el.dataset.page==="gantt")renderGantt();
    }});
  }});
  document.getElementById("modal-overlay").addEventListener("click",e=>{{if(e.target===document.getElementById("modal-overlay"))closeModal();}});
  renderOverview();renderDomaines();renderCollabs();renderEvolutions();
}})();

function openModal(pid){{
  const p=DATA.projets.find(x=>x.projet_id===pid);if(!p)return;
  const hist=DATA.historiques[pid]||[];
  const pct=p.avancement_pct||0;const col=SC[p.statut]||"#9ca3af";
  document.getElementById("modal-body").innerHTML=`
    <button class="modal-close" onclick="closeModal()">✕</button>
    <div class="modal-title">${{esc(p.projet_nom)}}</div>
    <div class="modal-row">${{badge(p.statut)}}<span class="badge" style="background:#f3f4f6;color:#374151">${{esc(p.domaine||"")}}</span><span class="badge" style="background:#f3f4f6;color:#374151">${{esc(p.phase||"")}}</span></div>
    <div class="modal-sec"><div class="modal-stitle">Avancement — ${{pct}}%</div><div class="prog-track"><div class="prog-fill" style="width:${{pct}}%;background:${{col}}"></div></div></div>
    <div class="modal-sec"><div class="modal-stitle">Équipe</div><div class="modal-text"><strong>Responsable :</strong> ${{esc(p.responsable_principal||"—")}}<br><strong>Effectifs :</strong> ${{esc(p.effectifs||"—")}}</div></div>
    ${{p.livrable_quinzaine?`<div class="modal-sec"><div class="modal-stitle">Livrable</div><div class="modal-text">${{esc(p.livrable_quinzaine)}} ${{badge(p.livrable_statut||"ON_HOLD")}}</div></div>`:""}}
    ${{p.decisions?`<div class="modal-sec"><div class="modal-stitle">Décisions</div><div class="modal-text">${{esc(p.decisions)}}</div></div>`:""}}
    ${{p.actions_a_mener?`<div class="modal-sec"><div class="modal-stitle">Actions à mener</div><div class="modal-text">${{esc(p.actions_a_mener)}}${{p.actions_responsable?`<br><span style="color:#6b7280">→ ${{esc(p.actions_responsable)}}</span>`:""}}${{p.actions_echeance?`<br><span style="color:#f59e0b">Échéance : ${{esc(p.actions_echeance)}}</span>`:""}}</div></div>`:""}}
    ${{p.risques?`<div class="modal-sec"><div class="modal-stitle">Risques</div><div class="modal-text" style="color:#ef4444">${{esc(p.risques)}}${{p.risque_niveau?` <span class="badge bLATE">${{esc(p.risque_niveau)}}</span>`:""}} </div></div>`:""}}
    ${{p.points_blocage?`<div class="modal-sec"><div class="modal-stitle">Blocages</div><div class="modal-text" style="color:#dc2626">${{esc(p.points_blocage)}}</div></div>`:""}}
    ${{hist.length>1?`<div class="modal-sec"><div class="modal-stitle">Historique (${{hist.length}} quinzaines)</div>${{hist.map(h=>`<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid #f3f4f6;font-size:11px"><span style="min-width:90px;color:#6b7280">${{esc(h.quinzaine)}}</span>${{badge(h.statut)}}<span style="font-weight:600">${{h.avancement_pct||0}}%</span><span style="color:#9ca3af;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{esc(h.decisions||"")}}</span></div>`).join("")}}</div>`:""}}`;
  document.getElementById("modal-overlay").classList.add("open");
}}
function closeModal(){{document.getElementById("modal-overlay").classList.remove("open");}}

function renderOverview(){{
  const k=DATA.kpis;const P=DATA.projets;
  const maxD=Math.max(...Object.values(DATA.par_domaine).map(d=>d.total),1);
  const maxR=Math.max(...Object.values(DATA.par_resp).map(r=>r.total),1);
  const top=[...P].sort((a,b)=>({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[a.statut]||9)-({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[b.statut]||9)).slice(0,8);
  document.getElementById("page-overview").innerHTML=`
    <div class="metrics-row">
      <div class="metric-card"><div class="metric-label">Projets actifs</div><div class="metric-value" style="color:#4e8fff">${{k.nb_projets_actifs||0}}</div><div class="metric-sub">cette quinzaine</div></div>
      <div class="metric-card"><div class="metric-label">À risque / retard</div><div class="metric-value" style="color:#ef4444">${{(k.nb_at_risk||0)+(k.nb_en_retard||0)}}</div><div class="metric-sub">${{k.nb_en_retard||0}} retard · ${{k.nb_at_risk||0}} risque</div></div>
      <div class="metric-card"><div class="metric-label">Terminés</div><div class="metric-value" style="color:#10b981">${{k.nb_done||0}}</div><div class="metric-sub">${{k.nb_on_hold||0}} en pause</div></div>
      <div class="metric-card"><div class="metric-label">Avancement moyen</div><div class="metric-value" style="color:#8b5cf6">${{k.avancement_moyen||0}}%</div><div class="metric-sub">tous projets actifs</div></div>
      <div class="metric-card"><div class="metric-label">Décisions / Blocages</div><div class="metric-value">${{k.nb_decisions||0}}</div><div class="metric-sub">${{k.nb_blocages||0}} blocage(s)</div></div>
    </div>
    <div class="grid2">
      <div class="card"><div class="card-title">Par domaine</div><div class="bar-rows">${{Object.entries(DATA.par_domaine).sort((a,b)=>b[1].total-a[1].total).map(([d,s])=>`<div class="bar-row"><span class="bar-label" title="${{esc(d)}}">${{esc(d)}}</span><div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxD*100)}}%;background:${{domColor(d)}}"></div></div><span class="bar-count">${{s.total}}</span></div>`).join("")}}</div></div>
      <div class="card"><div class="card-title">Par responsable</div><div class="bar-rows">${{Object.entries(DATA.par_resp).sort((a,b)=>b[1].total-a[1].total).map(([r,s])=>`<div class="bar-row"><span class="bar-label" title="${{esc(r)}}">${{esc(r)}}</span><div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxR*100)}}%;background:#4e8fff"></div></div><span class="bar-count">${{s.total}}</span></div>`).join("")}}</div></div>
    </div>
    <div class="card"><div class="card-title">Projets — vue prioritaire</div><div class="proj-list">${{top.map(projItem).join("")}}</div></div>`;
}}

function renderDomaines(){{
  let html='<div class="filter-strip" id="df"><span class="fchip active" data-val="">Tous</span>'+DATA.domaines.map(d=>'<span class="fchip" data-val="'+esc(d)+'">'+esc(d)+'</span>').join('')+'</div>';
  html+=DATA.domaines.map(dom=>{{
    const pr=DATA.projets.filter(p=>p.domaine===dom);const s=DATA.par_domaine[dom]||{{}};
    let badges='';
    if(s.on_track)badges+='<span class="badge bON_TRACK">'+s.on_track+' en cours</span>';
    if(s.at_risk)badges+='<span class="badge bAT_RISK">'+s.at_risk+' à risque</span>';
    if(s.late)badges+='<span class="badge bLATE">'+s.late+' retard</span>';
    if(s.done)badges+='<span class="badge bDONE">'+s.done+' terminé</span>';
    return'<div class="card dom-sec" data-dom="'+esc(dom)+'"><div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;flex-wrap:wrap;gap:6px"><div style="display:flex;align-items:center;gap:8px"><span style="width:10px;height:10px;border-radius:50%;background:'+domColor(dom)+';flex-shrink:0"></span><span style="font-size:13px;font-weight:700">'+esc(dom)+'</span></div><div style="display:flex;gap:4px;flex-wrap:wrap">'+badges+'</div></div><div class="proj-list">'+pr.map(projItem).join('')+'</div></div>';
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
    <div class="collab-grid">${{resps.map(([name,r])=>`<div class="collab-card ${{name===sel?"selected":""}}" onclick="renderCollabs('${{esc(name)}}')"><div class="collab-header"><div class="avatar" style="${{avStyle(name)}}">${{initials(name)}}</div><div><div class="collab-name">${{esc(name)}}</div><div class="collab-sub">${{r.total}} projet${{r.total>1?"s":""}} · ${{r.en_cours}} en cours</div></div></div><div style="display:flex;gap:4px;flex-wrap:wrap">${{r.domaines.slice(0,3).map(d=>`<span style="font-size:9px;padding:2px 6px;border-radius:10px;background:#f3f4f6;color:#6b7280">${{esc(d)}}</span>`).join("")}}</div><div class="charge-bar"><div class="charge-fill" style="width:${{Math.round(r.en_cours/maxE*100)}}%"></div></div></div>`).join("")}}</div>
    <div class="card"><div class="card-title">Projets de ${{esc(sel)}}</div><div class="proj-list">${{detail.map(projItem).join("")||'<div style="color:#9ca3af;font-size:12px;padding:8px">Aucun projet.</div>'}}</div></div>`;
}}

function renderGantt(){{
  const el=document.getElementById("page-gantt");
  if(el.dataset.init)return;el.dataset.init="1";
  el.innerHTML=`<div class="gantt-controls"><label>Grouper :</label><select id="gg" onchange="buildGantt()"><option value="domaine">Domaine</option><option value="responsable_principal">Responsable</option></select><label style="margin-left:8px">Statut :</label><select id="gf" onchange="buildGantt()"><option value="">Tous</option><option value="ON_TRACK">En cours</option><option value="AT_RISK">À risque</option><option value="LATE">En retard</option><option value="DONE">Terminé</option></select></div><div class="card"><div id="gi"></div><div class="gantt-legend" id="gl"></div></div>`;
  buildGantt();
}}
function buildGantt(){{
  const grp=document.getElementById("gg")?.value||"domaine";
  const fst=document.getElementById("gf")?.value||"";
  let P=DATA.projets.filter(p=>p.avancement_pct!=null);
  if(fst)P=P.filter(p=>p.statut===fst);
  if(!P.length){{document.getElementById("gi").innerHTML='<div style="font-size:12px;color:#9ca3af;padding:12px">Aucun projet.</div>';return;}}
  const now=new Date();const months=[];
  for(let i=-1;i<=4;i++)months.push(new Date(now.getFullYear(),now.getMonth()+i,1));
  const todayM=now.toISOString().slice(0,7);
  const MFR=["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];
  const groups={{}};P.forEach(p=>{{const k=p[grp]||"Autre";if(!groups[k])groups[k]=[];groups[k].push(p);}});
  let html=`<div class="gantt-wrap"><table class="gantt-table"><thead><tr><th class="g-label" style="font-size:10px;color:#9ca3af;font-weight:400">Projet</th>${{months.map(m=>{{const k=m.toISOString().slice(0,7);return`<th class="g-header${{k===todayM?" g-today-head":""}}">${{MFR[m.getMonth()]}}<br>${{String(m.getFullYear()).slice(2)}}</th>`;}}).join("")}}</tr></thead><tbody>`;
  Object.entries(groups).sort().forEach(([g,items],gi)=>{{
    const gc=TC[gi%TC.length];
    html+=`<tr><td colspan="${{months.length+1}}" style="padding:8px 8px 2px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:#6b7280;background:#f9fafb;border-top:1px solid #e5e7eb">${{esc(g)}}</td></tr>`;
    items.forEach(p=>{{
      const pc=grp==="domaine"?domColor(p.domaine):gc;
      const pct=p.avancement_pct||0;
      html+=`<tr><td class="g-label" onclick="openModal('${{esc(p.projet_id)}}')" title="${{esc(p.projet_nom)}}">${{esc(p.projet_nom)}}</td>`;
      months.forEach((m,mi)=>{{
        const isT=m.toISOString().slice(0,7)===todayM;
        const op=[0.35,0.6,0.85,0.5,0.3,0.2][mi]*(pct/100);
        const bar=op>0.05?`<div class="g-bar" style="left:0;right:0;background:${{pc}};opacity:${{op.toFixed(2)}}"></div>`:"";
        const nl=isT?`<div class="g-now" style="left:${{Math.round((now.getDate()-1)/new Date(now.getFullYear(),now.getMonth()+1,0).getDate()*100)}}%"></div>`:"";
        html+=`<td class="g-cell">${{bar}}${{nl}}</td>`;
      }});
      html+=`</tr>`;
    }});
  }});
  html+=`</tbody></table></div>`;
  document.getElementById("gi").innerHTML=html;
  document.getElementById("gl").innerHTML=
    `<span style="display:flex;align-items:center;gap:4px"><i style="width:14px;height:2px;background:#ef4444;display:inline-block"></i>Aujourd'hui</span>`+
    Object.keys(groups).slice(0,8).map((g,i)=>`<span style="display:flex;align-items:center;gap:4px"><i style="width:14px;height:6px;background:${{TC[i%TC.length]}};border-radius:2px;display:inline-block"></i>${{esc(g)}}</span>`).join("");
}}

function renderEvolutions(){{
  const delta=DATA.delta||[];
  const sub=DATA.q_prev?`Évolutions entre ${{DATA.q_prev}} et ${{DATA.quinzaine}}`:`Snapshot initial — ${{DATA.quinzaine}}`;
  let html=`<div style="font-size:12px;color:#6b7280;margin-bottom:14px">${{sub}}</div>`;
  html+=`<div class="card"><div class="card-title">Changements détectés (${{delta.length}})</div>`;
  if(!delta.length)html+=`<div style="font-size:12px;color:#9ca3af;padding:8px">${{DATA.q_prev?"Aucun changement.":"Premier snapshot."}}</div>`;
  else html+=`<div>${{delta.map(d=>{{
    const dv=d.delta_avancement||0;const sign=dv>0?"+":"";
    const dc=dv>0?"#10b981":dv<0?"#ef4444":"#9ca3af";
    return`<div class="tl-item"><div class="tl-dot" style="background:${{dc}}"></div><div class="tl-body"><div class="tl-title" onclick="openModal('${{esc(d.projet_id)}}')">${{esc(d.projet_nom||d.projet_id)}}</div><div class="tl-meta">${{d.statut_avant&&d.statut_apres&&d.statut_avant!==d.statut_apres?`<span class="tl-tag">${{SL[d.statut_avant]||d.statut_avant}} → ${{SL[d.statut_apres]||d.statut_apres}}</span>`:""}}${{dv!==0?`<span class="tl-tag" style="color:${{dc}};background:${{dv>0?"#f0fdf4":"#fff1f2"}}">${{sign}}${{Math.round(dv)}}%</span>`:""}}${{badge(d.statut_apres||"ON_HOLD")}}</div></div></div>`;
  }}).join("")}}</div>`;
  html+=`</div>`;
  const alertes=DATA.projets.filter(p=>p.points_blocage||p.statut==="LATE"||p.statut==="AT_RISK");
  if(alertes.length)html+=`<div class="card"><div class="card-title">Points d'attention (${{alertes.length}})</div><div class="proj-list">${{alertes.map(projItem).join("")}}</div></div>`;
  document.getElementById("page-evolutions").innerHTML=html;
}}

function askChat(q){{document.getElementById("chat-input").value=q;sendChat();}}
function llmLookup(q){{
  // 1. Correspondance exacte sur la quinzaine active
  const key=DATA.quinzaine+":"+q.toLowerCase().trim();
  if(LLM[key])return LLM[key];
  // 2. Correspondance exacte sans préfixe quinzaine (cache généré sans préfixe)
  const plain=q.toLowerCase().trim();
  if(LLM[plain])return LLM[plain];
  // 3. Recherche floue : trouve la clé du cache qui contient le plus de mots de la question
  const words=plain.split(/\s+/).filter(w=>w.length>3);
  let best=null,bestScore=0;
  for(const[k,v] of Object.entries(LLM)){{
    const score=words.filter(w=>k.includes(w)).length;
    if(score>bestScore){{bestScore=score;best=v;}}
  }}
  if(bestScore>=2)return best;
  return null;
}}
function sendChat(){{
  const input=document.getElementById("chat-input");const q=input.value.trim();if(!q)return;
  const msgs=document.getElementById("chat-msgs");const btn=document.querySelector(".chat-send");
  msgs.innerHTML+=`<div class="msg user"><div class="msg-av">Toi</div><div class="bubble">${{esc(q)}}</div></div>`;
  input.value="";btn.disabled=true;msgs.scrollTop=msgs.scrollHeight;
  const pid=`msg-${{Date.now()}}`;
  msgs.innerHTML+=`<div class="msg" id="${{pid}}"><div class="msg-av">AI</div><div class="bubble" style="color:#9ca3af">Analyse…</div></div>`;
  msgs.scrollTop=msgs.scrollHeight;
  setTimeout(()=>{{
    const cached=llmLookup(q);
    const r=cached||repondreLocal(q);
    const src=cached?"":"<span style=\"font-size:10px;color:#9ca3af;display:block;margin-top:6px\">⚡ Réponse locale — LLM non activé</span>";
    document.getElementById(pid).querySelector(".bubble").innerHTML=r.replace(/\n/g,"<br>").replace(/\\n/g,"<br>")+src;
    btn.disabled=false;msgs.scrollTop=msgs.scrollHeight;
  }},300);
}}
function repondreLocal(q){{
  const ql=q.toLowerCase();const P=DATA.projets;const k=DATA.kpis;
  if(/retard|late/.test(ql)){{const r=P.filter(p=>p.statut==="LATE");return r.length?r.length+" projet(s) en retard :\\n"+r.map(p=>"- "+p.projet_nom+" ("+( p.responsable_principal||"?")+")"+(p.points_blocage?" : "+p.points_blocage:"")).join("\\n"):"Aucun projet en retard sur "+DATA.quinzaine+".";}}
  if(/risque|at_risk/.test(ql)){{const r=P.filter(p=>p.statut==="AT_RISK");return r.length?r.length+" projet(s) à risque :\\n"+r.map(p=>"- "+p.projet_nom+" : "+(p.risques||"non précisé")).join("\\n"):"Aucun projet à risque.";}}
  if(/décision|decision/.test(ql)){{const r=P.filter(p=>p.decisions&&p.decisions.trim());return r.length?"Décisions sur "+DATA.quinzaine+" :\\n"+r.map(p=>"- "+p.projet_nom+" : "+p.decisions).join("\\n"):"Aucune décision enregistrée.";}}
  if(/blocage|bloqu/.test(ql)){{const r=P.filter(p=>p.points_blocage&&p.points_blocage.trim());return r.length?"Blocages actifs :\\n"+r.map(p=>"- "+p.projet_nom+" : "+p.points_blocage).join("\\n"):"Aucun blocage signalé.";}}
  return"Résumé "+DATA.quinzaine+" :\\n- "+k.nb_projets_actifs+" projets actifs\\n- "+k.nb_en_retard+" en retard · "+k.nb_at_risk+" à risque\\n- Avancement moyen : "+k.avancement_moyen+"%\\n- "+k.nb_decisions+" décision(s) · "+k.nb_blocages+" blocage(s)";
}}
</script>
</body>
</html>"""


def generer_dashboard(
    config_path: str = "config.yaml",
    quinzaine: str | None = None,
    llm_reponses: dict | None = None,
    output: str | None = None,
) -> str | None:
    """
    Génère le dashboard HTML et retourne le chemin du fichier créé.
    Appelable depuis run_pipeline.py ou en standalone.

    Paramètres :
        config_path   : chemin vers config.yaml
        quinzaine     : quinzaine ciblée (None = dernière)
        llm_reponses  : cache LLM pré-généré (dict question→réponse)
        output        : chemin de sortie (remplace la valeur de config.yaml)
    """
    import yaml
    cfg = yaml.safe_load(Path(config_path).read_text()) if Path(config_path).exists() else {}
    chemin_out = output or cfg.get("paths", {}).get("dashboard_out", "frontend/dashboard.html")

    try:
        from storage.storage import StorageManager as SM
    except ImportError:
        from storage import StorageManager as SM  # type: ignore

    sm      = SM(config_path)
    donnees = preparer_donnees(sm, quinzaine)
    if not donnees:
        return None

    chemin = Path(chemin_out)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(generer_html(donnees, llm_reponses or {}), encoding="utf-8")
    log.info(f"Dashboard → {chemin}")
    return str(chemin.resolve())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quinzaine", default=None)
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

    chemin = generer_dashboard(
        config_path=args.config,
        quinzaine=args.quinzaine,
        llm_reponses=llm_cache,
        output=args.output,
    )
    if chemin:
        print(f"\nOuvre : {chemin}\n")


if __name__ == "__main__":
    main()
