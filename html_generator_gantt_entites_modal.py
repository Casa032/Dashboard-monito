"""
=======================================================================
MODIFICATIONS html_generator.py
3 sujets : Gantt scrollable · Barres entités · Modal description
=======================================================================
Toutes les modifications sont dans html_generator.py uniquement.
Aucun fichier Python à changer.
=======================================================================
"""


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 1 — _calculer_snapshot()
# Ajouter par_entite dans le snapshot
#
# CHERCHER dans _calculer_snapshot() :
#     par_domaine, par_resp = {}, {}
#     for p in projets:
#         d = p.get("domaine") or "Autre"
#         ...
#         par_resp.setdefault(r, ...)
#         ...
#         if dom and dom not in par_resp[r]["domaines"]:
#             par_resp[r]["domaines"].append(dom)
#     return {
#
# REMPLACER le bloc par :
# ═══════════════════════════════════════════════════════════════════════

    par_domaine, par_resp, par_entite = {}, {}, {}
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
        # NOUVEAU — entités (multi-valeurs)
        import re as _re
        entite_raw = p.get("entite_concerne") or ""
        entite_list = [e.strip() for e in _re.split(r"[;,]", str(entite_raw)) if e.strip()] if entite_raw else []
        for ent in (entite_list or ["Non assigné"]):
            par_entite.setdefault(ent, {"total":0,"on_track":0,"at_risk":0,"late":0,"done":0})
            par_entite[ent]["total"] += 1
            for k2 in ["on_track","at_risk","late","done"]:
                if s == k2.upper(): par_entite[ent][k2] += 1

    return {
        "projets": projets, "kpis": kpis, "par_domaine": par_domaine,
        "par_resp": par_resp, "par_entite": par_entite,
        "domaines": sorted(set(p.get("domaine") or "" for p in projets if p.get("domaine"))),
        "q_prev": q_prev, "delta": delta,
    }


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 2 — preparer_donnees() return
# Ajouter par_entite dans le return et dans switchQuinzaine
#
# CHERCHER dans le return de preparer_donnees() :
#     "par_resp":    snap["par_resp"],
#
# AJOUTER APRÈS :
# ═══════════════════════════════════════════════════════════════════════

        "par_entite":  snap["par_entite"],


# Et dans switchQuinzaine() JS, CHERCHER :
#     DATA.par_resp=snap.par_resp;
# AJOUTER APRÈS :

  DATA.par_entite=snap.par_entite;


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 3 — renderOverview()
# Remplacer filtre entité par barres entité dans la grille
#
# CHERCHER dans renderOverview() le innerHTML complet et REMPLACER
# la ligne buildFiltreEntite("ov") par rien (supprimer)
# et la grille grid2 par une grille à 3 colonnes :
# ═══════════════════════════════════════════════════════════════════════

    // Remplacer la grid2 existante par :
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:12px">
      <div class="card"><div class="card-title">par domaine</div>
        <div class="bar-rows">${{Object.entries(DATA.par_domaine).sort((a,b)=>b[1].total-a[1].total).map(([d,s])=>`
          <div class="bar-row">
            <span class="bar-label" title="${{esc(d)}}">${{esc(d)}}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxD*100)}}%;background:${{domColor(d)}}"></div></div>
            <span class="bar-count">${{s.total}}</span>
          </div>`).join("")}}</div>
      </div>
      <div class="card"><div class="card-title">par responsable</div>
        <div class="bar-rows">${{Object.entries(DATA.par_resp).sort((a,b)=>b[1].total-a[1].total).map(([r,s])=>`
          <div class="bar-row">
            <span class="bar-label" title="${{esc(r)}}">${{esc(r)}}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/maxR*100)}}%;background:#00d4ff"></div></div>
            <span class="bar-count">${{s.total}}</span>
          </div>`).join("")}}</div>
      </div>
      <div class="card"><div class="card-title">par entité</div>
        <div class="bar-rows">${{Object.entries(DATA.par_entite||{{}}).sort((a,b)=>b[1].total-a[1].total).map(([e,s])=>`
          <div class="bar-row">
            <span class="bar-label" title="${{esc(e)}}">${{esc(e)}}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${{Math.round(s.total/Math.max(...Object.values(DATA.par_entite).map(x=>x.total),1)*100)}}%;background:var(--violet)"></div></div>
            <span class="bar-count">${{s.total}}</span>
          </div>`).join("")}}</div>
      </div>
    </div>


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 4 — openModal()
# Corriger la description en double
#
# CHERCHER dans openModal() la ligne qui affiche description :
#     ${{m.description?`<div class="modal-sec">...
#
# REMPLACER par (une seule source, priorité META) :
# ═══════════════════════════════════════════════════════════════════════

    // Calcul de la description unique — priorité META, fallback quinzaine
    const descUnique = m.description && m.description !== "nan"
      ? m.description
      : (p.description && p.description !== "nan" ? p.description : "");

    // Puis dans le HTML de la modal, remplacer les deux occurrences par :
    ${{descUnique?`<div class="modal-sec"><div class="modal-stitle">description</div>
      <div class="modal-text" style="color:var(--text3)">${{esc(descUnique)}}</div></div>`:""}}


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 5 — CSS à ajouter dans CSS (variable CSS)
# Styles pour le Gantt scrollable SVG
#
# CHERCHER dans CSS :
#     .gantt-legend span{...}
#
# AJOUTER APRÈS :
# ═══════════════════════════════════════════════════════════════════════

