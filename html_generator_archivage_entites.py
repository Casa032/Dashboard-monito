"""
=======================================================================
MODIFICATIONS html_generator.py — ARCHIVAGE + FILTRE ENTITÉ
=======================================================================
5 modifications dans l'ordre. Chaque section indique exactement
QUOI chercher et QUOI remplacer/ajouter.
=======================================================================
"""


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 1 — preparer_donnees()
# Charger archivage et entités
#
# CHERCHER :
#     agenda_list = agenda.where(...).to_dict(...) if not agenda.empty else []
#
#     return {
#
# REMPLACER par :
# ═══════════════════════════════════════════════════════════════════════

    agenda_list = agenda.where(agenda.notna(), None).to_dict(orient="records") if not agenda.empty else []

    # ARCHIVAGE — projets terminés 12 mois glissants
    archivage = sm.charger_archivage(mois_glissants=12)
    archivage_list = archivage.where(archivage.notna(), None).to_dict(orient="records") if not archivage.empty else []

    # ENTITÉS — extraites dynamiquement depuis les données
    entites = sm.lister_entites()

    return {
        "genere_le":   datetime.now().strftime("%d/%m/%Y a %H:%M"),
        "quinzaines":  quinzaines_triees,
        "quinzaine":   q_active,
        "q_prev":      snap["q_prev"],
        "kpis":        snap["kpis"],
        "projets":     snap["projets"],
        "domaines":    snap["domaines"],
        "entites":     entites,           # ← NOUVEAU
        "par_domaine": snap["par_domaine"],
        "par_resp":    snap["par_resp"],
        "delta":       snap["delta"],
        "meta":        meta_list,
        "historiques": historiques,
        "snapshots":   snapshots,
        "agenda":      agenda_list,
        "archivage":   archivage_list,    # ← NOUVEAU
    }


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 2 — renderOverview()
# Ajouter le filtre entité et la section archivage
#
# CHERCHER dans renderOverview() :
#     document.getElementById("page-overview").innerHTML=`
#       <div class="metrics-row">
#
# REMPLACER tout le contenu de innerHTML par :
# ═══════════════════════════════════════════════════════════════════════

  document.getElementById("page-overview").innerHTML=`
    <div class="metrics-row">
      <div class="metric-card c-cyan"><div class="metric-label">projets actifs</div><div class="metric-value">${{k.nb_projets_actifs||0}}</div><div class="metric-sub">cette quinzaine</div></div>
      <div class="metric-card c-red"><div class="metric-label">a risque / retard</div><div class="metric-value">${{(k.nb_at_risk||0)+(k.nb_en_retard||0)}}</div><div class="metric-sub">${{k.nb_en_retard||0}} retard · ${{k.nb_at_risk||0}} risque</div></div>
      <div class="metric-card c-green"><div class="metric-label">termines</div><div class="metric-value">${{k.nb_done||0}}</div><div class="metric-sub">${{k.nb_on_hold||0}} en pause</div></div>
      <div class="metric-card c-violet"><div class="metric-label">avancement moyen</div><div class="metric-value">${{k.avancement_moyen||0}}%</div><div class="metric-sub">tous projets actifs</div></div>
      <div class="metric-card c-amber"><div class="metric-label">decisions / blocages</div><div class="metric-value">${{k.nb_decisions||0}}</div><div class="metric-sub">${{k.nb_blocages||0}} blocage(s)</div></div>
    </div>
    ${{buildFiltreEntite("ov")}}
    ${{alertes.length?`<div class="card"><div class="card-title">alertes actives (${{alertes.length}})</div><div class="proj-list" id="ov-proj-list">${{alertes.map(projItem).join("")}}</div></div>`:""}}
    <div class="grid2">
      <div class="card"><div class="card-title">par domaine</div><div class="bar-rows">${{Object.entries(DATA.par_domaine).sort((a,b)=>b[1].total-a[1].total).map(([d,s])=>`<div class="bar-row"><span class="bar-label" title="${{esc(d)}}">${{esc(d)}}</span><div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxD*100)}}%;background:${{domColor(d)}}"></div></div><span class="bar-count">${{s.total}}</span></div>`).join("")}}</div></div>
      <div class="card"><div class="card-title">par responsable</div><div class="bar-rows">${{Object.entries(DATA.par_resp).sort((a,b)=>b[1].total-a[1].total).map(([r,s])=>`<div class="bar-row"><span class="bar-label" title="${{esc(r)}}">${{esc(r)}}</span><div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxR*100)}}%;background:#00d4ff"></div></div><span class="bar-count">${{s.total}}</span></div>`).join("")}}</div></div>
    </div>
    <div class="card"><div class="card-title">projets — vue prioritaire (${{top.length}})</div><div class="proj-list" id="ov-top-list">${{top.map(projItem).join("")}}</div></div>
    ${{buildArchivageSection()}}`;

  // Attacher les événements du filtre entité
  attachFiltreEntite("ov", (ent)=>filterOverviewByEntite(ent));


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 3 — renderDomaines()
# Ajouter le filtre entité
#
# CHERCHER au début de renderDomaines() :
#     let html='<div class="filter-strip" id="df">...
#
# REMPLACER par :
# ═══════════════════════════════════════════════════════════════════════

  let html=buildFiltreEntite("dom")+'<div class="filter-strip" id="df"><span class="fchip active" data-val="">Tous</span>'+DATA.domaines.map(d=>'<span class="fchip" data-val="'+esc(d)+'">'+esc(d)+'</span>').join('')+'</div>';
  html+=DATA.domaines.map(dom=>{{
    const pr=DATA.projets.filter(p=>p.domaine===dom);
    // ... (reste inchangé)


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 4 — Ajouter les fonctions helpers JS
# À ajouter AVANT renderOverview()
# ═══════════════════════════════════════════════════════════════════════

function _eclaterEntites(val){{
  if(!val||String(val).trim()==="")return[];
  return String(val).split(/[;,]/).map(e=>e.trim()).filter(Boolean);
}}

function _projetMatchEntite(p, ent){{
  if(!ent)return true;
  return _eclaterEntites(p.entite_concerne||p.entite_concerne_meta||"").includes(ent);
}}

function buildFiltreEntite(prefix){{
  const entites=DATA.entites||[];
  if(!entites.length)return"";
  return`<div class="filter-strip" id="fe-${{prefix}}" style="margin-bottom:8px">
    <span style="font-size:9px;color:var(--text3);line-height:22px;font-family:var(--font-mono)">entité :</span>
    <span class="fchip active" data-ent="" onclick="handleFiltreEntite('${{prefix}}',this,'')">Toutes</span>
    ${{entites.map(e=>`<span class="fchip" data-ent="${{esc(e)}}" onclick="handleFiltreEntite('${{prefix}}',this,'${{esc(e)}}')">${{esc(e)}}</span>`).join("")}}
  </div>`;
}}

function handleFiltreEntite(prefix, el, ent){{
  document.querySelectorAll(`#fe-${{prefix}} .fchip`).forEach(c=>c.classList.remove("active"));
  el.classList.add("active");
  if(prefix==="ov")filterOverviewByEntite(ent);
  else if(prefix==="dom")filterDomainesByEntite(ent);
  else if(prefix==="col")filterCollabsByEntite(ent);
  else if(prefix==="gantt"){{selEntiteGantt=ent;buildGantt();}}
}}

