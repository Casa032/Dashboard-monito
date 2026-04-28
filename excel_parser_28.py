"""
excel_parser.py
===============
Lecture des fiches individuelles Excel et consolidation vers Parquet.

Structure attendue dans chaque fiche :
    - Feuille META       : infos statiques du projet
    - Feuilles quinzaine : T1_2026_R1 ... T4_2099_R6
    - Feuille AGENDA     : événements (dans la fiche du manager uniquement)
    - Feuilles ignorées  : TEMPLATE, DICTIONNAIRE, tout ce qui ne matche pas

Stratégie incrémentale :
    - Quinzaines passées → Parquet figé, jamais relu sauf si --force
    - Quinzaine courante → toujours relue (saisie encore en cours)

Usage :
    python excel_parser.py
    python excel_parser.py --force
    python excel_parser.py --quinzaine T1_2026_R1
    python excel_parser.py --config config.yaml
"""

import re
import logging
import argparse
import yaml
import pandas as pd
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

PATTERN_QUINZAINE = re.compile(r"^T[1-4]_\d{4}_R[1-6]$")

COLONNES_FEUILLE = [
    "ref_sujet", "sujet", "phase", "statut", "avancement_pct",
    "livrable_quinzaine", "livrable_statut",
    "actions_realises", "actions_a_mener", "actions_echeance",
    "charge_a_prevoir", "risques", "risque_niveau",
    "points_blocage", "commentaire",
]

COLONNES_META = [
    "type", "ref_sujet", "sujet", "domaine", "entite_concerne",
    "effectifs", "responsable_principal",
    "date_debut", "date_fin_prevue",
    "priorite", "budget_jours", "description",
]

COLONNES_AGENDA = ["date", "titre", "type", "description", "projet_ref"]
TYPES_AGENDA_VALIDES = {"REUNION", "LIVRAISON", "ACTUALITE", "JALON", "AUTRE"}

RENAME_FEUILLE = {
    "sujet":       "projet_nom",
    "ref_sujet":   "projet_id",
    "commentaire": "commentaire_libre",
}
RENAME_META = {
    "sujet":     "projet_nom",
    "ref_sujet": "projet_id",
}


