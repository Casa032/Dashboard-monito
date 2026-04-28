"""
storage.py
==========
Persistance Parquet des données issues du pipeline Excel.

Colonnes supportées avec fallbacks :
    projet_id    ← aussi ref_sujet
    projet_nom   ← aussi sujet
    decisions    ← aussi actions_realises
"""

import pandas as pd
import yaml
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S")
log = logging.getLogger(__name__)


def _cfg(config_path="config.yaml") -> dict:
    p = Path(config_path)
    return yaml.safe_load(p.read_text(encoding="utf-8")) if p.exists() else {}


def _col(df: pd.DataFrame, *noms) -> str | None:
    for n in noms:
        if n in df.columns:
            return n
    return None


def _id_col(df: pd.DataFrame) -> str:
    return _col(df, "projet_id", "ref_sujet") or "projet_id"


def _nom_col(df: pd.DataFrame) -> str:
    return _col(df, "projet_nom", "sujet") or "projet_nom"


def _normaliser(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.copy()
    if "projet_id" not in df.columns and "ref_sujet" in df.columns:
        df["projet_id"] = df["ref_sujet"]
    if "projet_nom" not in df.columns and "sujet" in df.columns:
        df["projet_nom"] = df["sujet"]
    return df


class StorageManager:
    def __init__(self, config_path="config.yaml"):
        cfg         = _cfg(config_path)
        paths       = cfg.get("paths", {})
        storage_cfg = cfg.get("storage", {})

        self.parquet_dir = Path(
            paths.get("parquet_dir") or paths.get("parquet") or "storage/parquet"
        )
        self.parquet_dir.mkdir(parents=True, exist_ok=True)

        self.fq = self.parquet_dir / storage_cfg.get("fichier_quinzaines", "quinzaines.parquet")
        self.fm = self.parquet_dir / storage_cfg.get("fichier_meta",       "meta_projets.parquet")
        self.fa = self.parquet_dir / "agenda.parquet"

        log.info(f"StorageManager — Parquet — dossier : {self.parquet_dir}")

    # ── Écriture ──────────────────────────────────────────────────────────────

    def sauvegarder_quinzaine(self, df: pd.DataFrame, nom_quinzaine: str) -> bool:
        if df is None or df.empty:
            log.warning(f"DataFrame vide pour '{nom_quinzaine}'")
            return False
        try:
            df = _normaliser(df)
            if "quinzaine" not in df.columns:
                df["quinzaine"] = nom_quinzaine
            if self.fq.exists():
                existant = _normaliser(pd.read_parquet(self.fq))
                existant = existant[existant["quinzaine"] != nom_quinzaine]
                df_final = pd.concat([existant, df], ignore_index=True)
            else:
                df_final = df.copy()
            df_final.to_parquet(self.fq, index=False)
            log.info(f"'{nom_quinzaine}' — {len(df)} ligne(s)")
            return True
        except Exception as e:
            log.error(f"Erreur sauvegarde '{nom_quinzaine}' : {e}")
            return False

    def sauvegarder_meta(self, df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            log.warning("DataFrame META vide")
            return False
        try:
            _normaliser(df).to_parquet(self.fm, index=False)
            log.info(f"META — {len(df)} projet(s)")
            return True
        except Exception as e:
            log.error(f"Erreur sauvegarde META : {e}")
            return False

    def sauvegarder_agenda(self, df: pd.DataFrame) -> bool:
        if df is None or df.empty:
            log.warning("DataFrame AGENDA vide")
            return False
        try:
            df.to_parquet(self.fa, index=False)
            log.info(f"AGENDA — {len(df)} événement(s)")
            return True
        except Exception as e:
            log.error(f"Erreur sauvegarde AGENDA : {e}")
            return False

    # ── Lecture ───────────────────────────────────────────────────────────────

    def charger_quinzaines(self, quinzaines=None, projets=None) -> pd.DataFrame:
        if not self.fq.exists():
            log.warning("Aucune donnée — lance run_pipeline.py d'abord")
            return pd.DataFrame()
        df = _normaliser(pd.read_parquet(self.fq))
        if quinzaines:
            df = df[df["quinzaine"].isin(quinzaines)]
        if projets:
            col = _id_col(df)
            df  = df[df[col].isin(projets)]
        return df.reset_index(drop=True)

    def charger_meta(self) -> pd.DataFrame:
        # Cherche d'abord meta_projets.parquet, puis meta.parquet (produit par excel_parser)
        for chemin in [self.fm, self.parquet_dir / "meta.parquet"]:
            if chemin.exists():
                return _normaliser(pd.read_parquet(chemin))
        # Fallback : dériver depuis les quinzaines
        df = self.charger_quinzaines()
        if df.empty:
            return pd.DataFrame()
        col_id  = _id_col(df)
        col_nom = _nom_col(df)
        meta_cols = [c for c in [col_id, col_nom, "domaine", "entite_concerne",
                                  "effectifs", "responsable_principal", "date_debut",
                                  "date_fin_prevue", "priorite", "budget_jours",
                                  "description", "type"]
                     if c and c in df.columns]
        return df[meta_cols].drop_duplicates(subset=[col_id]).reset_index(drop=True)

    def charger_agenda(self) -> pd.DataFrame:
        """
        Charge les événements de l'AGENDA.
        Retourne un DataFrame trié par date avec colonnes :
            date, titre, type, description, projet_ref
        """
        if self.fa.exists():
            df = pd.read_parquet(self.fa)
            return df.sort_values("date").reset_index(drop=True)
        # Fallback : cherche agenda.parquet produit directement par excel_parser
        alt = self.parquet_dir / "agenda.parquet"
        if alt.exists():
            df = pd.read_parquet(alt)
            return df.sort_values("date").reset_index(drop=True)
        return pd.DataFrame()

    # ── Requêtes analytiques ──────────────────────────────────────────────────

    def projet(self, projet_id: str) -> pd.DataFrame:
        df  = self.charger_quinzaines()
        if df.empty:
            return df
        col = _id_col(df)
        return df[df[col] == projet_id].sort_values("quinzaine").reset_index(drop=True)

    def derniere_quinzaine(self) -> pd.DataFrame:
        df = self.charger_quinzaines()
        if df.empty:
            return df
        return df[df["quinzaine"] == df["quinzaine"].max()].reset_index(drop=True)

    def kpis(self, quinzaine=None) -> dict:
        df = self.charger_quinzaines(quinzaines=[quinzaine]) if quinzaine \
             else self.derniere_quinzaine()
        if df.empty:
            return {}
        pct      = pd.to_numeric(df["avancement_pct"], errors="coerce")
        col_dec  = _col(df, "decisions", "actions_realises")
        nb_dec   = int(df[col_dec].apply(
            lambda x: bool(str(x).strip()) if pd.notna(x) else False
        ).sum()) if col_dec else 0
        col_bloc = _col(df, "points_blocage")
        nb_bloc  = int(df[col_bloc].apply(
            lambda x: bool(str(x).strip()) if pd.notna(x) else False
        ).sum()) if col_bloc else 0
        return {
            "quinzaine":         str(df["quinzaine"].iloc[0]),
            "nb_projets_actifs": int((~df["statut"].isin(["DONE", "ON_HOLD"])).sum()),
            "nb_done":           int((df["statut"] == "DONE").sum()),
            "nb_on_hold":        int((df["statut"] == "ON_HOLD").sum()),
            "nb_en_retard":      int((df["statut"] == "LATE").sum()),
            "nb_at_risk":        int((df["statut"] == "AT_RISK").sum()),
            "avancement_moyen":  round(float(pct.mean()), 1),
            "nb_decisions":      nb_dec,
            "nb_blocages":       nb_bloc,
        }

    def projets_par_statut(self, quinzaine=None) -> dict:
        df = self.charger_quinzaines(quinzaines=[quinzaine]) if quinzaine \
             else self.derniere_quinzaine()
        return {} if df.empty else df["statut"].value_counts().to_dict()

    def delta_quinzaines(self, q_avant: str, q_apres: str) -> pd.DataFrame:
        df = self.charger_quinzaines(quinzaines=[q_avant, q_apres])
        if df.empty:
            return pd.DataFrame()
        col_id  = _id_col(df)
        col_nom = _nom_col(df)
        avant = df[df["quinzaine"] == q_avant][
            [col_id, col_nom, "statut", "avancement_pct"]
        ].rename(columns={col_id: "projet_id", col_nom: "projet_nom",
                           "statut": "statut_avant", "avancement_pct": "avancement_avant"})
        apres = df[df["quinzaine"] == q_apres][
            [col_id, "statut", "avancement_pct"]
        ].rename(columns={col_id: "projet_id",
                           "statut": "statut_apres", "avancement_pct": "avancement_apres"})
        m = avant.merge(apres, on="projet_id", how="outer")
        m["avancement_avant"] = pd.to_numeric(m["avancement_avant"], errors="coerce")
        m["avancement_apres"] = pd.to_numeric(m["avancement_apres"], errors="coerce")
        m["delta_avancement"] = m["avancement_apres"] - m["avancement_avant"]
        return m.sort_values("delta_avancement").reset_index(drop=True)

    def lister_quinzaines(self) -> list:
        df = self.charger_quinzaines()
        return sorted(df["quinzaine"].unique().tolist()) if not df.empty else []

    def lister_projets(self) -> list:
        df = self.derniere_quinzaine()
        if df.empty:
            return []
        col_id  = _id_col(df)
        col_nom = _nom_col(df)
        cols    = [c for c in [col_id, col_nom, "statut", "avancement_pct",
                                "responsable_principal"] if c in df.columns]
        result  = df[cols].to_dict(orient="records")
        for r in result:
            if "projet_id" not in r and "ref_sujet" in r:
                r["projet_id"] = r["ref_sujet"]
            if "projet_nom" not in r and "sujet" in r:
                r["projet_nom"] = r["sujet"]
        return result

    def infos(self) -> dict:
        r = {
            "moteur": "Parquet", "dossier": str(self.parquet_dir),
            "quinzaines_existe": self.fq.exists(),
            "meta_existe":       self.fm.exists(),
            "agenda_existe":     self.fa.exists(),
            "quinzaines": [], "nb_lignes": 0, "nb_projets": 0,
        }
        if self.fq.exists():
            df = _normaliser(pd.read_parquet(self.fq))
            col_id = _id_col(df)
            r["quinzaines"] = sorted(df["quinzaine"].unique().tolist())
            r["nb_lignes"]  = len(df)
            r["nb_projets"] = df[col_id].nunique() if col_id in df.columns else 0
        return r
