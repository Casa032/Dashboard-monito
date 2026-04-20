"""
excel_parser.py
===============
Lecture des fiches individuelles Excel et consolidation vers Parquet.

Structure attendue dans chaque fiche :
    - Feuille META       : infos statiques du projet (ref_sujet, sujet, domaine, etc.)
    - Feuilles quinzaine : T1_2026_R1, T2_2026_R3, etc. (pattern T[1-4]_20XX_R[1-6])
    - Feuilles ignorées  : TEMPLATE, DICTIONNAIRE, et tout ce qui ne matche pas le pattern

Stratégie incrémentale :
    - Quinzaines passées → Parquet figé, jamais relu sauf si --force
    - Quinzaine courante → toujours relue (saisie encore en cours)

Usage :
    python excel_parser.py                         # incrémental
    python excel_parser.py --force                 # tout retraiter
    python excel_parser.py --quinzaine T1_2026_R1  # une seule quinzaine
    python excel_parser.py --config config.yaml
"""

import re
import sys
import logging
import argparse
import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

# Pattern valide pour les feuilles quinzaine : T1_2026_R1 ... T4_2099_R6
PATTERN_QUINZAINE = re.compile(r"^T[1-4]_\d{4}_R[1-6]$")

# Colonnes attendues dans les feuilles quinzaine (ton dictionnaire)
COLONNES_FEUILLE = [
    "ref_sujet", "sujet", "phase", "statut", "avancement_pct",
    "livrable_quinzaine", "livrable_statut",
    "actions_realises", "actions_a_mener", "actions_echeance",
    "charge_a_prevoir", "risques", "risque_niveau",
    "points_blocage", "commentaire",
]

# Colonnes attendues dans META
COLONNES_META = [
    "type", "ref_sujet", "sujet", "domaine", "entite_concerne",
    "effectifs", "responsable_principal",
    "date_debut", "date_fin_prevue",
    "priorite", "budget_jours", "description",
]

# Mapping vers les noms internes utilisés dans le dashboard et le RAG
RENAME_FEUILLE = {
    "sujet":             "projet_nom",
    "ref_sujet":         "projet_id",
    "commentaire":       "commentaire_libre",
}

RENAME_META = {
    "sujet":     "projet_nom",
    "ref_sujet": "projet_id",
}