def _charger_config(config_path: str) -> dict:
    p = Path(config_path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def _quinzaine_courante(config: dict) -> str | None:
    q = config.get("quinzaine_courante")
    if q:
        return q
    now = datetime.now()
    trimestre = (now.month - 1) // 3 + 1
    mois_dans_trim = (now.month - 1) % 3 + 1
    rang = 1 if mois_dans_trim == 1 else (3 if mois_dans_trim == 2 else 5)
    if now.day > 15:
        rang += 1
    return f"T{trimestre}_{now.year}_R{min(rang, 6)}"


def _est_feuille_quinzaine(nom: str) -> bool:
    return bool(PATTERN_QUINZAINE.match(nom))


def _lire_meta(wb_path: Path, xl: pd.ExcelFile) -> pd.DataFrame:
    if "META" not in xl.sheet_names:
        log.warning(f"{wb_path.name} — pas de feuille META")
        return pd.DataFrame()
    try:
        df = xl.parse("META", dtype=str)
    except Exception as e:
        log.error(f"{wb_path.name} — erreur lecture META : {e}")
        return pd.DataFrame()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    cols = [c for c in COLONNES_META if c in df.columns]
    df = df[cols].copy()
    if "ref_sujet" in df.columns:
        df = df[df["ref_sujet"].notna() & (df["ref_sujet"].str.strip() != "")]
    df = df.rename(columns=RENAME_META)
    df["source_fichier"] = wb_path.name
    return df


def _lire_agenda(wb_path: Path, xl: pd.ExcelFile) -> pd.DataFrame:
    """
    Lit la feuille AGENDA si elle existe.
    Retourne DataFrame vide si absente ou vide.
    Colonnes : date (YYYY-MM-DD), titre, type, description, projet_ref
    """
    if "AGENDA" not in xl.sheet_names:
        return pd.DataFrame()
    try:
        df = xl.parse("AGENDA", dtype=str)
    except Exception as e:
        log.error(f"{wb_path.name} — erreur lecture AGENDA : {e}")
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    if "date" not in df.columns or "titre" not in df.columns:
        log.warning(f"{wb_path.name} — AGENDA sans colonnes date/titre, ignoré")
        return pd.DataFrame()

    df = df[df["date"].notna() & df["titre"].notna()].copy()
    df = df[df["date"].str.strip() != ""]
    df = df[df["titre"].str.strip() != ""]
    if df.empty:
        return pd.DataFrame()

    # Normaliser type
    if "type" in df.columns:
        df["type"] = df["type"].apply(
            lambda v: str(v).strip().upper() if pd.notna(v) else "AUTRE"
        )
        df["type"] = df["type"].apply(
            lambda v: v if v in TYPES_AGENDA_VALIDES else "AUTRE"
        )
    else:
        df["type"] = "AUTRE"

    # Parser les dates
    def _parse_date(v):
        v = str(v).strip()
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
            try:
                return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        log.warning(f"Date AGENDA non parsée : {v}")
        return None

    df["date"] = df["date"].apply(_parse_date)
    df = df[df["date"].notna()].copy()

    # Garder colonnes utiles + compléter manquantes
    cols = [c for c in COLONNES_AGENDA if c in df.columns]
    df = df[cols].copy()
    for col in COLONNES_AGENDA:
        if col not in df.columns:
            df[col] = ""

    df["source_fichier"] = wb_path.name
    log.info(f"{wb_path.name} — AGENDA : {len(df)} événement(s)")
    return df


def _lire_feuille_quinzaine(wb_path: Path, xl: pd.ExcelFile,
                             nom_feuille: str, responsable: str) -> pd.DataFrame:
    try:
        df = xl.parse(nom_feuille, dtype=str)
    except Exception as e:
        log.error(f"{wb_path.name}/{nom_feuille} — erreur : {e}")
        return pd.DataFrame()
    if df.empty:
        return pd.DataFrame()

    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    if "ref_sujet" not in df.columns:
        log.warning(f"{wb_path.name}/{nom_feuille} — colonne ref_sujet absente")
        return pd.DataFrame()

    df = df[df["ref_sujet"].notna() & (df["ref_sujet"].str.strip() != "")].copy()
    if df.empty:
        return pd.DataFrame()

    cols = [c for c in COLONNES_FEUILLE if c in df.columns]
    df = df[cols].copy()

    if "avancement_pct" in df.columns:
        def _norm_pct(v):
            try:
                f = float(str(v).replace(",", ".").replace("%", "").strip())
                return round(f * 100 if f <= 1.0 else f)
            except (ValueError, TypeError):
                return None
        df["avancement_pct"] = df["avancement_pct"].apply(_norm_pct)

    if "statut" in df.columns:
        STATUT_MAP = {
            "en cours": "ON_TRACK", "a risque": "AT_RISK", "à risque": "AT_RISK",
            "en retard": "LATE", "terminé": "DONE", "termine": "DONE",
            "stand by": "ON_HOLD", "on hold": "ON_HOLD",
            "on_track": "ON_TRACK", "at_risk": "AT_RISK",
            "late": "LATE", "done": "DONE", "on_hold": "ON_HOLD",
        }
        df["statut"] = df["statut"].apply(
            lambda v: STATUT_MAP.get(str(v).strip().lower(),
                                     str(v).strip().upper() if pd.notna(v) else "ON_TRACK")
        )

    df = df.rename(columns=RENAME_FEUILLE)
    df["quinzaine"]             = nom_feuille
    df["responsable_principal"] = responsable
    df["source_fichier"]        = wb_path.name
    return df


def _extraire_responsable(wb_path: Path) -> str:
    stem = re.sub(r"(?i)^fiches?_", "", wb_path.stem)
    return stem.replace("_", " ").strip()


def parser_fiches(
    dossier_fiches: str | Path,
    dossier_parquet: str | Path,
    quinzaine_courante: str | None = None,
    force: bool = False,
    quinzaine_unique: str | None = None,
) -> dict[str, int]:
    """
    Parcourt tous les fichiers Excel, produit :
        - meta.parquet
        - agenda.parquet  (si feuille AGENDA trouvée)
        - T1_2026_R1.parquet, etc.
    """
    dossier_fiches  = Path(dossier_fiches)
    dossier_parquet = Path(dossier_parquet)
    dossier_parquet.mkdir(parents=True, exist_ok=True)

    if not dossier_fiches.exists():
        log.error(f"Dossier fiches introuvable : {dossier_fiches}")
        return {}

    fichiers = [
        f for f in dossier_fiches.rglob("*.xls*")
        if not f.name.startswith("~$") and f.suffix in (".xlsx", ".xlsm", ".xls")
    ]
    if not fichiers:
        log.warning(f"Aucun fichier Excel dans {dossier_fiches}")
        return {}

    log.info(f"{len(fichiers)} fiche(s) trouvée(s)")

    donnees_par_q: dict[str, list[pd.DataFrame]] = {}
    metas:   list[pd.DataFrame] = []
    agendas: list[pd.DataFrame] = []

    for fichier in sorted(fichiers):
        responsable = _extraire_responsable(fichier)
        log.info(f"  Lecture : {fichier.name} ({responsable})")
        try:
            xl = pd.ExcelFile(fichier, engine="openpyxl")
        except Exception as e:
            log.error(f"  Impossible d'ouvrir {fichier.name} : {e}")
            continue

        df_meta = _lire_meta(fichier, xl)
        if not df_meta.empty:
            metas.append(df_meta)

        df_agenda = _lire_agenda(fichier, xl)
        if not df_agenda.empty:
            agendas.append(df_agenda)

        feuilles_q = [s for s in xl.sheet_names if _est_feuille_quinzaine(s)]
        for nom_feuille in feuilles_q:
            if quinzaine_unique and nom_feuille != quinzaine_unique:
                continue
            df_q = _lire_feuille_quinzaine(fichier, xl, nom_feuille, responsable)
            if not df_q.empty:
                donnees_par_q.setdefault(nom_feuille, []).append(df_q)

    df_meta_global = pd.DataFrame()
    if metas:
        df_meta_global = pd.concat(metas, ignore_index=True).drop_duplicates(
            subset=["projet_id"], keep="last"
        )
        (dossier_parquet / "meta.parquet").parent.mkdir(parents=True, exist_ok=True)
        df_meta_global.to_parquet(dossier_parquet / "meta.parquet", index=False)
        log.info(f"META → meta.parquet ({len(df_meta_global)} projets)")

    if agendas:
        df_ag = pd.concat(agendas, ignore_index=True).sort_values("date").reset_index(drop=True)
        df_ag.to_parquet(dossier_parquet / "agenda.parquet", index=False)
        log.info(f"AGENDA → agenda.parquet ({len(df_ag)} événements)")

    resultats = {}
    for quinzaine, dfs in sorted(donnees_par_q.items()):
        chemin_q    = dossier_parquet / f"{quinzaine}.parquet"
        est_courante = (quinzaine == quinzaine_courante)

        if chemin_q.exists() and not force and not est_courante:
            log.info(f"  {quinzaine} — skip (passée)")
            continue

        df_c = pd.concat(dfs, ignore_index=True)

        if not df_meta_global.empty:
            cols_join = [c for c in ["projet_id", "domaine", "entite_concerne",
                                     "effectifs", "date_debut", "date_fin_prevue",
                                     "priorite", "budget_jours", "description", "type"]
                         if c in df_meta_global.columns]
            df_join = df_meta_global[cols_join].drop_duplicates(subset=["projet_id"])
            df_c = df_c.merge(df_join, on="projet_id", how="left", suffixes=("", "_meta"))

        df_c.to_parquet(chemin_q, index=False)
        resultats[quinzaine] = len(df_c)
        log.info(f"  {quinzaine} [{'COURANTE' if est_courante else 'nouvelle'}] → {len(df_c)} lignes")

    return resultats


def main():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%Y-%m-%d %H:%M:%S")
    parser = argparse.ArgumentParser()
    parser.add_argument("--config",    default="config.yaml")
    parser.add_argument("--force",     action="store_true")
    parser.add_argument("--quinzaine", default=None)
    args = parser.parse_args()

    config = _charger_config(args.config)
    paths  = config.get("paths", {})

    resultats = parser_fiches(
        dossier_fiches=paths.get("fiches_individuelles", "Monitoring/Fiches_individuelles"),
        dossier_parquet=paths.get("parquet_dir") or paths.get("parquet", "storage/parquet"),
        quinzaine_courante=_quinzaine_courante(config),
        force=args.force,
        quinzaine_unique=args.quinzaine,
    )

    if resultats:
        print(f"\n✓ {len(resultats)} quinzaine(s) :")
        for q, n in sorted(resultats.items()):
            print(f"  {q} → {n} ligne(s)")
    else:
        print("\nAucune quinzaine nouvelle.")
    print()


if __name__ == "__main__":
    main()
