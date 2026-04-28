"""
=======================================================================
SUITE DES MODIFICATIONS html_generator.py
=======================================================================
"""

# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 8 — Gestion du clic nav pour la page calendrier
#
# Dans la fonction init(), tu as ce bloc qui gère le clic sur les
# nav-items. Le code actuel fait un if(pg==="gantt")renderGantt().
# Il faut ajouter le même principe pour "calendrier".
#
# CHERCHER dans init() :
#       if(pg==="gantt")renderGantt();
#
# REMPLACER PAR :
# ═══════════════════════════════════════════════════════════════════════

      if(pg==="gantt")renderGantt();
      if(pg==="calendrier")renderCalendrier();


# ═══════════════════════════════════════════════════════════════════════
# MODIFICATION 9 — switchQuinzaine() : reset le calendrier au changement
#
# CHERCHER dans switchQuinzaine() :
#       const gp=document.getElementById("page-gantt");
#       if(gp&&gp.innerHTML.trim()!=="")renderGantt();
#
# REMPLACER PAR :
# ═══════════════════════════════════════════════════════════════════════

  const gp=document.getElementById("page-gantt");
  if(gp&&gp.innerHTML.trim()!=="")renderGantt();
  // Reset calendrier pour qu'il se régénère avec les nouvelles données
  const cp=document.getElementById("page-calendrier");
  if(cp)cp.innerHTML="";


# ═══════════════════════════════════════════════════════════════════════
# RÉCAPITULATIF COMPLET DE L'ORDRE DES MODIFICATIONS
# ═══════════════════════════════════════════════════════════════════════

"""
1. preparer_donnees() — ajouter chargement agenda + "agenda": agenda_list dans le return
2. Sidebar HTML       — ajouter nav-item Calendrier entre Evolutions et Chat LLM
3. Pages HTML         — ajouter <div class="page" id="page-calendrier"></div>
4. Constante PAGES    — ajouter calendrier:"calendrier" dans le dict JS
5. init() JS          — initialiser badge nb-cal avec DATA.agenda.length
6. renderGantt()      — remplacer par la nouvelle version 12 mois avec dates META
7. renderCalendrier() — ajouter la fonction complète après renderEvolutions()
8. init() nav click   — ajouter if(pg==="calendrier")renderCalendrier()
9. switchQuinzaine()  — ajouter reset du calendrier

STRUCTURE AGENDA dans l'onglet Excel du manager :
┌─────────────┬─────────────────────────┬───────────┬────────────────────────┬─────────────┐
│    date     │         titre           │   type    │      description       │ projet_ref  │
├─────────────┼─────────────────────────┼───────────┼────────────────────────┼─────────────┤
│ 02/05/2026  │ Réunion PICKIS          │ REUNION   │ Point quinzaine data   │             │
│ 06/05/2026  │ Actualité groupe DEKA   │ ACTUALITE │ Présentation résultats │             │
│ 12/05/2026  │ Livraison scoring       │ LIVRAISON │ V1 en production       │ PROJ-001    │
│ 15/05/2026  │ Comité data             │ REUNION   │ Gouvernance mensuelle  │             │
└─────────────┴─────────────────────────┴───────────┴────────────────────────┴─────────────┘

Types acceptés : REUNION / LIVRAISON / ACTUALITE / JALON / AUTRE
"""
