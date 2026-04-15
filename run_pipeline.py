"""
run_pipeline.py
===============
Point d'entrée unique du pipeline Project Intelligence.

Pipeline complet :
    monito.xlsx → Parquet → dashboard.html + (optionnel) PDF

Usage :
    python run_pipeline.py                  # ingestion + dashboard
    python run_pipeline.py --pdf            # + génère un PDF quinzaine
    python run_pipeline.py --quinzaine Q2_2025_S1   # quinzaine ciblée
    python run_pipeline.py --skip-ingest    # regénère seulement le dashboard
    python run_pipeline.py --llm            # active le chat LLM dans le dashboard

Prérequis :
    pip install pandas pyarrow openpyxl pyyaml reportlab
"""

import sys
import argparse
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Project Intelligence — monito.xlsx → dashboard + PDF"
    )
    parser.add_argument("--config",        default="config.yaml",  help="Fichier de configuration")
    parser.add_argument("--quinzaine",     default=None,           help="Quinzaine ciblée (ex: Q2_2025_S1)")
    parser.add_argument("--skip-ingest",   action="store_true",    help="Sauter l'ingestion Excel (utiliser le Parquet existant)")
    parser.add_argument("--pdf",           action="store_true",    help="Générer un rapport PDF en plus du dashboard")
    parser.add_argument("--llm",           action="store_true",    help="Pré-générer les réponses LLM pour le chat")
    parser.add_argument("--only-ingest",   action="store_true",    help="Ingestion seulement, sans générer le dashboard")
    args = parser.parse_args()

    config = args.config
    ok = True

    # ── Étape 1 : Ingestion Excel → Parquet ──────────────────────────────────
    if not args.skip_ingest:
        print("\n" + "="*55)
        print("  ÉTAPE 1 — Lecture de monito.xlsx → Parquet")
        print("="*55)
        try:
            from excel_parser import pipeline_complet
            ok = pipeline_complet(config)
            if not ok:
                print("\n⚠️  Ingestion incomplète — vérifier monito.xlsx")
                sys.exit(1)
            print("✓ Ingestion terminée")
        except ImportError as e:
            print(f"✗ Impossible d'importer excel_parser : {e}")
            sys.exit(1)
    else:
        print("\nIngestion ignorée (--skip-ingest) — utilisation du Parquet existant")

    if args.only_ingest:
        print("\nPipeline terminé (--only-ingest).")
        return

    # ── Étape 2 : Pré-génération LLM (optionnel) ─────────────────────────────
    llm_cache = {}
    if args.llm:
        print("\n" + "="*55)
        print("  ÉTAPE 2 — Pré-génération LLM")
        print("="*55)
        try:
            from rag_engine import enrichir_html_generator
            llm_cache = enrichir_html_generator(config, quinzaine=args.quinzaine)
            print(f"✓ {len(llm_cache)} réponses LLM générées")
        except Exception as e:
            print(f"⚠️  LLM non disponible : {e}")
            print("   Le dashboard sera généré sans réponses pré-cachées.")

    # ── Étape 3 : Génération du dashboard HTML ────────────────────────────────
    print("\n" + "="*55)
    print("  ÉTAPE 3 — Génération du dashboard HTML")
    print("="*55)
    try:
        from html_generator import generer_dashboard
        chemin_html = generer_dashboard(
            config_path=config,
            quinzaine=args.quinzaine,
            llm_reponses=llm_cache,
        )
        if chemin_html:
            print(f"✓ Dashboard généré : {chemin_html}")
        else:
            print("⚠️  Dashboard non généré")
    except Exception as e:
        print(f"✗ Erreur génération dashboard : {e}")
        log.exception(e)

    # ── Étape 4 : Génération PDF (optionnel) ──────────────────────────────────
    if args.pdf:
        print("\n" + "="*55)
        print("  ÉTAPE 4 — Génération du rapport PDF")
        print("="*55)
        try:
            from pdf_builder import PdfBuilder
            builder = PdfBuilder(config)
            chemin_pdf = builder.rapport_quinzaine(quinzaine=args.quinzaine)
            if chemin_pdf:
                print(f"✓ Rapport PDF généré : {chemin_pdf}")
        except Exception as e:
            print(f"✗ Erreur génération PDF : {e}")
            log.exception(e)

    print("\n" + "="*55)
    print("  Pipeline terminé ✓")
    print("="*55 + "\n")


if __name__ == "__main__":
    main()