.gantt-scroll-wrap{{overflow-x:auto;cursor:grab;user-select:none;position:relative;}}
.gantt-scroll-wrap:active{{cursor:grabbing;}}
.gantt-svg-container{{position:relative;}}
.gantt-toolbar{{display:flex;gap:6px;align-items:center;margin-bottom:10px;flex-wrap:wrap;}}
.gantt-toolbar select{{font-size:11px;padding:4px 8px;border:1px solid var(--border2);
  border-radius:var(--radius);background:var(--bg3);color:var(--text);cursor:pointer;
  font-family:var(--font-mono);}}
.granularity-btn{{font-size:10px;padding:3px 10px;border-radius:20px;
  border:1px solid var(--border2);color:var(--text2);cursor:pointer;
  background:var(--bg2);font-family:var(--font-mono);transition:all .12s;}}
.granularity-btn.active{{background:var(--cyan-dim);color:var(--cyan);border-color:var(--cyan);}}
.gantt-nav-btn{{font-size:13px;padding:3px 12px;background:var(--bg2);
  border:1px solid var(--border2);border-radius:var(--radius);
  color:var(--text);cursor:pointer;font-family:var(--font-mono);transition:all .12s;}}
.gantt-nav-btn:hover{{border-color:var(--cyan);color:var(--cyan);}}


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 6 — renderGantt() et buildGantt()
# REMPLACER ENTIÈREMENT les deux fonctions par le code ci-dessous
# ═══════════════════════════════════════════════════════════════════════

