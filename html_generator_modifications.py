"""
=======================================================================
MODIFICATIONS À APPORTER DANS html_generator.py
=======================================================================
Ce fichier liste exactement les 5 endroits à modifier/ajouter.
Chaque section indique QUOI chercher et QUOI remplacer/ajouter.
=======================================================================
"""

# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 1 — preparer_donnees()
# Ajouter le chargement de l'agenda et des snapshots Gantt 12 mois
#
# CHERCHER cette ligne (vers la fin de preparer_donnees) :
#     meta_list = meta.where(meta.notna(), None).to_dict(...)
#
# REMPLACER le return final par :
# ═══════════════════════════════════════════════════════════════════════

    meta_list = meta.where(meta.notna(), None).to_dict(orient="records") if not meta.empty else []

    # AGENDA — charger les événements
    agenda = sm.charger_agenda()
    agenda_list = agenda.where(agenda.notna(), None).to_dict(orient="records") if not agenda.empty else []

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
        "agenda":      agenda_list,   # ← NOUVEAU
    }


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 2 — Sidebar HTML
# Ajouter l'item "Calendrier" entre Évolutions et Chat LLM
#
# CHERCHER :
#     <div class="nav-item" data-page="chat"><span class="nav-icon">⌘</span>Chat LLM</div>
#
# REMPLACER PAR :
# ═══════════════════════════════════════════════════════════════════════

    <div class="nav-item" data-page="calendrier"><span class="nav-icon">▦</span>Calendrier<span class="nav-badge" id="nb-cal">—</span></div>
    <div class="nav-item" data-page="chat"><span class="nav-icon">⌘</span>Chat LLM</div>


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 3 — Contenu HTML pages
# Ajouter la page calendrier entre page-evolutions et page-chat
#
# CHERCHER :
#     <div class="page" id="page-chat">
#
# AJOUTER AVANT :
# ═══════════════════════════════════════════════════════════════════════

      <div class="page" id="page-calendrier"></div>


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 4 — Constante PAGES dans le JS
# Ajouter la page calendrier dans le dict de navigation
#
# CHERCHER :
#     const PAGES={{overview:"overview",...,chat:"chat_llm"}};
#
# REMPLACER PAR :
# ═══════════════════════════════════════════════════════════════════════

const PAGES={{overview:"overview",domaines:"par_domaine",collabs:"collaborateurs",gantt:"roadmap_gantt",evolutions:"evolutions",calendrier:"calendrier",chat:"chat_llm"}};


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 5 — Fonction init() dans le JS
# Initialiser le badge calendrier
#
# CHERCHER dans la fonction init() :
#     document.getElementById("nb-evol").textContent=(DATA.delta||[]).length;
#
# AJOUTER JUSTE APRÈS :
# ═══════════════════════════════════════════════════════════════════════

  const nbCal=document.getElementById("nb-cal");
  if(nbCal)nbCal.textContent=(DATA.agenda||[]).length;


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 6 — Remplacer renderGantt() et buildGantt() EN ENTIER
# Le nouveau Gantt est sur 12 mois glissants avec barres réelles META
#
# CHERCHER : function renderGantt(){{
# REMPLACER tout jusqu'à la fin de buildGantt() par le code ci-dessous
# ═══════════════════════════════════════════════════════════════════════

function renderGantt(){{
  const el=document.getElementById("page-gantt");
  if(el&&el.innerHTML.trim()!=="")return;
  el.innerHTML=`
    <div class="gantt-controls">
      <label>grouper :</label>
      <select id="gg" onchange="buildGantt()">
        <option value="domaine">Domaine</option>
        <option value="responsable_principal">Responsable</option>
        <option value="statut">Statut</option>
      </select>
      <label style="margin-left:8px">statut :</label>
      <select id="gf" onchange="buildGantt()">
        <option value="">Tous</option>
        <option value="ON_TRACK">ON_TRACK</option>
        <option value="AT_RISK">AT_RISK</option>
        <option value="LATE">LATE</option>
        <option value="DONE">DONE</option>
      </select>
    </div>
    <div class="card"><div id="gi"></div><div class="gantt-legend" id="gl"></div></div>`;
  buildGantt();
}}

