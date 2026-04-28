"""
À COLLER dans html_generator.py
APRÈS renderEvolutions() et AVANT openModal()

Remplace toute l'ancienne renderCalendrier() si tu l'as déjà,
sinon colle directement à cet endroit.
"""

# ── SECTION À COLLER ──────────────────────────────────────────────────────────
# Dans la f-string HTML (entre les guillemets triples), colle ce bloc JS.
# Cherche : "function openModal(id){{"
# Colle AVANT cette ligne.
# ─────────────────────────────────────────────────────────────────────────────

RENDERALENDRIER = """
function renderCalendrier(){{
  const el=document.getElementById("page-calendrier");
  if(!el)return;
  const AGENDA=DATA.agenda||[];
  const TYPES_CAL={{
    REUNION:  {{label:"Réunion",   bg:"rgba(0,149,255,.12)",  border:"#0095ff",text:"#0095ff"}},
    LIVRAISON:{{label:"Livraison", bg:"rgba(16,217,148,.12)", border:"#10d994",text:"#10d994"}},
    ACTUALITE:{{label:"Actualité", bg:"rgba(245,158,11,.12)", border:"#f59e0b",text:"#f59e0b"}},
    JALON:    {{label:"Jalon",     bg:"rgba(139,92,246,.12)", border:"#8b5cf6",text:"#8b5cf6"}},
    AUTRE:    {{label:"Autre",     bg:"rgba(71,85,105,.12)",  border:"#475569",text:"#475569"}},
  }};
  const MFR=["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"];
  const now=new Date();
  let curY=now.getFullYear(),curM=now.getMonth();
  let activeTypes=new Set(Object.keys(TYPES_CAL));

  function evtsForDate(y,m,d){{
    const key=`${{y}}-${{String(m+1).padStart(2,"0")}}-${{String(d).padStart(2,"0")}}`;
    return AGENDA.filter(e=>e.date===key&&activeTypes.has(e.type));
  }}

  function openEvt(idx){{
    const e=AGENDA[idx];if(!e)return;
    const t=TYPES_CAL[e.type]||TYPES_CAL.AUTRE;
    const dt=new Date(e.date);
    const dateStr=dt.toLocaleDateString("fr-FR",{{weekday:"long",day:"numeric",month:"long",year:"numeric"}});
    // Chercher projet lié
    const projLie=e.projet_ref?(DATA.projets.find(p=>(p.projet_id||p.ref_sujet)===e.projet_ref)||null):null;

    document.getElementById("modal-body").innerHTML=`
      <button class="modal-close" onclick="closeModal()">x</button>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
        <div style="width:10px;height:10px;border-radius:50%;background:${{t.border}};flex-shrink:0"></div>
        <span class="badge" style="background:${{t.bg}};color:${{t.text}};border:1px solid ${{t.border}};font-family:var(--font-mono);font-size:9px">${{t.label}}</span>
      </div>
      <div class="modal-title">${{esc(e.titre)}}</div>
      <div class="modal-id" style="color:var(--text3)">${{dateStr}}</div>
      ${{e.description?`<div class="modal-sec"><div class="modal-stitle">description</div>
        <div class="modal-text">${{esc(e.description)}}</div></div>`:""}}
      ${{projLie?`<div class="modal-sec"><div class="modal-stitle">projet lié</div>
        <div class="proj-item" onclick="closeModal();openModal('${{esc(projLie.projet_id||projLie.ref_sujet)}}')" style="cursor:pointer">
          <span class="proj-dot" style="background:${{SC[projLie.statut]||"#475569"}}"></span>
          <span class="proj-name">${{esc(projLie.projet_nom||projLie.sujet||"")}}</span>
          ${{badge(projLie.statut)}}
          <span class="proj-pct">${{projLie.avancement_pct||0}}%</span>
        </div></div>`:
        e.projet_ref?`<div class="modal-sec"><div class="modal-stitle">projet lié</div>
          <div class="modal-text" style="color:var(--text3);font-family:var(--font-mono)">${{esc(e.projet_ref)}}</div></div>`:""}}
    `;
    document.getElementById("modal-overlay").classList.add("open");
  }}

  function buildCal(){{
    const todayStr=`${{now.getFullYear()}}-${{String(now.getMonth()+1).padStart(2,"0")}}-${{String(now.getDate()).padStart(2,"0")}}`;
    const first=new Date(curY,curM,1);
    const startDow=(first.getDay()+6)%7;
    const daysInMonth=new Date(curY,curM+1,0).getDate();
    const daysInPrev=new Date(curY,curM,0).getDate();
    const upcoming=AGENDA.filter(e=>e.date>=todayStr&&activeTypes.has(e.type))
      .sort((a,b)=>a.date.localeCompare(b.date)).slice(0,6);

    let html=`
      <div style="display:flex;align-items:center;gap:12px;margin-bottom:14px">
        <button onclick="calNav(-1)" style="font-size:14px;padding:4px 14px;background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);color:var(--text);cursor:pointer;font-family:var(--font-mono)">&#8249;</button>
        <span style="flex:1;text-align:center;font-size:14px;font-weight:600;font-family:var(--font-mono);color:var(--text)">${{MFR[curM]}} ${{curY}}</span>
        <button onclick="calNav(1)" style="font-size:14px;padding:4px 14px;background:var(--bg2);border:1px solid var(--border2);border-radius:var(--radius);color:var(--text);cursor:pointer;font-family:var(--font-mono)">&#8250;</button>
      </div>
      <div style="display:flex;gap:5px;flex-wrap:wrap;margin-bottom:12px" id="cal-type-filters">
        ${{Object.entries(TYPES_CAL).map(([k,v])=>`
          <span class="fchip${{activeTypes.has(k)?" active":""}}"
            style="${{activeTypes.has(k)?"color:"+v.text+";border-color:"+v.border+";background:"+v.bg:""}}"
            onclick="calToggleType('${{k}}')" data-t="${{k}}">
            <span style="width:6px;height:6px;border-radius:50%;background:${{v.border}};display:inline-block;margin-right:4px"></span>${{v.label}}
          </span>`).join("")}}
      </div>
      <div style="display:grid;grid-template-columns:1fr 260px;gap:12px">
        <div class="card" style="padding:10px">
          <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--border);border-radius:6px;overflow:hidden">
            ${{["Lun","Mar","Mer","Jeu","Ven","Sam","Dim"].map(d=>`
              <div style="background:var(--bg3);padding:5px;text-align:center;font-size:9px;font-weight:600;color:var(--text3);font-family:var(--font-mono)">${{d}}</div>`).join("")}}`;

    // Jours mois précédent
    for(let i=0;i<startDow;i++){{
      html+=`<div style="background:var(--bg2);min-height:76px;padding:5px;opacity:.25">
        <div style="font-size:10px;color:var(--text3);font-family:var(--font-mono)">${{daysInPrev-startDow+1+i}}</div></div>`;
    }}

    // Jours du mois
    for(let d=1;d<=daysInMonth;d++){{
      const isToday=d===now.getDate()&&curM===now.getMonth()&&curY===now.getFullYear();
      const evts=evtsForDate(curY,curM,d);
      const show=evts.slice(0,3);const more=evts.length-3;
      html+=`<div style="background:${{isToday?"rgba(0,212,255,.05)":"var(--bg2)"}};min-height:76px;padding:5px;
          border:${{isToday?"1px solid rgba(0,212,255,.25)":"1px solid transparent"}};
          transition:background .12s;cursor:${{evts.length?"pointer":"default"}}"
          ${{evts.length?`onclick="calOpenDay(${{curY}},${{curM}},${{d}})"`:""}}
          onmouseover="if(${{evts.length>0}})this.style.background='var(--bg3)'"
          onmouseout="this.style.background='${{isToday?"rgba(0,212,255,.05)":"var(--bg2)"}}'">
        <div style="font-size:10px;font-weight:600;margin-bottom:3px;font-family:var(--font-mono);color:${{isToday?"var(--cyan)":"var(--text3)"}}">
          ${{isToday?`<span style="background:var(--cyan);color:var(--bg);border-radius:50%;width:17px;height:17px;display:inline-flex;align-items:center;justify-content:center;font-size:9px">${{d}}</span>`:d}}
        </div>
        ${{show.map(e=>{{const t=TYPES_CAL[e.type]||TYPES_CAL.AUTRE;const idx=AGENDA.indexOf(e);
          return`<div style="font-size:9px;padding:2px 5px;border-radius:3px;margin-bottom:2px;
            background:${{t.bg}};border-left:2px solid ${{t.border}};color:${{t.text}};
            overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
            cursor:pointer" onclick="event.stopPropagation();openEvt(${{idx}})"
            title="${{esc(e.titre)}}">${{esc(e.titre)}}</div>`;}}}).join("")}}
        ${{more>0?`<div style="font-size:8px;color:var(--text3);font-family:var(--font-mono);padding:1px 4px">+${{more}} autre${{more>1?"s":""}}</div>`:""}}</div>`;
    }}

    // Jours mois suivant
    const total=startDow+daysInMonth;const rem=(7-total%7)%7;
    for(let i=1;i<=rem;i++){{
      html+=`<div style="background:var(--bg2);min-height:76px;padding:5px;opacity:.25">
        <div style="font-size:10px;color:var(--text3);font-family:var(--font-mono)">${{i}}</div></div>`;
    }}

    html+=`</div></div>

        <div style="display:flex;flex-direction:column;gap:10px">
          <div class="card">
            <div class="card-title">prochains événements</div>
            ${{upcoming.length?upcoming.map((e,i)=>{{
              const dt=new Date(e.date);const t=TYPES_CAL[e.type]||TYPES_CAL.AUTRE;
              const idx=AGENDA.indexOf(e);
              const diffJ=Math.ceil((dt-now)/(1000*60*60*24));
              return`<div class="proj-item" style="cursor:pointer;flex-direction:column;align-items:flex-start;gap:4px" onclick="openEvt(${{idx}})">
                <div style="display:flex;align-items:center;gap:7px;width:100%">
                  <div style="min-width:30px;text-align:center;background:var(--bg3);border-radius:5px;padding:3px 0;flex-shrink:0">
                    <div style="font-size:12px;font-weight:600;color:var(--text);font-family:var(--font-mono);line-height:1">${{dt.getDate()}}</div>
                    <div style="font-size:8px;color:var(--text3);text-transform:uppercase">${{MFR[dt.getMonth()].slice(0,3)}}</div>
                  </div>
                  <span class="proj-name" style="font-size:11px">${{esc(e.titre)}}</span>
                  <span class="badge" style="background:${{t.bg}};color:${{t.text}};border:1px solid ${{t.border}};margin-left:auto;font-size:8px">${{t.label}}</span>
                </div>
                <div style="font-size:9px;color:var(--text3);font-family:var(--font-mono);padding-left:37px">
                  ${{diffJ===0?"aujourd'hui":diffJ===1?"demain":"dans "+diffJ+" j"}}
                  ${{e.projet_ref?" · "+e.projet_ref:""}}
                </div>
              </div>`;
            }}).join(""):`<div style="font-size:11px;color:var(--text3);padding:8px 0;font-family:var(--font-mono)">// aucun événement à venir</div>`}}
          </div>
          <div class="card">
            <div class="card-title">légende</div>
            ${{Object.entries(TYPES_CAL).map(([,v])=>
              `<div style="display:flex;align-items:center;gap:7px;margin-bottom:7px;font-size:11px;color:var(--text2)">
                <span style="width:8px;height:8px;border-radius:50%;background:${{v.border}};flex-shrink:0"></span>
                ${{v.label}}
              </div>`).join("")}}
          </div>
        </div>
      </div>`;

    el.innerHTML=html;
  }}

  // Modal jour (si plusieurs événements)
  window.calOpenDay=function(y,m,d){{
    const key=`${{y}}-${{String(m+1).padStart(2,"0")}}-${{String(d).padStart(2,"0")}}`;
    const evts=AGENDA.filter(e=>e.date===key&&activeTypes.has(e.type));
    if(evts.length===1){{openEvt(AGENDA.indexOf(evts[0]));return;}}
    const dt=new Date(y,m,d);
    const dateStr=dt.toLocaleDateString("fr-FR",{{weekday:"long",day:"numeric",month:"long"}});
    document.getElementById("modal-body").innerHTML=`
      <button class="modal-close" onclick="closeModal()">x</button>
      <div class="modal-title">${{dateStr}}</div>
      <div class="modal-id">${{evts.length}} événement(s)</div>
      <div class="proj-list" style="margin-top:12px">
        ${{evts.map(e=>{{const t=TYPES_CAL[e.type]||TYPES_CAL.AUTRE;const idx=AGENDA.indexOf(e);
          return`<div class="proj-item" onclick="closeModal();setTimeout(()=>openEvt(${{idx}}),150)">
            <span class="proj-dot" style="background:${{t.border}}"></span>
            <span class="proj-name">${{esc(e.titre)}}</span>
            <span class="badge" style="background:${{t.bg}};color:${{t.text}};border:1px solid ${{t.border}};font-size:8px">${{t.label}}</span>
          </div>`;
        }}).join("")}}
      </div>`;
    document.getElementById("modal-overlay").classList.add("open");
  }};

  window.calNav=function(dir){{
    curM+=dir;
    if(curM>11){{curM=0;curY++;}}
    if(curM<0){{curM=11;curY--;}}
    buildCal();
  }};

  window.calToggleType=function(t){{
    if(activeTypes.has(t)){{if(activeTypes.size>1)activeTypes.delete(t);}}
    else activeTypes.add(t);
    document.querySelectorAll("#cal-type-filters .fchip").forEach(c=>{{
      const tt=c.dataset.t;const v=TYPES_CAL[tt];
      c.className="fchip"+(activeTypes.has(tt)?" active":"");
      c.style.cssText=activeTypes.has(tt)
        ?"color:"+v.text+";border-color:"+v.border+";background:"+v.bg:"";
    }});
    buildCal();
  }};

  window.openEvt=openEvt;
  buildCal();
}}
"""
