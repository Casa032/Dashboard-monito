"""
=======================================================================
INTÉGRATION PAGE STATISTIQUES — html_generator.py
=======================================================================
4 modifications à faire dans l'ordre. Chaque section indique
exactement QUOI chercher et QUOI ajouter/remplacer.
=======================================================================
"""

# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 1 — Sidebar
# CHERCHER :
#   <div class="nav-item" data-page="chat"><span class="nav-icon">⌘</span>Chat LLM</div>
# AJOUTER AVANT :
# ═══════════════════════════════════════════════════════════════════════
"""
    <div class="nav-item" data-page="stats"><span class="nav-icon">◉</span>Statistiques</div>
"""


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 2 — Pages HTML
# CHERCHER :
#   <div class="page" id="page-evolutions"></div>
# AJOUTER APRÈS :
# ═══════════════════════════════════════════════════════════════════════
"""
      <div class="page" id="page-stats"></div>
"""


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 3 — Constante PAGES dans le JS
# CHERCHER :
#   const PAGES={{overview:"overview",...,chat:"chat_llm"}};
# REMPLACER PAR :
# ═══════════════════════════════════════════════════════════════════════
"""
const PAGES={{overview:"overview",domaines:"par_domaine",collabs:"collaborateurs",gantt:"roadmap_gantt",evolutions:"evolutions",stats:"statistiques",chat:"chat_llm"}};
"""


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 4 — Ajouter le clic nav pour stats dans init()
# CHERCHER dans init() :
#   if(pg==="gantt")renderGantt();
# REMPLACER PAR :
# ═══════════════════════════════════════════════════════════════════════
"""
      if(pg==="gantt")renderGantt();
      if(pg==="stats")renderStats();
"""


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 5 — Ajouter les fonctions JS
# CHERCHER :
#   function renderEvolutions(){{
# AJOUTER AVANT (coller tout le bloc ci-dessous) :
# ═══════════════════════════════════════════════════════════════════════

