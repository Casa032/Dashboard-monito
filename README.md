# Dashboard-monito


# Project Intelligence — Guide d'utilisation

## Structure du projet

```
project_intelligence/
├── run_pipeline.py         ← Point d'entrée unique ✅
├── config.yaml             ← Configuration centrale
│
├── excel_parser.py         ← Lit monito.xlsx → Parquet
├── storage.py              ← Lecture/écriture Parquet
├── rag_engine.py           ← Requêtes LLM sur les données
├── html_generator.py       ← Génère dashboard.html
├── pdf_builder.py          ← Génère les rapports PDF
│
├── data/
│   └── monito.xlsx         ← Fichier Excel unique (à remplir directement)
│
├── storage/
│   └── parquet/            ← Données stockées (généré automatiquement)
│
├── frontend/
│   └── dashboard.html      ← Dashboard généré
│
└── reporting/
    └── output/             ← PDFs générés
```

## Changements par rapport à l'ancienne structure

| Avant | Après |
|-------|-------|
| Fiches Excel individuelles dans `data/tables/` | ❌ Supprimé |
| `merger.py` pour fusionner les fiches | ❌ Supprimé |
| `monito.xlsx` généré par merger | ✅ `monito.xlsx` saisi directement |

Le pipeline est simplifié : **tu remplis `monito.xlsx` directement**, puis tu lances `run_pipeline.py`.

---

## Lancement rapide

### 1. Installer les dépendances
```bash
pip install pandas pyarrow openpyxl pyyaml reportlab
```

### 2. Remplir le fichier Excel
- Ouvre `data/monito.xlsx`
- Remplis tes données de quinzaine dans les sheets correspondantes
- La sheet `META` contient le référentiel des projets

### 3. Lancer le pipeline
```bash
# Pipeline complet (ingestion + dashboard)
python run_pipeline.py

# Avec génération PDF en plus
python run_pipeline.py --pdf

# Pour une quinzaine spécifique
python run_pipeline.py --quinzaine Q2_2025_S1

# Regénérer seulement le dashboard (sans relire le Excel)
python run_pipeline.py --skip-ingest

# Avec le chat LLM pré-généré (nécessite Ollama)
python run_pipeline.py --llm
```

---

## Structure du fichier Excel `monito.xlsx`

### Sheet META (référentiel projets)
| projet_id | projet_nom | domaine | date_debut | date_fin_prevue | budget_jours | client_interne | description |
|-----------|-----------|---------|------------|-----------------|--------------|----------------|-------------|

### Sheets de quinzaine (ex: `Q1_2025_S1`, `Q2_2025_S1`...)
| projet_id | projet_nom | domaine | phase | effectifs | responsable_principal | statut | avancement_pct | livrable_quinzaine | livrable_statut | decisions | actions_a_mener | actions_responsable | actions_echeance | risques | risque_niveau | points_blocage | commentaire_libre |

**Valeurs de statut acceptées :** `ON_TRACK` · `AT_RISK` · `LATE` · `DONE` · `ON_HOLD`

### Sheets ignorées automatiquement
`DICTIONNAIRE`, `TEMPLATE`, `NOTES`

---

## Utilisation individuelle des modules

```bash
# Ingestion seule
python excel_parser.py

# Dashboard seul (données déjà en Parquet)
python html_generator.py

# PDF seul
python pdf_builder.py --type quinzaine
python pdf_builder.py --type projet --projet PROJ-001
python pdf_builder.py --type delta --q-avant Q1_2025_S1 --q-apres Q2_2025_S1

# Chat LLM en ligne de commande
python rag_engine.py --question "quels projets sont en retard ?"
python rag_engine.py  # mode interactif
```

---

## Configuration (`config.yaml`)

```yaml
paths:
  excel_source:  "data/monito.xlsx"     # Ton fichier Excel
  parquet_dir:   "storage/parquet"      # Stockage interne
  dashboard_out: "frontend/dashboard.html"
  pdf_out:       "reporting/output"

llm:
  endpoint: "http://localhost:11434/v1"  # Ollama local
  model:    "mistral"
```