GANTT_JS = """
// ── Variables état Gantt ───────────────────────────────────────────────
let ganttGranularity = "month";   // "week" | "month" | "quarter"
let ganttOffsetPx    = 0;         // décalage scroll courant en px
let ganttFiltreStatut = "";
let ganttFiltreEntite = "";
let ganttIsDragging  = false;
let ganttDragStartX  = 0;
let ganttDragStartOffset = 0;

// Largeur d'une unité selon la granularité
const GANTT_UNIT_W = {{ week:40, month:80, quarter:180 }};
// Nombre d'unités passées / futures visibles au démarrage
const GANTT_PAST   = {{ week:8,  month:3,  quarter:2   }};
const GANTT_FUTURE = {{ week:24, month:9,  quarter:6   }};

function renderGantt(){{
  const el = document.getElementById("page-gantt");
  if(!el) return;
  el.innerHTML = `
    <div class="gantt-toolbar">
      <button class="gantt-nav-btn" onclick="ganttNav(-3)">&#8249;&#8249;</button>
      <button class="gantt-nav-btn" onclick="ganttNav(-1)">&#8249;</button>
      <button class="gantt-nav-btn" onclick="ganttGoToday()">Aujourd'hui</button>
      <button class="gantt-nav-btn" onclick="ganttNav(1)">&#8250;</button>
      <button class="gantt-nav-btn" onclick="ganttNav(3)">&#8250;&#8250;</button>
      <div style="flex:1"></div>
      <span style="font-size:9px;color:var(--text3);font-family:var(--font-mono)">granularité :</span>
      <button class="granularity-btn active" id="gbtn-week"    onclick="setGranularity('week')">Semaine</button>
      <button class="granularity-btn"        id="gbtn-month"   onclick="setGranularity('month')">Mois</button>
      <button class="granularity-btn"        id="gbtn-quarter" onclick="setGranularity('quarter')">Trimestre</button>
      <span style="font-size:9px;color:var(--text3);font-family:var(--font-mono);margin-left:8px">statut :</span>
      <select id="gf" onchange="ganttFiltreStatut=this.value;buildGantt()">
        <option value="">Tous</option>
        <option value="ON_TRACK">ON_TRACK</option>
        <option value="AT_RISK">AT_RISK</option>
        <option value="LATE">LATE</option>
        <option value="DONE">DONE</option>
      </select>
      ${{(DATA.entites||[]).length?`
      <span style="font-size:9px;color:var(--text3);font-family:var(--font-mono)">entité :</span>
      <select id="ge" onchange="ganttFiltreEntite=this.value;buildGantt()">
        <option value="">Toutes</option>
        ${{(DATA.entites||[]).map(e=>`<option value="${{esc(e)}}">${{esc(e)}}</option>`).join("")}}
      </select>`:""}}
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      <div id="gantt-scroll-area" class="gantt-scroll-wrap">
        <div id="gantt-inner"></div>
      </div>
    </div>
    <div class="gantt-legend" id="gl"></div>`;

  // Démarrer en vue mois par défaut
  ganttGranularity = "month";
  ganttOffsetPx    = 0;
  _attachGanttScroll();
  buildGantt();
}}

function setGranularity(g){{
  ganttGranularity = g;
  ganttOffsetPx    = 0;
  document.querySelectorAll(".granularity-btn").forEach(b=>b.classList.remove("active"));
  document.getElementById("gbtn-"+g)?.classList.add("active");
  buildGantt();
}}

function ganttNav(n){{
  const uw = GANTT_UNIT_W[ganttGranularity]||80;
  ganttOffsetPx -= n * uw * 2;
  buildGantt();
}}

function ganttGoToday(){{
  ganttOffsetPx = 0;
  buildGantt();
}}

function _attachGanttScroll(){{
  const wrap = document.getElementById("gantt-scroll-area");
  if(!wrap) return;

  // Drag scroll souris
  wrap.addEventListener("mousedown", e=>{{
    ganttIsDragging   = true;
    ganttDragStartX   = e.clientX;
    ganttDragStartOffset = ganttOffsetPx;
    e.preventDefault();
  }});
  window.addEventListener("mousemove", e=>{{
    if(!ganttIsDragging) return;
    ganttOffsetPx = ganttDragStartOffset + (e.clientX - ganttDragStartX);
    buildGantt();
  }});
  window.addEventListener("mouseup", ()=>{{ ganttIsDragging = false; }});

  // Scroll molette horizontal
  wrap.addEventListener("wheel", e=>{{
    e.preventDefault();
    ganttOffsetPx -= e.deltaX || e.deltaY;
    buildGantt();
  }}, {{ passive:false }});

  // Touch mobile
  let touchStartX = 0;
  wrap.addEventListener("touchstart", e=>{{ touchStartX = e.touches[0].clientX; }}, {{passive:true}});
  wrap.addEventListener("touchmove", e=>{{
    const dx = e.touches[0].clientX - touchStartX;
    ganttOffsetPx += dx;
    touchStartX = e.touches[0].clientX;
    buildGantt();
  }}, {{passive:true}});
}}

function buildGantt(){{
  const inner = document.getElementById("gantt-inner");
  if(!inner) return;

  const uw    = GANTT_UNIT_W[ganttGranularity] || 80;
  const past  = GANTT_PAST[ganttGranularity]   || 3;
  const fut   = GANTT_FUTURE[ganttGranularity] || 9;
  const now   = new Date();
  const ROW_H = 28;
  const HDR_H = 48;
  const LBL_W = 170;
  const MFR   = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"];
  const TRIM  = ["T1","T2","T3","T4"];

  // ── Générer les unités temporelles ──────────────────────────────────
  function startOfWeek(d){{
    const r=new Date(d);r.setDate(r.getDate()-(r.getDay()||7)+1);
    r.setHours(0,0,0,0);return r;
  }}

  let units = [];  // {{ label, start, end }}
  if(ganttGranularity === "week"){{
    const origin = startOfWeek(now);
    for(let i=-past*4; i<=fut*4; i++){{
      const s = new Date(origin); s.setDate(s.getDate()+i*7);
      const e = new Date(s); e.setDate(e.getDate()+6);
      units.push({{ label: s.getDate()+"/"+MFR[s.getMonth()], start:new Date(s), end:new Date(e) }});
    }}
  }} else if(ganttGranularity === "month"){{
    for(let i=-past; i<=fut; i++){{
      const s = new Date(now.getFullYear(), now.getMonth()+i, 1);
      const e = new Date(now.getFullYear(), now.getMonth()+i+1, 0);
      units.push({{ label: MFR[s.getMonth()]+"'"+String(s.getFullYear()).slice(2), start:new Date(s), end:new Date(e) }});
    }}
  }} else {{
    for(let i=-past; i<=fut; i++){{
      const qBase = Math.floor(now.getMonth()/3);
      const qOff  = qBase + i;
      const yr    = now.getFullYear() + Math.floor(qOff/4);
      const qIdx  = ((qOff%4)+4)%4;
      const s     = new Date(yr, qIdx*3, 1);
      const e     = new Date(yr, qIdx*3+3, 0);
      units.push({{ label: TRIM[qIdx]+" "+yr, start:new Date(s), end:new Date(e) }});
    }}
  }}

  const totalUnits = units.length;
  const svgW       = LBL_W + totalUnits * uw;

  // ── Position pixel d'une date ────────────────────────────────────────
  const rangeStart = units[0].start;
  const rangeEnd   = units[units.length-1].end;
  const rangeMs    = rangeEnd - rangeStart;
  function xPos(d){{
    return LBL_W + Math.max(0, Math.min(1,(d-rangeStart)/rangeMs)) * (totalUnits*uw);
  }}

  // ── Position "aujourd'hui" ───────────────────────────────────────────
  const todayX = xPos(now);

  // ── Filtrer projets avec dates valides ───────────────────────────────
  const metaById={{}};
  (DATA.meta||[]).forEach(m=>{{ metaById[m.projet_id||m.ref_sujet]=m; }});

  function parseDate(s){{
    if(!s||String(s).trim()===""||String(s)==="nan")return null;
    const v=String(s).trim();
    const parts=v.includes("/")?v.split("/"):null;
    if(parts&&parts.length===3)return new Date(parts[2],parts[1]-1,parts[0]);
    try{{return new Date(v);}}catch(e){{return null;}}
  }}

  let projets = DATA.projets.filter(p=>{{
    if(ganttFiltreStatut&&p.statut!==ganttFiltreStatut) return false;
    if(ganttFiltreEntite){{
      const ents=(p.entite_concerne||"").split(/[;,]/).map(e=>e.trim());
      if(!ents.includes(ganttFiltreEntite)) return false;
    }}
    const m = metaById[p.projet_id||p.ref_sujet]||{{}};
    const deb = parseDate(p.date_debut||m.date_debut);
    const fin = parseDate(p.date_fin_prevue||m.date_fin_prevue);
    return deb&&fin; // masquer sans dates
  }});

  // ── Grouper ──────────────────────────────────────────────────────────
  const groups={{}};
  projets.forEach(p=>{{
    const k=p.domaine||"Autre";
    if(!groups[k])groups[k]=[];
    groups[k].push(p);
  }});

  // ── Calcul hauteur totale SVG ────────────────────────────────────────
  let totalRows = 0;
  Object.values(groups).forEach(items=>{{ totalRows += 1 + items.length; }});
  const svgH = HDR_H + totalRows * ROW_H + 20;

  // ── Construction SVG ─────────────────────────────────────────────────
  let svg = `<svg xmlns="http://www.w3.org/2000/svg"
    width="${{svgW + Math.abs(ganttOffsetPx)}}" height="${{svgH}}"
    style="display:block;transform:translateX(${{ganttOffsetPx}}px);transition:transform .05s linear">`;

  // Fond et grille verticale
  svg += `<rect width="100%" height="100%" fill="var(--bg2)"/>`;

  // En-têtes unités
  units.forEach((u,i)=>{{
    const x = LBL_W + i*uw;
    const isNow = u.start <= now && now <= u.end;
    svg += `<rect x="${{x}}" y="0" width="${{uw}}" height="${{HDR_H}}"
      fill="${{isNow?"rgba(0,212,255,.06)":"var(--bg3)"}}"
      stroke="var(--border)" stroke-width="0.5"/>`;
    svg += `<text x="${{x+uw/2}}" y="${{HDR_H/2+4}}" text-anchor="middle"
      font-size="10" fill="${{isNow?"var(--cyan)":"var(--text3)"}}"
      font-family="var(--font-mono)" font-weight="${{isNow?"600":"400"}}">${{u.label}}</text>`;
    // Ligne verticale grille
    svg += `<line x1="${{x}}" y1="${{HDR_H}}" x2="${{x}}" y2="${{svgH}}"
      stroke="var(--border)" stroke-width="0.5" opacity="0.5"/>`;
  }});

  // Ligne fixe label col
  svg += `<rect x="0" y="0" width="${{LBL_W}}" height="${{svgH}}"
    fill="var(--bg2)" stroke="var(--border)" stroke-width="0.5"/>`;
  svg += `<text x="10" y="${{HDR_H/2+4}}" font-size="9" fill="var(--text3)"
    font-family="var(--font-mono)">PROJET</text>`;

  // Lignes projets
  let rowIdx = 0;
  Object.entries(groups).sort().forEach(([grp,items],gi)=>{{
    const gc = PALETTE[gi%PALETTE.length];
    const gy = HDR_H + rowIdx * ROW_H;

    // En-tête groupe
    svg += `<rect x="0" y="${{gy}}" width="${{svgW}}" height="${{ROW_H}}"
      fill="var(--bg3)" stroke="var(--border)" stroke-width="0.3"/>`;
    svg += `<text x="10" y="${{gy+ROW_H/2+4}}" font-size="9" font-weight="600"
      fill="${{gc}}" font-family="var(--font-mono)" letter-spacing="0.08em"
      text-transform="uppercase">${{grp.toUpperCase()}}</text>`;
    rowIdx++;

    items.forEach(p=>{{
      const ry  = HDR_H + rowIdx * ROW_H;
      const col = SC[p.statut]||gc;
      const m   = metaById[p.projet_id||p.ref_sujet]||{{}};
      const deb = parseDate(p.date_debut||m.date_debut);
      const fin = parseDate(p.date_fin_prevue||m.date_fin_prevue);
      const pv  = p.avancement_pct||0;
      const isOver  = fin < now && p.statut!=="DONE";
      const isSoon  = fin > now && (fin-now)<30*24*3600*1000;
      const x1  = xPos(deb);
      const x2  = Math.max(xPos(fin), x1+4);
      const bw  = x2-x1;

      // Fond ligne alternée
      svg += `<rect x="0" y="${{ry}}" width="${{svgW}}" height="${{ROW_H}}"
        fill="${{rowIdx%2===0?"rgba(255,255,255,.01)":"transparent"}}"
        stroke="var(--border)" stroke-width="0.3"/>`;

      // Label projet
      const nomTronc = (nom(p)||"").slice(0,22)+(nom(p).length>22?"…":"");
      svg += `<text x="8" y="${{ry+ROW_H/2+4}}" font-size="10"
        fill="var(--text2)" font-family="var(--font-mono)"
        style="cursor:pointer" onclick="openModal('${{p.projet_id||p.ref_sujet}}')">${{esc(nomTronc)}}</text>`;

      // Barre projet
      if(bw>0){{
        if(isOver){{
          // Barre pointillée pour projets dépassés
          svg += `<rect x="${{x1}}" y="${{ry+6}}" width="${{bw}}" height="${{ROW_H-14}}"
            fill="none" stroke="${{col}}" stroke-width="1.5"
            stroke-dasharray="4,3" rx="3" opacity="0.6"/>`;
        }} else {{
          // Barre pleine
          svg += `<rect x="${{x1}}" y="${{ry+6}}" width="${{bw}}" height="${{ROW_H-14}}"
            fill="${{col}}" rx="3" opacity="0.8"/>`;
          // Barre progression interne
          if(pv>0&&pv<100){{
            svg += `<rect x="${{x1}}" y="${{ry+6}}" width="${{bw*pv/100}}" height="${{ROW_H-14}}"
              fill="${{col}}" rx="3" opacity="0.4"/>`;
          }}
          // Label pourcentage si assez large
          if(bw>30){{
            svg += `<text x="${{x1+bw/2}}" y="${{ry+ROW_H/2+4}}" text-anchor="middle"
              font-size="9" fill="white" font-family="var(--font-mono)"
              pointer-events="none">${{pv}}%</text>`;
          }}
        }}
        // Point rouge échéance proche
        if(isSoon){{
          svg += `<circle cx="${{x2}}" cy="${{ry+ROW_H/2}}" r="4"
            fill="#f43f5e" stroke="var(--bg2)" stroke-width="1.5"/>`;
        }}
      }}
      rowIdx++;
    }});
  }});

  // Ligne aujourd'hui — par-dessus tout
  svg += `<line x1="${{todayX}}" y1="0" x2="${{todayX}}" y2="${{svgH}}"
    stroke="#f43f5e" stroke-width="1.5" opacity="0.7" stroke-dasharray="4,3"/>`;
  svg += `<text x="${{todayX+4}}" y="12" font-size="8" fill="#f43f5e"
    font-family="var(--font-mono)">auj.</text>`;

  svg += `</svg>`;

  inner.innerHTML = svg;

  // Légende
  const gl = document.getElementById("gl");
  if(gl){{
    gl.innerHTML =
      `<span><i style="width:12px;height:1.5px;background:#f43f5e;display:inline-block"></i> aujourd'hui</span>`+
      `<span><i style="width:12px;height:8px;border:1.5px dashed #94a3b8;border-radius:2px;display:inline-block"></i> date dépassée</span>`+
      `<span><i style="width:6px;height:6px;border-radius:50%;background:#f43f5e;display:inline-block"></i> échéance &lt;30j</span>`+
      `<span style="color:var(--text3);font-family:var(--font-mono);font-size:9px">
        ← glisser pour naviguer · molette pour scroller →
      </span>`;
  }}
}}
"""