STATS_JS = r"""
// ── Statistiques ─────────────────────────────────────────────────────

function computeStats(){{
  const snaps=DATA.snapshots||{{}};
  const qs=DATA.quinzaines||[];
  const hist=DATA.historiques||{{}};
  const meta=DATA.meta||[];

  // ── Série temporelle : une entrée par quinzaine ──────────────────
  const serie=qs.map(q=>{{
    const s=snaps[q]||{{}};
    const k=s.kpis||{{}};
    const p=s.projets||[];
    const total=p.length||1;
    const enDiff=(k.nb_at_risk||0)+(k.nb_en_retard||0);
    const livres=p.filter(x=>x.livrable_statut==="LIVRE").length;
    const nonLivres=p.filter(x=>x.livrable_statut==="NON_LIVRE").length;
    const reportes=p.filter(x=>x.livrable_statut==="REPORTE").length;
    const avecLivrable=p.filter(x=>x.livrable_statut&&x.livrable_statut.trim()!=="").length;
    return {{
      q,
      avancement:k.avancement_moyen||0,
      tauxDiff:Math.round(enDiff/total*100),
      nbDiff:enDiff,
      nbBlocages:k.nb_blocages||0,
      nbDecisions:k.nb_decisions||0,
      nbActifs:k.nb_projets_actifs||0,
      livres, nonLivres, reportes, avecLivrable,
      tauxLivre:avecLivrable>0?Math.round(livres/avecLivrable*100):null,
      parDomaine:s.par_domaine||{{}},
      parResp:s.par_resp||{{}},
      projets:p,
    }};
  }});

  // ── Vélocité par domaine : delta avancement moyen entre quinzaines ─
  const domaines=[...new Set(qs.flatMap(q=>(snaps[q]?.projets||[]).map(p=>p.domaine).filter(Boolean)))];
  const velociteDomaine={{}};
  domaines.forEach(dom=>{{
    const pts=[];
    for(let i=1;i<qs.length;i++){{
      const avant=(snaps[qs[i-1]]?.projets||[]).filter(p=>p.domaine===dom);
      const apres=(snaps[qs[i]]?.projets||[]).filter(p=>p.domaine===dom);
      if(!avant.length||!apres.length)continue;
      const avMap={{}};avant.forEach(p=>avMap[p.projet_id||p.ref_sujet]=p.avancement_pct||0);
      const deltas=apres.map(p=>{{const id=p.projet_id||p.ref_sujet;return avMap[id]!=null?(p.avancement_pct||0)-avMap[id]:null;}}).filter(x=>x!=null);
      if(deltas.length)pts.push(deltas.reduce((a,b)=>a+b,0)/deltas.length);
    }}
    velociteDomaine[dom]=pts.length?Math.round(pts.reduce((a,b)=>a+b,0)/pts.length*10)/10:null;
  }});

  // ── Signaux faibles ───────────────────────────────────────────────
  const signauxFaibles=[];
  Object.entries(hist).forEach(([pid,rows])=>{{
    if(rows.length<2)return;
    const sorted=[...rows].sort((a,b)=>a.quinzaine.localeCompare(b.quinzaine));
    const nom=sorted[0].projet_nom||sorted[0].sujet||pid;

    // Stagnation : delta < 5% sur 2 quinzaines consécutives
    for(let i=1;i<sorted.length;i++){{
      const delta=Math.abs((sorted[i].avancement_pct||0)-(sorted[i-1].avancement_pct||0));
      if(delta<5&&sorted[i].statut!=="DONE"&&sorted[i].statut!=="ON_HOLD"){{
        signauxFaibles.push({{
          type:"STAGNATION",
          nom, pid,
          detail:`Avancement stable (Δ${{Math.round(delta)}}%) entre ${{sorted[i-1].quinzaine}} et ${{sorted[i].quinzaine}}`,
          statut:sorted[i].statut, quinzaine:sorted[i].quinzaine,
        }});
        break;
      }}
    }}

    // Oscillation : statut change ≥ 3 fois
    const changements=sorted.filter((r,i)=>i>0&&r.statut!==sorted[i-1].statut).length;
    if(changements>=3){{
      signauxFaibles.push({{
        type:"OSCILLATION",
        nom, pid,
        detail:`Statut a changé ${{changements}} fois sur ${{sorted.length}} quinzaines`,
        statut:sorted[sorted.length-1].statut,
        quinzaine:sorted[sorted.length-1].quinzaine,
      }});
    }}

    // Trainards : ≥ 3 quinzaines consécutives en LATE ou AT_RISK
    let streak=0,maxStreak=0;
    sorted.forEach(r=>{{
      if(r.statut==="LATE"||r.statut==="AT_RISK"){{streak++;maxStreak=Math.max(maxStreak,streak);}}
      else streak=0;
    }});
    if(maxStreak>=3){{
      signauxFaibles.push({{
        type:"TRAINARD",
        nom, pid,
        detail:`${{maxStreak}} quinzaines consécutives en difficulté`,
        statut:sorted[sorted.length-1].statut,
        quinzaine:sorted[sorted.length-1].quinzaine,
      }});
    }}
  }});

  // Concentration charge : responsable avec > 40% des projets actifs
  const dernierSnap=serie[serie.length-1]||{{}};
  const parResp=dernierSnap.parResp||{{}};
  const totalActifs=Object.values(parResp).reduce((s,r)=>s+r.total,0)||1;
  const concentrations=Object.entries(parResp)
    .map(([r,d])=>{{return{{resp:r,n:d.total,pct:Math.round(d.total/totalActifs*100)}};  }})
    .filter(x=>x.pct>40);

  return {{serie, velociteDomaine, signauxFaibles, concentrations, domaines}};
}}

// ── SVG helpers ────────────────────────────────────────────────────────

function svgLine(points,color,h=120,pad=30){{
  if(points.length<2)return"";
  const vals=points.map(p=>p.y);
  const min=Math.min(...vals),max=Math.max(...vals);
  const range=max-min||1;
  const w=points.length>1?(points[points.length-1].x-points[0].x):1;
  const pts=points.map(p=>{{
    const x=pad+(p.x-points[0].x)/(w||1)*(400-pad*2);
    const y=pad+(1-(p.y-min)/range)*(h-pad*2);
    return`${{x.toFixed(1)}},${{y.toFixed(1)}}`;
  }}).join(" ");
  const first=pts.split(" ")[0],last=pts.split(" ").pop();
  const [lx,ly]=last.split(",");
  const [fx,fy]=first.split(",");
  return`<polyline points="${{pts}}" fill="none" stroke="${{color}}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    <polygon points="${{pts}} ${{lx}},${{h-pad}} ${{fx}},${{h-pad}}" fill="${{color}}" opacity="0.08"/>
    ${{points.map((p,i)=>{{const[px,py]=pts.split(" ")[i].split(",");return`<circle cx="${{px}}" cy="${{py}}" r="3" fill="${{color}}" stroke="var(--bg2)" stroke-width="1.5"/>`;}}  ).join("")}}`;
}}

function svgChart(serie,keyFn,color,label,unit="%",h=140){{
  if(!serie.length)return`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:12px">// données insuffisantes</div>`;
  const pad=32;const W=400;
  const points=serie.map((s,i)=>{{return{{x:i,y:keyFn(s),label:s.q}};  }});
  const vals=points.map(p=>p.y);
  const min=Math.min(...vals),max=Math.max(...vals);
  const range=max-min||1;
  const ticks=[0,.25,.5,.75,1].map(t=>min+t*range);

  return`<svg viewBox="0 0 ${{W}} ${{h}}" style="width:100%;height:${{h}}px;overflow:visible">
    <defs><linearGradient id="g${{label.replace(/\s/g,"_")}}" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="${{color}}" stop-opacity=".3"/>
      <stop offset="100%" stop-color="${{color}}" stop-opacity="0"/>
    </linearGradient></defs>
    ${{ticks.map(t=>{{const y=pad+(1-(t-min)/range)*(h-pad*2);
      return`<line x1="${{pad}}" y1="${{y.toFixed(1)}}" x2="${{W-10}}" y2="${{y.toFixed(1)}}" stroke="var(--border)" stroke-width="0.5"/>
        <text x="${{pad-4}}" y="${{(y+3).toFixed(1)}}" text-anchor="end" font-size="8" fill="var(--text3)" font-family="var(--font-mono)">${{Math.round(t)}}${{unit}}</text>`;
    }}).join("")}}
    ${{svgLine(points,color,h,pad)}}
    ${{points.map((p,i)=>{{const x=pad+i/(points.length-1||1)*(W-pad*2-10);
      return`<text x="${{x.toFixed(1)}}" y="${{h-4}}" text-anchor="middle" font-size="7.5" fill="var(--text3)" font-family="var(--font-mono)">${{p.label.replace("_"," ")}}</text>`;
    }}).join("")}}
  </svg>`;
}}

function barChart(items,color){{
  if(!items.length)return`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">// aucune donnée</div>`;
  const max=Math.max(...items.map(i=>i.val),1);
  return items.sort((a,b)=>b.val-a.val).map(item=>{{
    const pct=Math.round(item.val/max*100);
    const color2=item.color||color;
    return`<div style="display:flex;align-items:center;gap:8px;margin-bottom:7px">
      <span style="font-size:10px;min-width:110px;max-width:110px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text2)" title="${{esc(item.label)}}">${{esc(item.label)}}</span>
      <div style="flex:1;height:6px;background:var(--bg4);border-radius:4px;overflow:hidden">
        <div style="width:${{pct}}%;height:100%;border-radius:4px;background:${{color2}};transition:width .5s ease"></div>
      </div>
      <span style="font-size:10px;font-weight:600;min-width:32px;text-align:right;font-family:var(--font-mono);color:var(--text2)">${{item.val}}${{item.unit||""}}</span>
    </div>`;
  }}).join("");
}}

function jauge(val,max,color,label,sublabel=""){{
  const pct=Math.min(Math.round(val/max*100),100);
  const angle=-90+pct*1.8;
  const r=38;const cx=50;const cy=50;
  const x=cx+r*Math.cos((angle-90)*Math.PI/180);
  const y=cy+r*Math.sin((angle-90)*Math.PI/180);
  const large=pct>50?1:0;
  return`<div style="text-align:center">
    <svg viewBox="0 0 100 70" style="width:90px;height:63px">
      <path d="M${{cx-r}},${{cy}} A${{r}},${{r}} 0 1 1 ${{cx+r}},${{cy}}" fill="none" stroke="var(--bg4)" stroke-width="8" stroke-linecap="round"/>
      ${{pct>0?`<path d="M${{cx-r}},${{cy}} A${{r}},${{r}} 0 ${{large}} 1 ${{x.toFixed(1)}},${{y.toFixed(1)}}" fill="none" stroke="${{color}}" stroke-width="8" stroke-linecap="round"/>`:"" }}
      <text x="50" y="52" text-anchor="middle" font-size="14" font-weight="700" fill="${{color}}" font-family="var(--font-mono)">${{val}}${{max===100?"%":""}}</text>
    </svg>
    <div style="font-size:10px;font-weight:600;color:var(--text);margin-top:-6px">${{label}}</div>
    ${{sublabel?`<div style="font-size:9px;color:var(--text3);font-family:var(--font-mono)">${{sublabel}}</div>`:""}}
  </div>`;
}}

// ── Render principal ────────────────────────────────────────────────────

function renderStats(){{
  const el=document.getElementById("page-stats");
  if(!el)return;
  const st=computeStats();
  const s=st.serie;
  const last=s[s.length-1]||{{}};
  const hasHist=s.length>=2;

  // Sous-onglets
  const TABS=[
    {{id:"sante",    label:"Santé portefeuille"}},
    {{id:"velocite", label:"Vélocité"}},
    {{id:"livraisons",label:"Livraisons"}},
    {{id:"signaux",  label:"Signaux faibles"}},
  ];
  let activeTab="sante";

  function renderTab(){{
    const body=document.getElementById("stats-body");if(!body)return;
    if(activeTab==="sante") body.innerHTML=renderSante(st,s,last,hasHist);
    else if(activeTab==="velocite") body.innerHTML=renderVelocite(st,s,last,hasHist);
    else if(activeTab==="livraisons") body.innerHTML=renderLivraisons(st,s,last,hasHist);
    else if(activeTab==="signaux") body.innerHTML=renderSignaux(st,last);
  }}

  el.innerHTML=`
    <div style="display:flex;gap:4px;margin-bottom:14px;border-bottom:1px solid var(--border);padding-bottom:0" id="stats-tabs">
      ${{TABS.map(t=>`<div class="stat-tab${{t.id===activeTab?" active":""}}" data-tab="${{t.id}}"
        style="font-size:11px;padding:7px 14px;cursor:pointer;font-family:var(--font-mono);
        border-bottom:2px solid ${{t.id===activeTab?"var(--cyan)":"transparent"}};
        color:${{t.id===activeTab?"var(--cyan)":"var(--text3)"}};
        margin-bottom:-1px;transition:all .12s"
        onmouseover="if('${{t.id}}'!==activeTab)this.style.color='var(--text)'"
        onmouseout="if('${{t.id}}'!==activeTab)this.style.color='var(--text3)'"
        onclick="switchStatTab('${{t.id}}')">${{t.label}}</div>`).join("")}}
    </div>
    <div id="stats-body"></div>`;

  window.switchStatTab=function(tab){{
    activeTab=tab;
    document.querySelectorAll(".stat-tab").forEach(t=>{{
      const isActive=t.dataset.tab===tab;
      t.style.borderBottom=isActive?"2px solid var(--cyan)":"2px solid transparent";
      t.style.color=isActive?"var(--cyan)":"var(--text3)";
    }});
    renderTab();
  }};
  renderTab();
}}

// ── Onglet Santé ────────────────────────────────────────────────────────

function renderSante(st,s,last,hasHist){{
  const avMoy=last.avancement||0;
  const tauxDiff=last.tauxDiff||0;
  const nbBloc=last.nbBlocages||0;

  // Tendance avancement
  let tendAv="stable",tendCol="var(--text3)";
  if(s.length>=2){{
    const delta=s[s.length-1].avancement-s[s.length-2].avancement;
    if(delta>2){{tendAv=`+${{delta.toFixed(1)}}% vs Q-1`;tendCol="var(--green)";}}
    else if(delta<-2){{tendAv=`${{delta.toFixed(1)}}% vs Q-1`;tendCol="var(--red)";}}
    else{{tendAv=`stable vs Q-1`;tendCol="var(--text3)";}}
  }}

  return`
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px">
      ${{jauge(avMoy,100,"var(--cyan)","Avancement moyen",tendAv)}}
      ${{jauge(tauxDiff,100,"var(--red)","Taux en difficulté",`${{last.nbDiff||0}} projets`)}}
      ${{jauge(nbBloc,Math.max(nbBloc,10),"var(--amber)","Blocages actifs","cette quinzaine")}}
    </div>
    <div class="grid2">
      <div class="card">
        <div class="card-title">évolution avancement moyen</div>
        ${{hasHist
          ?svgChart(s,x=>x.avancement,"var(--cyan)","avancement","%")
          :`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">// disponible dès 2 quinzaines</div>`}}
      </div>
      <div class="card">
        <div class="card-title">évolution taux en difficulté</div>
        ${{hasHist
          ?svgChart(s,x=>x.tauxDiff,"var(--red)","difficulté","%")
          :`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">// disponible dès 2 quinzaines</div>`}}
      </div>
    </div>
    <div class="grid2">
      <div class="card">
        <div class="card-title">blocages & décisions par quinzaine</div>
        ${{hasHist
          ?`<div style="margin-bottom:8px">`+svgChart(s,x=>x.nbBlocages,"var(--amber)","blocages","",120)+`</div>
            <div style="font-size:9px;color:var(--amber);font-family:var(--font-mono);margin-bottom:4px">▲ Blocages</div>
            <div>`+svgChart(s,x=>x.nbDecisions,"var(--green)","décisions","",120)+`</div>
            <div style="font-size:9px;color:var(--green);font-family:var(--font-mono)">▲ Décisions</div>`
          :`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">// disponible dès 2 quinzaines</div>`}}
      </div>
      <div class="card">
        <div class="card-title">répartition statuts — quinzaine courante</div>
        ${{barChart(
          Object.entries({{"ON_TRACK":last.projets?.filter(p=>p.statut==="ON_TRACK").length||0,
            "AT_RISK":last.projets?.filter(p=>p.statut==="AT_RISK").length||0,
            "LATE":last.projets?.filter(p=>p.statut==="LATE").length||0,
            "DONE":last.projets?.filter(p=>p.statut==="DONE").length||0,
            "ON_HOLD":last.projets?.filter(p=>p.statut==="ON_HOLD").length||0}})
            .map(([k,v])=>{{return{{label:k,val:v,unit:" proj",color:SC[k]||"var(--text3)"}};}})
            .filter(x=>x.val>0),
          "var(--cyan)"
        )}}
      </div>
    </div>`;
}}

// ── Onglet Vélocité ─────────────────────────────────────────────────────

function renderVelocite(st,s,last,hasHist){{
  const velItems=Object.entries(st.velociteDomaine)
    .filter(([,v])=>v!=null)
    .map(([d,v])=>{{return{{label:d,val:Math.max(v,0),rawVal:v,unit:"%/Q",color:domColor(d)}};  }});

  const respItems=Object.entries(last.parResp||{{}})
    .map(([r,d])=>{{return{{label:r,val:d.total,unit:" proj"}};  }});

  return`
    <div class="card" style="margin-bottom:12px">
      <div class="card-title">vélocité par domaine (Δ avancement moyen / quinzaine)</div>
      ${{velItems.length
        ?barChart(velItems,"var(--cyan)")
        :`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">// disponible dès 2 quinzaines</div>`}}
      ${{velItems.length?`<div style="font-size:9px;color:var(--text3);font-family:var(--font-mono);margin-top:8px">
        Domaine le plus rapide : <span style="color:var(--green)">
        ${{velItems.sort((a,b)=>b.val-a.val)[0]?.label||"—"}}</span>
        · Domaine le plus lent : <span style="color:var(--amber)">
        ${{velItems.sort((a,b)=>a.val-b.val)[0]?.label||"—"}}</span>
      </div>`:"" }}
    </div>
    <div class="grid2">
      <div class="card">
        <div class="card-title">charge par responsable</div>
        ${{barChart(respItems,"var(--violet)")}}
        ${{st.concentrations.length
          ?`<div style="margin-top:10px;padding:8px;background:var(--amber-dim);border-radius:var(--radius);border:1px solid rgba(245,158,11,.2)">
              <div style="font-size:9px;color:var(--amber);font-family:var(--font-mono);font-weight:600;margin-bottom:4px">⚠ Concentration détectée</div>
              ${{st.concentrations.map(c=>`<div style="font-size:10px;color:var(--text2)">${{esc(c.resp)}} porte ${{c.pct}}% des projets actifs</div>`).join("")}}
            </div>`
          :`<div style="font-size:9px;color:var(--green);font-family:var(--font-mono);margin-top:8px">✓ Charge bien répartie</div>`}}
      </div>
      <div class="card">
        <div class="card-title">évolution projets actifs</div>
        ${{hasHist
          ?svgChart(s,x=>x.nbActifs,"var(--violet)","actifs","")
          :`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">// disponible dès 2 quinzaines</div>`}}
      </div>
    </div>`;
}}

// ── Onglet Livraisons ───────────────────────────────────────────────────

function renderLivraisons(st,s,last,hasHist){{
  const avecData=s.filter(x=>x.avecLivrable>0);
  const hasTaux=avecData.length>0;
  const dernierTaux=hasTaux?avecData[avecData.length-1].tauxLivre:null;

  return`
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px">
      ${{jauge(dernierTaux!=null?dernierTaux:0,100,"var(--green)","Taux livré",dernierTaux!=null?`${{last.livres||0}} / ${{last.avecLivrable||0}}`:"données insuffisantes")}}
      ${{jauge(last.reportes||0,Math.max(last.avecLivrable||1,1),"var(--amber)","Reportés",`${{last.reportes||0}} livrable(s)`)}}
      ${{jauge(last.nonLivres||0,Math.max(last.avecLivrable||1,1),"var(--red)","Non livrés",`${{last.nonLivres||0}} livrable(s)`)}}
    </div>
    <div class="card" style="margin-bottom:12px">
      <div class="card-title">évolution taux de livraison</div>
      ${{hasTaux&&hasHist
        ?svgChart(avecData,x=>x.tauxLivre,"var(--green)","livraison","%")
        :`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">
          // ${{hasTaux?"disponible dès 2 quinzaines avec données":"livrable_statut non renseigné dans les fiches"}}</div>`}}
    </div>
    <div class="card">
      <div class="card-title">répartition livrables — quinzaine courante</div>
      ${{last.avecLivrable>0
        ?barChart([
            {{label:"LIVRE",    val:last.livres||0,    unit:"",color:"var(--green)"}},
            {{label:"EN COURS", val:(last.avecLivrable-(last.livres||0)-(last.nonLivres||0)-(last.reportes||0)),unit:"",color:"var(--cyan)"}},
            {{label:"NON LIVRE",val:last.nonLivres||0, unit:"",color:"var(--red)"}},
            {{label:"REPORTE",  val:last.reportes||0,  unit:"",color:"var(--amber)"}},
          ].filter(x=>x.val>0),"var(--green)")
        :`<div style="font-size:10px;color:var(--text3);font-family:var(--font-mono);padding:8px">
            // livrable_statut non renseigné — les données apparaîtront dès que les fiches sont remplies</div>`}}
    </div>`;
}}

// ── Onglet Signaux faibles ──────────────────────────────────────────────

function renderSignaux(st,last){{
  const TYPE_SF={{
    STAGNATION:{{label:"Stagnation",     color:"var(--amber)",icon:"≈"}},
    OSCILLATION:{{label:"Instabilité",    color:"var(--violet)",icon:"~"}},
    TRAINARD:   {{label:"Cas persistant", color:"var(--red)",  icon:"!"}},
  }};

  const parType={{}};
  st.signauxFaibles.forEach(s=>{{
    if(!parType[s.type])parType[s.type]=[];
    parType[s.type].push(s);
  }});

  const hasSignaux=st.signauxFaibles.length>0;

  return`
    ${{!hasSignaux?`
      <div class="card" style="text-align:center;padding:32px">
        <div style="font-size:24px;margin-bottom:8px">✓</div>
        <div style="font-size:13px;font-weight:600;color:var(--green);font-family:var(--font-mono)">Aucun signal faible détecté</div>
        <div style="font-size:10px;color:var(--text3);margin-top:6px;font-family:var(--font-mono)">// disponible dès 2+ quinzaines avec données</div>
      </div>`:""}}
    ${{Object.entries(parType).map(([type,items])=>{{
      const cfg=TYPE_SF[type]||{{}};
      return`<div class="card" style="margin-bottom:10px">
        <div class="card-title" style="color:${{cfg.color}}">${{cfg.icon}} ${{cfg.label}} (${{items.length}})</div>
        <div class="proj-list">
          ${{items.map(sig=>`<div class="proj-item" onclick="openModal('${{esc(sig.pid)}}')" style="flex-direction:column;align-items:flex-start;gap:3px">
            <div style="display:flex;align-items:center;gap:7px;width:100%">
              <span class="proj-dot" style="background:${{cfg.color}}"></span>
              <span class="proj-name" style="font-size:11px">${{esc(sig.nom)}}</span>
              ${{badge(sig.statut)}}
            </div>
            <div style="font-size:9px;color:var(--text3);font-family:var(--font-mono);padding-left:13px">${{esc(sig.detail)}}</div>
          </div>`).join("")}}
        </div>
      </div>`;
    }}).join("")}}
    <div class="card">
      <div class="card-title">à propos des signaux faibles</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
        ${{Object.entries(TYPE_SF).map(([,cfg])=>`
          <div style="background:var(--bg3);border-radius:var(--radius);padding:10px">
            <div style="font-size:11px;font-weight:600;color:${{cfg.color}};margin-bottom:4px">${{cfg.icon}} ${{cfg.label}}</div>
            <div style="font-size:9px;color:var(--text3);line-height:1.5">${{
              cfg.label==="Stagnation"?"Δ avancement < 5% sur 2 quinzaines consécutives, projet non terminé":
              cfg.label==="Instabilité"?"Statut change ≥ 3 fois sur l'historique":
              "≥ 3 quinzaines consécutives en AT_RISK ou LATE"
            }}</div>
          </div>`).join("")}}
      </div>
    </div>`;
}}
"""