def _charger_config(config_path: str) -> dict:
    p = Path(config_path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def _quinzaine_courante(config: dict) -> str | None:
    """
    Retourne la quinzaine courante depuis config.yaml.
    Si non déclarée, la déduit de la date du jour.
    Format : T[trimestre]_[année]_R[rang dans le trimestre]
    Ex : T2_2026_R3
    """
    q = config.get("quinzaine_courante")
    if q:
        return q
    now = datetime.now()
    trimestre = (now.month - 1) // 3 + 1
    # Rang approximatif dans le trimestre selon le mois courant dans le trimestre
    mois_dans_trim = (now.month - 1) % 3 + 1
    rang = 1 if mois_dans_trim == 1 else (3 if mois_dans_trim == 2 else 5)
    if now.day > 15:
        rang += 1
    rang = min(rang, 6)
    return f"T{trimestre}_{now.year}_R{rang}"


def _est_feuille_quinzaine(nom: str) -> bool:
    return bool(PATTERN_QUINZAINE.match(nom))


def _lire_meta(wb_path: Path, xl: pd.ExcelFile) -> pd.DataFrame:
    """
    Lit la feuille META d'un fichier Excel.
    Retourne un DataFrame avec les colonnes META normalisées.
    Colonnes absentes → NaN, colonnes inconnues → ignorées.
    """
    if "META" not in xl.sheet_names:
        log.warning(f"{wb_path.name} — pas de feuille META")
        return pd.DataFrame()

    try:
        df = xl.parse("META", dtype=str)
    except Exception as e:
        log.error(f"{wb_path.name} — erreur lecture META : {e}")
        return pd.DataFrame()

    # Normaliser les noms de colonnes (minuscules, strip)
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Garder uniquement les colonnes connues
    cols_presentes = [c for c in COLONNES_META if c in df.columns]
    df = df[cols_presentes].copy()

    # Filtrer les lignes sans ref_sujet
    if "ref_sujet" in df.columns:
        df = df[df["ref_sujet"].notna() & (df["ref_sujet"].str.strip() != "")]

    df = df.rename(columns=RENAME_META)
    df["source_fichier"] = wb_path.name

    log.debug(f"{wb_path.name} — META : {len(df)} projet(s)")
    return df


def _lire_feuille_quinzaine(wb_path: Path, xl: pd.ExcelFile,
                             nom_feuille: str, responsable: str) -> pd.DataFrame:
    """
    Lit une feuille quinzaine d'un fichier Excel.
    Enrichit chaque ligne avec le nom du responsable et la quinzaine.
    """
    try:
        df = xl.parse(nom_feuille, dtype=str)
    except Exception as e:
        log.error(f"{wb_path.name}/{nom_feuille} — erreur lecture : {e}")
        return pd.DataFrame()

    if df.empty:
        return pd.DataFrame()

    # Normaliser les noms de colonnes
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Filtrer les lignes sans ref_sujet (lignes vides / template)
    if "ref_sujet" not in df.columns:
        log.warning(f"{wb_path.name}/{nom_feuille} — colonne 'ref_sujet' absente")
        return pd.DataFrame()

    df = df[df["ref_sujet"].notna() & (df["ref_sujet"].str.strip() != "")].copy()
    if df.empty:
        return pd.DataFrame()

    # Garder les colonnes connues + toute colonne présente
    cols_presentes = [c for c in COLONNES_FEUILLE if c in df.columns]
    df = df[cols_presentes].copy()

    # Normalisation avancement_pct : 0-1 → 0-100
    if "avancement_pct" in df.columns:
        def _normaliser_pct(v):
            try:
                f = float(str(v).replace(",", ".").replace("%", "").strip())
                return round(f * 100 if f <= 1.0 else f)
            except (ValueError, TypeError):
                return None
        df["avancement_pct"] = df["avancement_pct"].apply(_normaliser_pct)

    # Normalisation statut → majuscules avec underscore
    if "statut" in df.columns:
        STATUT_MAP = {
            "en cours":   "ON_TRACK",
            "a risque":   "AT_RISK",
            "à risque":   "AT_RISK",
            "en retard":  "LATE",
            "terminé":    "DONE",
            "termine":    "DONE",
            "stand by":   "ON_HOLD",
            "on hold":    "ON_HOLD",
            "on_track":   "ON_TRACK",
            "at_risk":    "AT_RISK",
            "late":       "LATE",
            "done":       "DONE",
            "on_hold":    "ON_HOLD",
        }
        df["statut"] = df["statut"].apply(
            lambda v: STATUT_MAP.get(str(v).strip().lower(), str(v).strip().upper()
                                     if pd.notna(v) else "ON_TRACK")
        )

    df = df.rename(columns=RENAME_FEUILLE)
    df["quinzaine"]             = nom_feuille
    df["responsable_principal"] = responsable
    df["source_fichier"]        = wb_path.name

    return df


def _extraire_responsable(wb_path: Path) -> str:
    """
    Déduit le nom du responsable depuis le nom du fichier.
    Ex : Fiches_Juno.xlsx → "Juno"
         Fiches_Jean_Dupont.xlsx → "Jean Dupont"
    """
    stem = wb_path.stem  # sans extension
    # Supprimer préfixe "Fiches_" ou "Fiche_" case-insensitive
    stem = re.sub(r"(?i)^fiches?_", "", stem)
    return stem.replace("_", " ").strip()


def parser_fiches(
    dossier_fiches: str | Path,
    dossier_parquet: str | Path,
    quinzaine_courante: str | None = None,
    force: bool = False,
    quinzaine_unique: str | None = None,
) -> dict[str, int]:
    """
    Parcourt tous les fichiers Excel de dossier_fiches.
    Pour chaque quinzaine détectée :
        - Si Parquet existe et quinzaine != courante → skip (incrémental)
        - Sinon → lit, consolide, sauvegarde Parquet
    Retourne un dict {quinzaine: nb_lignes_écrites}.
    """
    dossier_fiches  = Path(dossier_fiches)
    dossier_parquet = Path(dossier_parquet)
    dossier_parquet.mkdir(parents=True, exist_ok=True)

    if not dossier_fiches.exists():
        log.error(f"Dossier fiches introuvable : {dossier_fiches}")
        return {}

    # Lister tous les fichiers Excel (pas les temp ~$...)
    fichiers = [
        f for f in dossier_fiches.rglob("*.xls*")
        if not f.name.startswith("~$") and f.suffix in (".xlsx", ".xlsm", ".xls")
    ]
    if not fichiers:
        log.warning(f"Aucun fichier Excel dans {dossier_fiches}")
        return {}

    log.info(f"{len(fichiers)} fiche(s) trouvée(s) dans {dossier_fiches}")

    # Collecter toutes les données par quinzaine
    # {quinzaine: [df1, df2, ...]}
    donnees_par_q: dict[str, list[pd.DataFrame]] = {}
    metas: list[pd.DataFrame] = []

    for fichier in sorted(fichiers):
        responsable = _extraire_responsable(fichier)
        log.info(f"  Lecture : {fichier.name} (responsable : {responsable})")
        try:
            xl = pd.ExcelFile(fichier, engine="openpyxl")
        except Exception as e:
            log.error(f"  Impossible d'ouvrir {fichier.name} : {e}")
            continue

        # Lire META
        df_meta = _lire_meta(fichier, xl)
        if not df_meta.empty:
            metas.append(df_meta)

        # Lire les feuilles quinzaine
        feuilles_quinzaine = [s for s in xl.sheet_names if _est_feuille_quinzaine(s)]
        if not feuilles_quinzaine:
            log.warning(f"  {fichier.name} — aucune feuille quinzaine détectée")
            continue

        for nom_feuille in feuilles_quinzaine:
            # Filtre si quinzaine_unique demandée
            if quinzaine_unique and nom_feuille != quinzaine_unique:
                continue

            df_q = _lire_feuille_quinzaine(fichier, xl, nom_feuille, responsable)
            if not df_q.empty:
                donnees_par_q.setdefault(nom_feuille, []).append(df_q)

    # Sauvegarder la META consolidée
    if metas:
        df_meta_global = pd.concat(metas, ignore_index=True).drop_duplicates(
            subset=["projet_id"], keep="last"
        )
        chemin_meta = dossier_parquet / "meta.parquet"
        df_meta_global.to_parquet(chemin_meta, index=False)
        log.info(f"META consolidée → {chemin_meta} ({len(df_meta_global)} projets)")

    # Sauvegarder les Parquet par quinzaine (stratégie incrémentale)
    resultats = {}
    for quinzaine, dfs in sorted(donnees_par_q.items()):
        chemin_q = dossier_parquet / f"{quinzaine}.parquet"
        est_courante = (quinzaine == quinzaine_courante)

        if chemin_q.exists() and not force and not est_courante:
            log.info(f"  {quinzaine} — Parquet existant, skip (quinzaine passée)")
            continue

        df_consolide = pd.concat(dfs, ignore_index=True)

        # Joindre META pour enrichir avec date_debut, date_fin_prevue, budget_jours, etc.
        if metas:
            df_meta_join = df_meta_global[
                [c for c in ["projet_id", "domaine", "entite_concerne", "effectifs",
                              "date_debut", "date_fin_prevue", "priorite",
                              "budget_jours", "description", "type"]
                 if c in df_meta_global.columns]
            ].drop_duplicates(subset=["projet_id"])
            df_consolide = df_consolide.merge(df_meta_join, on="projet_id", how="left",
                                              suffixes=("", "_meta"))

        df_consolide.to_parquet(chemin_q, index=False)
        resultats[quinzaine] = len(df_consolide)
        statut_str = "COURANTE" if est_courante else "nouvelle"
        log.info(f"  {quinzaine} [{statut_str}] → {chemin_q} ({len(df_consolide)} lignes)")

    return resultats


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    parser = argparse.ArgumentParser(description="Conversion fiches Excel → Parquet")
    parser.add_argument("--config",     default="config.yaml")
    parser.add_argument("--force",      action="store_true",
                        help="Retraiter toutes les quinzaines même passées")
    parser.add_argument("--quinzaine",  default=None,
                        help="Traiter une seule quinzaine (ex: T1_2026_R1)")
    args = parser.parse_args()

    config = _charger_config(args.config)
    paths  = config.get("paths", {})

    dossier_fiches  = paths.get("fiches_individuelles", "Monitoring/Fiches_individuelles")
    dossier_parquet = paths.get("parquet",              "storage/parquet")
    quinzaine_cour  = _quinzaine_courante(config)

    log.info(f"Quinzaine courante : {quinzaine_cour}")
    log.info(f"Dossier fiches     : {dossier_fiches}")
    log.info(f"Dossier parquet    : {dossier_parquet}")

    resultats = parser_fiches(
        dossier_fiches=dossier_fiches,
        dossier_parquet=dossier_parquet,
        quinzaine_courante=quinzaine_cour,
        force=args.force,
        quinzaine_unique=args.quinzaine,
    )

    if resultats:
        print(f"\n✓ {len(resultats)} quinzaine(s) traitée(s) :")
        for q, n in sorted(resultats.items()):
            print(f"  {q} → {n} ligne(s)")
    else:
        print("\nAucune quinzaine nouvelle à traiter.")
    print()


if __name__ == "__main__":
    main()