function buildGantt(){{
  const grp=document.getElementById("gg")?.value||"domaine";
  const fst=document.getElementById("gf")?.value||"";
  let P=DATA.projets.filter(p=>p.avancement_pct!=null);
  if(fst)P=P.filter(p=>p.statut===fst);
  if(!P.length){{document.getElementById("gi").innerHTML='<div style="font-size:11px;color:var(--text3);padding:12px;font-family:var(--font-mono)">// aucun projet</div>';return;}}

  const now=new Date();
  const months=[];
  for(let i=-1;i<=10;i++)months.push(new Date(now.getFullYear(),now.getMonth()+i,1));
  const todayM=now.toISOString().slice(0,7);
  const MFR=["Jan","Fev","Mar","Avr","Mai","Jun","Jul","Aou","Sep","Oct","Nov","Dec"];

  const totalMs=new Date(months[months.length-1].getFullYear(),months[months.length-1].getMonth()+1,1)-months[0];
  function pctPos(d){{return Math.max(0,Math.min(100,(d-months[0])/totalMs*100));}}

  const groups={{}};
  P.forEach(p=>{{const k=p[grp]||"Autre";if(!groups[k])groups[k]=[];groups[k].push(p);}});
  const metaById={{}};(DATA.meta||[]).forEach(m=>{{metaById[m.projet_id||m.ref_sujet]=m;}});

  let html=`<div class="gantt-wrap"><table class="gantt-table"><thead><tr>
    <th class="g-label" style="font-family:var(--font-mono);color:var(--text3);font-size:9px">PROJET</th>
    ${{months.map(m=>{{
      const k=m.toISOString().slice(0,7);
      return`<th class="g-header${{k===todayM?" g-today-head":""}}">${{MFR[m.getMonth()]}}<br><span style="font-size:8px;opacity:.6">${{String(m.getFullYear()).slice(2)}}</span></th>`;
    }}).join("")}}
  </tr></thead><tbody>`;

  Object.entries(groups).sort().forEach(([g,items],gi)=>{{
    const gc=PALETTE[gi%PALETTE.length];
    html+=`<tr><td colspan="${{months.length+1}}" style="padding:7px 10px 2px;font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:.1em;color:var(--text3);background:var(--bg3);border-top:1px solid var(--border);font-family:var(--font-mono)">${{esc(g)}}</td></tr>`;

    items.forEach(p=>{{
      const m=metaById[pid(p)]||{{}};
      const col=SC[p.statut]||gc;
      const pv=pp(p);

      function parseDate(s){{
        if(!s)return null;
        const parts=s.split("/");
        if(parts.length===3)return new Date(parts[2],parts[1]-1,parts[0]);
        return new Date(s);
      }}

      const deb=parseDate(p.date_debut||m.date_debut);
      const fin=parseDate(p.date_fin_prevue||m.date_fin_prevue);
      const isOver=fin&&fin<now&&p.statut!=="DONE";
      const isSoon=fin&&fin>now&&(fin-now)<30*24*3600*1000;

      const todayPct=pctPos(now);

      html+=`<tr><td class="g-label" onclick="openModal('${{esc(pid(p))}}')" title="${{esc(nom(p))}}">${{esc(nom(p))}}</td>`;

      if(deb&&fin){{
        // Mode dates réelles depuis META
        const startPct=pctPos(deb);
        const endPct=pctPos(fin);
        const w=Math.max(endPct-startPct,0.8);
        months.forEach(month=>{{
          const isT=month.toISOString().slice(0,7)===todayM;
          const mEnd=new Date(month.getFullYear(),month.getMonth()+1,0);
          const nl=isT?`<div class="g-now" style="left:${{Math.round((now.getDate()-1)/mEnd.getDate()*100)}}%"></div>`:"";
          html+=`<td class="g-cell">${{nl}}</td>`;
        }});
        // On overlay la barre sur la première cellule via position absolue sur la ligne
        // Technique : on insère la barre dans une td relative
        html=html.replace(`</tr>`,
          `</tr>`);
        // Simplification : on affiche en mode pleine ligne avec position relative sur le tr
        html+=`<tr style="height:0"><td colspan="${{months.length+1}}" style="padding:0;position:relative;height:0">
          <div style="position:absolute;top:-20px;left:calc(150px + ${{startPct}}% * (100% - 150px) / 100);width:calc(${{w}}% * (100% - 150px) / 100);height:14px;border-radius:3px;background:${{col}};opacity:${{isOver?".4":"0.8"}};border:${{isOver?"1.5px dashed "+col:"none"}};${{isOver?"background:transparent;":""}}display:flex;align-items:center;padding:0 4px" title="${{esc(nom(p))}} :: ${{deb.toLocaleDateString("fr")}} → ${{fin.toLocaleDateString("fr")}}">
            ${{w>6?`<span style="font-size:8px;color:white;white-space:nowrap;overflow:hidden;font-family:var(--font-mono)">${{pv}}%${{isSoon?' !':""}}</span>`:""}}</div>
          ${{isSoon?`<div style="position:absolute;top:-13px;left:calc(150px + ${{endPct}}% * (100% - 150px) / 100);width:6px;height:6px;border-radius:50%;background:#f43f5e;transform:translateX(-50%)"></div>`:""}}</td></tr>`;
      }}else{{
        // Mode avancement si pas de dates META
        const ops=[0.15,0.3,0.55,0.8,0.55,0.3,0.15,0.08,0.05,0.03,0.02,0.01];
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
  document.getElementById("gl").innerHTML=
    `<span><i style="width:12px;height:1.5px;background:var(--red);display:inline-block"></i> aujourd'hui</span>`+
    `<span><i style="width:12px;height:8px;border:1.5px dashed #94a3b8;border-radius:2px;display:inline-block"></i> date depassee</span>`+
    `<span><i style="width:6px;height:6px;border-radius:50%;background:#f43f5e;display:inline-block"></i> echeance < 30j</span>`+
    Object.keys(groups).slice(0,6).map((g,i)=>`<span><i style="width:12px;height:5px;background:${{PALETTE[i%PALETTE.length]}};border-radius:2px;display:inline-block"></i>${{esc(g)}}</span>`).join("");
}}


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 7 — Ajouter la fonction renderCalendrier() dans le JS
# À ajouter après renderEvolutions() et avant openModal()
# ═══════════════════════════════════════════════════════════════════════

function renderCalendrier(){{
  const el=document.getElementById("page-calendrier");
  if(!el)return;
  const AGENDA=DATA.agenda||[];
  const TYPES_CAL={{
    REUNION:  {{label:"Reunion",   bg:"rgba(0,149,255,.12)",  border:"#0095ff",text:"#0095ff"}},
    LIVRAISON:{{label:"Livraison", bg:"rgba(16,217,148,.12)", border:"#10d994",text:"#10d994"}},
    ACTUALITE:{{label:"Actualite", bg:"rgba(245,158,11,.12)", border:"#f59e0b",text:"#f59e0b"}},
    JALON:    {{label:"Jalon",     bg:"rgba(139,92,246,.12)", border:"#8b5cf6",text:"#8b5cf6"}},
    AUTRE:    {{label:"Autre",     bg:"rgba(71,85,105,.12)",  border:"#475569",text:"#475569"}},
  }};
  const MFR=["Janvier","Fevrier","Mars","Avril","Mai","Juin","Juillet","Aout","Septembre","Octobre","Novembre","Decembre"];
  const now=new Date();
  let curY=now.getFullYear(),curM=now.getMonth();
  let activeTypes=new Set(Object.keys(TYPES_CAL));

  function evtsForDate(y,m,d){{
    const key=`${{y}}-${{String(m+1).padStart(2,"0")}}-${{String(d).padStart(2,"0")}}`;
    return AGENDA.filter(e=>e.date===key&&activeTypes.has(e.type));
  }}

  function buildCal(){{
    const todayStr=`${{now.getFullYear()}}-${{String(now.getMonth()+1).padStart(2,"0")}}-${{String(now.getDate()).padStart(2,"0")}}`;
    const first=new Date(curY,curM,1);
    const startDow=(first.getDay()+6)%7;
    const daysInMonth=new Date(curY,curM+1,0).getDate();
    const daysInPrev=new Date(curY,curM,0).getDate();

    // Upcoming events
    const upcoming=AGENDA.filter(e=>e.date>=todayStr&&activeTypes.has(e.type)).sort((a,b)=>a.date.localeCompare(b.date)).slice(0,6);

    let html=`
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
        <button onclick="calNav(-1)" style="font-size:14px;padding:4px 12px;background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);color:var(--text);cursor:pointer">&#8249;</button>
        <span style="flex:1;text-align:center;font-size:13px;font-weight:600;font-family:var(--font-mono);color:var(--text)">${{MFR[curM]}} ${{curY}}</span>
        <button onclick="calNav(1)" style="font-size:14px;padding:4px 12px;background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);color:var(--text);cursor:pointer">&#8250;</button>
      </div>
      <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px" id="cal-type-filters">
        ${{Object.entries(TYPES_CAL).map(([k,v])=>`<span class="fchip${{activeTypes.has(k)?" active":""}}" style="${{activeTypes.has(k)?"color:"+v.text+";border-color:"+v.border+";background:"+v.bg:""}}" onclick="calToggleType('${{k}}')" data-t="${{k}}"><span style="width:6px;height:6px;border-radius:50%;background:${{v.border}};display:inline-block;margin-right:4px"></span>${{v.label}}</span>`).join("")}}
      </div>
      <div style="display:grid;grid-template-columns:1fr 260px;gap:12px">
        <div class="card" style="padding:10px">
          <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--border);border-radius:6px;overflow:hidden">
            ${{["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"].map(d=>`<div style="background:var(--bg3);padding:5px 4px;text-align:center;font-size:9px;font-weight:600;color:var(--text3);font-family:var(--font-mono)">${{d}}</div>`).join("")}}`;

    // Cellules jours
    for(let i=0;i<startDow;i++){{
      const d=daysInPrev-startDow+1+i;
      html+=`<div style="background:var(--bg2);min-height:72px;padding:5px;opacity:.3"><div style="font-size:10px;color:var(--text3)">${{d}}</div></div>`;
    }}
    for(let d=1;d<=daysInMonth;d++){{
      const isToday=d===now.getDate()&&curM===now.getMonth()&&curY===now.getFullYear();
      const evts=evtsForDate(curY,curM,d);
      const show=evts.slice(0,2);const more=evts.length-2;
      html+=`<div style="background:${{isToday?"rgba(0,212,255,.06)":"var(--bg2)"}};min-height:72px;padding:5px;border:${{isToday?"1px solid rgba(0,212,255,.3)":"none"}}">
        <div style="font-size:10px;font-weight:600;color:${{isToday?"var(--cyan)":"var(--text3)"}};font-family:var(--font-mono);margin-bottom:3px">${{isToday?`<span style="background:var(--cyan);color:var(--bg);border-radius:50%;width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;font-size:9px">${{d}}</span>`:d}}</div>
        ${{show.map(e=>{{const t=TYPES_CAL[e.type]||TYPES_CAL.AUTRE;return`<div style="font-size:9px;padding:2px 4px;border-radius:2px;margin-bottom:1px;background:${{t.bg}};border-left:2px solid ${{t.border}};color:${{t.text}};overflow:hidden;text-overflow:ellipsis;white-space:nowrap;cursor:default" title="${{esc(e.titre)}}${{e.description?" — "+e.description:""}}">${{esc(e.titre)}}</div>`;}}}).join("")}}
        ${{more>0?`<div style="font-size:8px;color:var(--text3);font-family:var(--font-mono)">+${{more}}</div>`:""}}</div>`;
    }}
    const total=startDow+daysInMonth;const rem=(7-total%7)%7;
    for(let i=1;i<=rem;i++){{
      html+=`<div style="background:var(--bg2);min-height:72px;padding:5px;opacity:.3"><div style="font-size:10px;color:var(--text3)">${{i}}</div></div>`;
    }}

    html+=`</div></div>
        <div>
          <div class="card" style="margin-bottom:10px">
            <div class="card-title">prochains evenements</div>
            ${{upcoming.length?upcoming.map(e=>{{
              const dt=new Date(e.date);const t=TYPES_CAL[e.type]||TYPES_CAL.AUTRE;
              return`<div style="display:flex;gap:8px;padding:7px 0;border-bottom:1px solid var(--border);align-items:flex-start">
                <div style="min-width:34px;text-align:center;background:var(--bg3);border-radius:6px;padding:3px 0">
                  <div style="font-size:13px;font-weight:600;color:var(--text);font-family:var(--font-mono);line-height:1">${{dt.getDate()}}</div>
                  <div style="font-size:8px;color:var(--text3);text-transform:uppercase">${{MFR[dt.getMonth()].slice(0,3)}}</div>
                </div>
                <div style="flex:1;min-width:0">
                  <div style="font-size:11px;font-weight:600;color:var(--text);overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${{esc(e.titre)}}</div>
                  <div style="display:flex;align-items:center;gap:4px;margin-top:2px">
                    <span style="width:5px;height:5px;border-radius:50%;background:${{t.border}};flex-shrink:0"></span>
                    <span style="font-size:9px;color:var(--text3);font-family:var(--font-mono)">${{t.label}}${{e.projet_ref?" · "+e.projet_ref:""}}</span>
                  </div>
                  ${{e.description?`<div style="font-size:9px;color:var(--text3);margin-top:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-style:italic">${{esc(e.description)}}</div>`:""}}</div>
              </div>`;
            }}).join(""):`<div style="font-size:11px;color:var(--text3);padding:8px 0;font-family:var(--font-mono)">// aucun evenement</div>`}}
          </div>
          <div class="card">
            <div class="card-title">legende</div>
            ${{Object.entries(TYPES_CAL).map(([,v])=>`<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;font-size:10px;color:var(--text2)"><span style="width:8px;height:8px;border-radius:50%;background:${{v.border}}"></span>${{v.label}}</div>`).join("")}}
          </div>
        </div>
      </div>`;

    el.innerHTML=html;
  }}

  window.calNav=function(dir){{curM+=dir;if(curM>11){{curM=0;curY++;}}if(curM<0){{curM=11;curY--;}}buildCal();}};
  window.calToggleType=function(t){{
    if(activeTypes.has(t)){{if(activeTypes.size>1)activeTypes.delete(t);}}
    else activeTypes.add(t);
    // Re-render filters + calendar
    document.querySelectorAll("#cal-type-filters .fchip").forEach(c=>{{
      const tt=c.dataset.t;const v=TYPES_CAL[tt];
      c.className="fchip"+(activeTypes.has(tt)?" active":"");
      c.style.cssText=activeTypes.has(tt)?"color:"+v.text+";border-color:"+v.border+";background:"+v.bg:"";
    }});
    buildCal();
  }};

  buildCal();
}}
