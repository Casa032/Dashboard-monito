"""
rag_engine.py
=============
Moteur de requêtes en langage naturel sur les données de monitoring.

Stratégie : RAG sans base vectorielle.
    Construit dynamiquement un contexte textuel depuis le Parquet
    et l'envoie au LLM interne avec la question.

Format quinzaine : T1_2026_R1 (T[trimestre]_[année]_R[rang])

Rôle dans le pipeline :
    excel_parser.py → storage.py → rag_engine.py → html_generator.py
                                                  → api/main.py (POST /api/chat)

Usage :
    python rag_engine.py
    python rag_engine.py --question "quels projets sont en retard ?"
    python rag_engine.py --quinzaine T1_2026_R1 --question "résume l'avancement"
    python rag_engine.py --test
    python rag_engine.py --pre-gen
"""

import sys
import json
import yaml
import logging
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

try:
    from storage.storage import StorageManager
except ImportError:
    from storage import StorageManager  # type: ignore

log = logging.getLogger(__name__)

# ── Questions pré-générées pour le cache HTML ─────────────────────────────────
QUESTIONS_STANDARD = [
    "quels projets sont en retard ?",
    "quels projets sont à risque ?",
    "quelles décisions ont été prises ?",
    "y a-t-il des blocages actifs ?",
    "résume l'avancement global de la quinzaine",
    "quelles actions sont à mener en priorité ?",
    "quel est le projet le plus avancé ?",
    "quel est le projet le plus en difficulté ?",
    "quels projets arrivent bientôt à échéance ?",
    "quels projets ont un risque critique ou élevé ?",
]