function attachFiltreEntite(prefix, callback){{
  document.querySelectorAll(`#fe-${{prefix}} .fchip`).forEach(c=>{{
    c.onclick=()=>{{
      document.querySelectorAll(`#fe-${{prefix}} .fchip`).forEach(x=>x.classList.remove("active"));
      c.classList.add("active");
      callback(c.dataset.ent||"");
    }};
  }});
}}

function filterOverviewByEntite(ent){{
  const alertes=DATA.projets.filter(p=>(p.statut==="LATE"||p.statut==="AT_RISK"||p.points_blocage)&&_projetMatchEntite(p,ent));
  const top=[...DATA.projets].filter(p=>_projetMatchEntite(p,ent)).sort((a,b)=>
    ({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[a.statut]||9)-
    ({{"LATE":0,"AT_RISK":1,"ON_TRACK":2,"ON_HOLD":3,"DONE":4}}[b.statut]||9)
  ).slice(0,10);
  const listAl=document.getElementById("ov-proj-list");
  if(listAl)listAl.innerHTML=alertes.map(projItem).join("")||'<div style="font-size:10px;color:var(--text3);padding:8px;font-family:var(--font-mono)">// aucune alerte pour cette entite</div>';
  const listTop=document.getElementById("ov-top-list");
  if(listTop)listTop.innerHTML=top.map(projItem).join("")||'<div style="font-size:10px;color:var(--text3);padding:8px;font-family:var(--font-mono)">// aucun projet pour cette entite</div>';
}}

function filterDomainesByEntite(ent){{
  document.querySelectorAll(".dom-sec").forEach(s=>{{
    if(!ent){{s.style.display="";return;}}
    const dom=s.dataset.dom;
    const hasProj=DATA.projets.some(p=>p.domaine===dom&&_projetMatchEntite(p,ent));
    s.style.display=hasProj?"":"none";
  }});
}}

function filterCollabsByEntite(ent){{
  const filtered=ent?DATA.projets.filter(p=>_projetMatchEntite(p,ent)):DATA.projets;
  const resp=selCollab;
  const detail=filtered.filter(p=>p.responsable_principal===resp);
  const list=document.querySelector("#page-collabs .card .proj-list");
  if(list)list.innerHTML=detail.map(projItem).join("")||'<div style="font-size:10px;color:var(--text3);padding:8px;font-family:var(--font-mono)">// aucun projet pour cette entite</div>';
}}

function buildArchivageSection(){{
  const arch=DATA.archivage||[];
  if(!arch.length)return"";
  const MFR=["Jan","Fev","Mar","Avr","Mai","Jun","Jul","Aou","Sep","Oct","Nov","Dec"];
  return`<div class="card">
    <div class="card-title">projets archivés — 12 mois glissants (${{arch.length}})</div>
    <div class="proj-list">
      ${{arch.map(a=>{{
        const entites=_eclaterEntites(a.entite_concerne||"");
        let dateStr="";
        if(a.date_fin_prevue){{
          try{{
            const parts=a.date_fin_prevue.includes("/")?a.date_fin_prevue.split("/"):a.date_fin_prevue.split("-").reverse();
            const dt=new Date(parts[2],parts[1]-1,parts[0]);
            dateStr="clôt. "+dt.getDate()+" "+MFR[dt.getMonth()]+" "+dt.getFullYear();
          }}catch(e){{dateStr=a.date_fin_prevue;}}
        }}
        return`<div class="proj-item" onclick="openModalArchivage('${{esc(a.projet_id||a.ref_sujet)}}')">
          <span class="proj-dot" style="background:var(--violet)"></span>
          <span class="proj-name">${{esc(a.projet_nom||a.sujet||"")}}</span>
          <span class="badge bDONE">DONE</span>
          ${{entites.slice(0,2).map(e=>`<span style="font-size:9px;padding:1px 5px;border-radius:8px;background:var(--violet-dim);color:var(--violet);border:1px solid rgba(139,92,246,.2);font-family:var(--font-mono)">${{esc(e)}}</span>`).join("")}}
          <span class="proj-resp">${{dateStr}}</span>
        </div>`;
      }}).join("")}}
    </div>
  </div>`;
}}

function openModalArchivage(pid){{
  const a=(DATA.archivage||[]).find(x=>(x.projet_id||x.ref_sujet)===pid);
  if(!a)return;
  const entites=_eclaterEntites(a.entite_concerne||"");
  const collabsTemp=a.collaborateurs_temporaires?String(a.collaborateurs_temporaires).split(/[;,]/).map(c=>c.trim()).filter(Boolean):[];
  document.getElementById("modal-body").innerHTML=`
    <button class="modal-close" onclick="closeModal()">x</button>
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <span class="badge bDONE">ARCHIVÉ</span>
      ${{entites.map(e=>`<span style="font-size:9px;padding:2px 6px;border-radius:8px;background:var(--violet-dim);color:var(--violet);border:1px solid rgba(139,92,246,.2)">${{esc(e)}}</span>`).join("")}}
    </div>
    <div class="modal-title">${{esc(a.projet_nom||a.sujet||pid)}}</div>
    <div class="modal-id">${{esc(a.projet_id||a.ref_sujet||"")}}</div>
    <div class="modal-row">
      ${{a.domaine?`<span class="badge bON_HOLD">${{esc(a.domaine)}}</span>`:""}}
      ${{a.priorite?`<span class="badge bON_HOLD">prio:${{esc(a.priorite)}}</span>`:""}}
      ${{a.eta_projet?`<span class="badge bDONE">${{esc(a.eta_projet)}}</span>`:""}}
    </div>
    <div class="modal-sec"><div class="modal-stitle">informations projet</div>
      <div class="meta-grid">
        ${{[["responsable",a.responsable_principal],["date début",a.date_debut],["date fin prév.",a.date_fin_prevue],["budget j/sem",a.budget_jours],["effectifs",a.effectifs],["type",a.type]].filter(([,v])=>v&&v!=="undefined"&&v!=="nan").map(([k,v])=>`<div class="meta-item"><div class="meta-key">${{k}}</div><div class="meta-val">${{esc(v)}}</div></div>`).join("")}}
      </div>
    </div>
    ${{collabsTemp.length?`<div class="modal-sec"><div class="modal-stitle">collaborateurs temporaires</div>
      <div style="display:flex;gap:4px;flex-wrap:wrap">${{collabsTemp.map(c=>`<span style="font-size:10px;padding:2px 8px;border-radius:12px;background:var(--bg3);color:var(--text2);border:1px solid var(--border2)">${{esc(c)}}</span>`).join("")}}</div>
    </div>`:""}}
    ${{a.eta_intervention?`<div class="modal-sec"><div class="modal-stitle">période d'intervention</div><div class="modal-text">${{esc(a.eta_intervention)}}</div></div>`:""}}
    ${{a.description?`<div class="modal-sec"><div class="modal-stitle">description</div><div class="modal-text" style="color:var(--text3)">${{esc(a.description)}}</div></div>`:""}}
  `;
  document.getElementById("modal-overlay").classList.add("open");
}}


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 5 — buildGantt()
# Ajouter la variable selEntiteGantt et le filtre entité
#
# CHERCHER au début de buildGantt() :
#     const grp=document.getElementById("gg")?.value||"domaine";
#     const fst=document.getElementById("gf")?.value||"";
#     let P=DATA.projets.filter(p=>p.avancement_pct!=null);
#     if(fst)P=P.filter(p=>p.statut===fst);
#
# REMPLACER par :
# ═══════════════════════════════════════════════════════════════════════

  const grp=document.getElementById("gg")?.value||"domaine";
  const fst=document.getElementById("gf")?.value||"";
  let P=DATA.projets.filter(p=>p.avancement_pct!=null);
  if(fst)P=P.filter(p=>p.statut===fst);
  if(typeof selEntiteGantt!=="undefined"&&selEntiteGantt)
    P=P.filter(p=>_projetMatchEntite(p,selEntiteGantt));


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 6 — renderGantt()
# Ajouter le filtre entité dans les contrôles
# ET déclarer selEntiteGantt avant renderGantt
#
# CHERCHER :
#     let selCollab=null;
#
# AJOUTER APRÈS :
# ═══════════════════════════════════════════════════════════════════════

let selEntiteGantt="";


# Et dans renderGantt(), CHERCHER la ligne des contrôles :
#     el.innerHTML=`
#       <div class="gantt-controls">
#         <label>grouper :</label>
#
# AJOUTER dans la div gantt-controls, après les selects existants :

      ${{(DATA.entites||[]).length?`
      <label style="margin-left:8px">entité :</label>
      <span class="fchip${{!selEntiteGantt?" active":""}}" onclick="handleFiltreEntite('gantt',this,'')">Toutes</span>
      ${{(DATA.entites||[]).map(e=>`<span class="fchip${{selEntiteGantt===e?" active":""}}" onclick="handleFiltreEntite('gantt',this,'${{esc(e)}}')">${{esc(e)}}</span>`).join("")}}`:""}}


# ═══════════════════════════════════════════════════════════════════════
# RÉCAPITULATIF FINAL
# ═══════════════════════════════════════════════════════════════════════
"""
Ordre des modifications dans html_generator.py :

1. preparer_donnees()   → ajouter charger_archivage() + lister_entites() + "archivage" et "entites" dans le return
2. renderOverview()     → ajouter buildFiltreEntite("ov") + buildArchivageSection() + attachFiltreEntite()
3. renderDomaines()     → ajouter buildFiltreEntite("dom") en tête de html
4. Avant renderOverview → coller toutes les fonctions helpers (_eclaterEntites, _projetMatchEntite,
                          buildFiltreEntite, handleFiltreEntite, attachFiltreEntite,
                          filterOverviewByEntite, filterDomainesByEntite, filterCollabsByEntite,
                          buildArchivageSection, openModalArchivage)
5. buildGantt()         → ajouter filtre selEntiteGantt
6. renderGantt()        → ajouter chips entité dans les contrôles + déclarer selEntiteGantt=""

NOUVEAUTÉS dans les modals :
- openModalArchivage() : modal dédiée aux projets archivés avec collaborateurs_temporaires,
  eta_intervention, eta_projet affichés proprement
- Les projets archivés dans renderOverview sont cliquables → ouvre openModalArchivage()
"""