class RagEngine:
    """
    Moteur de requêtes LLM sur les données de monitoring projets.

    Adapté au format de données :
        - Feuilles quinzaine : T1_2026_R1 ... T4_2026_R6
        - Colonnes : ref_sujet/projet_id, sujet/projet_nom, domaine,
                     statut, avancement_pct, responsable_principal,
                     date_debut, date_fin_prevue, budget_jours, priorite, etc.
    """

    def __init__(self, config_path="config.yaml"):
        self.sm      = StorageManager(config_path)
        self.config  = self._charger_config(config_path)
        llm          = self.config.get("llm", {})
        self.api_key     = llm.get("api_key", "")
        self.base_url    = llm.get("base_url", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
        self.model       = llm.get("model", "qwen-plus")
        self.max_tokens  = llm.get("max_tokens", 1500)
        self.temperature = llm.get("temperature", 0.2)

        if not self.api_key:
            log.warning("RagEngine — aucune api_key dans config.yaml (llm.api_key)")
        log.info(f"RagEngine — base_url : {self.base_url} — modèle : {self.model}")

    def _charger_config(self, path) -> dict:
        p = Path(path)
        return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}

    # ── Construction du contexte ───────────────────────────────────────────────

    def construire_contexte(self, quinzaine: str | None = None) -> str:
        """
        Construit le contexte textuel injecté dans le prompt LLM.
        Inclut les KPIs globaux + le détail de chaque projet,
        enrichi des données META (dates, budget, priorité).
        """
        q = quinzaine or (self.sm.lister_quinzaines() or [""])[-1]
        df = self.sm.charger_quinzaines(quinzaines=[q])

        if df.empty:
            return f"Aucune donnée disponible pour la quinzaine {q}."

        kpis  = self.sm.kpis(quinzaine=q)
        lignes = []

        # En-tête avec KPIs
        lignes.append(f"=== MONITORING PROJETS — {q} ===")
        lignes.append(
            f"Résumé : {kpis.get('nb_projets_actifs', 0)} projets actifs, "
            f"{kpis.get('nb_en_retard', 0)} en retard, "
            f"{kpis.get('nb_at_risk', 0)} à risque, "
            f"avancement moyen {kpis.get('avancement_moyen', 0)}%"
        )
        lignes.append("")

        # Détail par projet
        for _, row in df.iterrows():
            nom = row.get("projet_nom") or row.get("sujet") or ""
            pid = row.get("projet_id") or row.get("ref_sujet") or ""

            bloc = [
                f"PROJET : {nom} ({pid})",
                f"  Statut         : {row.get('statut', '')}",
                f"  Avancement     : {row.get('avancement_pct', 0)}%",
                f"  Responsable    : {row.get('responsable_principal', '')}",
                f"  Domaine        : {row.get('domaine', '')}",
                f"  Phase          : {row.get('phase', '')}",
                f"  Priorité       : {row.get('priorite', '')}",
                f"  Budget (j/sem) : {row.get('budget_jours', '')}",
                f"  Date début     : {row.get('date_debut', '')}",
                f"  Date fin prév. : {row.get('date_fin_prevue', '')}",
                f"  Entité         : {row.get('entite_concerne', '')}",
                f"  Livrable       : {row.get('livrable_quinzaine', '')} → {row.get('livrable_statut', '')}",
            ]

            # Champs optionnels
            for champ, label in [
                ("actions_realises",   "  Actions réalisées :"),
                ("actions_a_mener",    "  Actions à mener   :"),
                ("actions_echeance",   "  Échéance actions  :"),
                ("charge_a_prevoir",   "  Charge prévue     :"),
                ("risques",            "  Risques           :"),
                ("risque_niveau",      "  Niveau risque     :"),
                ("points_blocage",     "  Blocages          :"),
                ("commentaire_libre",  "  Commentaire       :"),
            ]:
                val = str(row.get(champ, "") or "").strip()
                if val and val not in ("None", "nan", ""):
                    bloc.append(f"{label} {val}")

            lignes.extend(bloc)
            lignes.append("")

        return "\n".join(lignes)

    def construire_contexte_historique(self, projet_id: str) -> str:
        """
        Contexte historique d'un projet sur toutes les quinzaines.
        """
        df = self.sm.projet(projet_id)
        if df.empty:
            return f"Aucune donnée pour le projet {projet_id}."

        nom = (df.get("projet_nom", df.get("sujet", pd.Series([projet_id]))).iloc[0]
               if hasattr(df, "get") else projet_id)
        lignes = [f"=== HISTORIQUE : {nom} ({projet_id}) ===", ""]

        for _, row in df.iterrows():
            lignes.append(f"[{row.get('quinzaine', '')}]")
            lignes.append(
                f"  Statut : {row.get('statut', '')} — {row.get('avancement_pct', 0)}%"
            )
            for champ, label in [
                ("livrable_quinzaine", "  Livrable   :"),
                ("actions_realises",   "  Réalisé    :"),
                ("actions_a_mener",    "  À mener    :"),
                ("risques",            "  Risques    :"),
                ("points_blocage",     "  Blocages   :"),
            ]:
                val = str(row.get(champ, "") or "").strip()
                if val and val not in ("None", "nan"):
                    lignes.append(f"{label} {val}")
            lignes.append("")

        return "\n".join(lignes)

    # ── Appel LLM ─────────────────────────────────────────────────────────────

    def _appeler_llm(self, systeme: str, utilisateur: str) -> str:
        if not self.api_key:
            return "[LLM non configuré — ajoute llm.api_key dans config.yaml]"
        try:
            import urllib.request

            payload = json.dumps({
                "model":       self.model,
                "max_tokens":  self.max_tokens,
                "temperature": self.temperature,
                "messages": [
                    {"role": "system", "content": systeme},
                    {"role": "user",   "content": utilisateur},
                ],
            }).encode("utf-8")

            url = self.base_url.rstrip("/") + "/chat/completions"
            req = urllib.request.Request(
                url, data=payload,
                headers={
                    "Content-Type":  "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
                return data["choices"][0]["message"]["content"].strip()

        except Exception as e:
            log.error(f"Erreur LLM : {e}")
            return f"[Erreur LLM : {e}]"

    # ── Requête principale ────────────────────────────────────────────────────

    def query(self, question: str, quinzaine: str | None = None) -> str:
        """
        Répond à une question en langage naturel sur les projets.
        Détecte automatiquement si la question porte sur un projet spécifique
        et adapte le contexte (snapshot quinzaine vs historique projet).
        """
        q = quinzaine or (self.sm.lister_quinzaines() or [""])[-1]

        # Détecter si un projet est mentionné dans la question
        projets = self.sm.lister_projets()
        projet_mentionne = None
        for p in projets:
            pid = str(p.get("projet_id") or p.get("ref_sujet") or "").lower()
            nom = str(p.get("projet_nom") or p.get("sujet") or "").lower()
            if (pid and pid in question.lower()) or (nom and nom in question.lower()):
                projet_mentionne = p.get("projet_id") or p.get("ref_sujet")
                break

        contexte = (
            self.construire_contexte_historique(projet_mentionne)
            if projet_mentionne
            else self.construire_contexte(q)
        )

        systeme = (
            "Tu es un assistant expert en pilotage de projets data. "
            "Tu travailles pour une équipe de data scientists. "
            "Tu réponds en français, de manière concise et structurée. "
            "Tu bases tes réponses uniquement sur les données fournies dans le contexte. "
            "Si une information est absente, dis-le clairement. "
            "Tu utilises des tirets pour les listes. "
            "Tu mets en avant les alertes (retards, risques critiques, blocages) en premier."
        )

        utilisateur = (
            f"Contexte de monitoring projets :\n\n{contexte}\n\n"
            f"Question : {question}"
        )

        log.info(f"LLM query — {q} — {question[:60]}...")
        return self._appeler_llm(systeme, utilisateur)

    # ── Pré-génération pour le cache HTML ─────────────────────────────────────

    def pre_generer(self,
                    questions: list | None = None,
                    quinzaine: str | None = None) -> dict:
        """
        Pré-génère les réponses LLM pour toutes les quinzaines disponibles.
        Retourne un dict {quinzaine:question → réponse} injecté en JSON dans le HTML.
        """
        qs = questions or QUESTIONS_STANDARD
        quinzaines_cibles = [quinzaine] if quinzaine else self.sm.lister_quinzaines()

        if not quinzaines_cibles:
            print("Aucune quinzaine disponible.")
            return {}

        cache = {}
        total = len(qs) * len(quinzaines_cibles)
        n = 0

        for q in quinzaines_cibles:
            print(f"\nPré-génération LLM — {len(qs)} questions — {q}")
            print("-" * 60)
            for question in qs:
                n += 1
                print(f"[{n}/{total}] {question[:55]}...")
                try:
                    reponse = self.query(question, quinzaine=q)
                    cache[f"{q}:{question.lower().strip()}"] = reponse
                    cache[question.lower().strip()] = reponse
                    print(f"       → {reponse[:80]}...")
                except Exception as e:
                    cache[f"{q}:{question.lower().strip()}"] = f"[Erreur : {e}]"
                    log.error(f"Erreur pré-génération '{question}' ({q}) : {e}")

        print("-" * 60)
        print(f"Cache LLM : {len(cache)} entrées ({len(quinzaines_cibles)} quinzaine(s))\n")
        return cache

    def tester_connexion(self) -> bool:
        print(f"Test connexion → {self.base_url} — modèle : {self.model}")
        reponse = self._appeler_llm(
            systeme="Tu es un assistant. Réponds en un seul mot.",
            utilisateur="Dis juste 'OK'."
        )
        ok = not reponse.startswith("[")
        print(f"Résultat : {'✓ Connecté' if ok else '✗ Échec — ' + reponse}")
        return ok


# ── Fonction d'intégration pour html_generator.py ─────────────────────────────

def enrichir_html_generator(config_path="config.yaml",
                             quinzaine: str | None = None,
                             questions: list | None = None) -> dict:
    rag = RagEngine(config_path)
    return rag.pre_generer(questions=questions, quinzaine=quinzaine)


# ── Point d'entrée ────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Moteur RAG — requêtes LLM projets")
    parser.add_argument("--question",  "-q", default=None)
    parser.add_argument("--quinzaine", "-Q", default=None,
                        help="Ex : T1_2026_R1")
    parser.add_argument("--pre-gen",   action="store_true")
    parser.add_argument("--test",      action="store_true")
    parser.add_argument("--contexte",  action="store_true")
    parser.add_argument("--config",    default="config.yaml")
    args = parser.parse_args()

    rag = RagEngine(args.config)

    if args.test:
        rag.tester_connexion()
        return

    if args.contexte:
        print(rag.construire_contexte(args.quinzaine))
        return

    if args.pre_gen:
        cache = rag.pre_generer(quinzaine=args.quinzaine)
        chemin = Path("storage/llm_cache.json")
        chemin.parent.mkdir(exist_ok=True)
        chemin.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Cache sauvegardé : {chemin}")
        return

    if args.question:
        print(f"\nQuestion : {args.question}")
        print("-" * 60)
        print(rag.query(args.question, quinzaine=args.quinzaine))
        print()
        return

    # Mode interactif
    print(f"\nMode interactif — quinzaine : {args.quinzaine or 'dernière'}")
    print("Tape 'exit' pour quitter\n" + "-" * 60)
    while True:
        try:
            question = input("\nQuestion : ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if question.lower() in ("exit", "quit", "q"):
            break
        if question:
            print(f"\n{rag.query(question, quinzaine=args.quinzaine)}")


if __name__ == "__main__":
    main()
