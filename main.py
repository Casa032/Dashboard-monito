"""
api/main.py
===========
Serveur FastAPI — expose le chat LLM via POST /api/chat.

Le dashboard HTML envoie ses questions ici en temps réel.
RagEngine construit le contexte depuis le Parquet et appelle Qwen.

Lancement :
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
    # ou depuis la racine du projet :
    python -m uvicorn api.main:app --port 8000 --reload

Dépendances :
    pip install fastapi uvicorn

Variables d'environnement (optionnel, sinon lu depuis config.yaml) :
    CONFIG_PATH   : chemin vers config.yaml  (défaut : "config.yaml")
    CHAT_API_PORT : port d'écoute            (défaut : 8000)
"""

import os
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Support structure plate ou dossiers
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from query.rag_engine import RagEngine
except ImportError:
    from rag_engine import RagEngine  # type: ignore

# ── Config ─────────────────────────────────────────────────────────────────────

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Project Intelligence — Chat API",
    description="Endpoint LLM pour le dashboard HTML de monitoring projets.",
    version="1.0.0",
)

# CORS : autorise le dashboard HTML (fichier local ou servi depuis n'importe où)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # restreindre en production si nécessaire
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

# Initialisation unique du moteur RAG au démarrage
try:
    rag = RagEngine(CONFIG_PATH)
    log.info(f"RagEngine initialisé — config : {CONFIG_PATH}")
except Exception as e:
    log.error(f"Impossible d'initialiser RagEngine : {e}")
    rag = None


# ── Schémas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str
    quinzaine: str | None = None   # None → dernière quinzaine disponible


class ChatResponse(BaseModel):
    reponse: str
    quinzaine: str | None = None
    source: str = "llm"            # "llm" | "fallback"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "Project Intelligence Chat API"}


@app.get("/health")
def health():
    return {"status": "ok", "rag_ready": rag is not None}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Reçoit une question en langage naturel et retourne une réponse LLM
    basée sur les données de monitoring de la quinzaine demandée.

    Corps JSON attendu :
        { "question": "quels projets sont en retard ?", "quinzaine": "Q1_2025_S2" }

    Réponse :
        { "reponse": "...", "quinzaine": "Q1_2025_S2", "source": "llm" }
    """
    if not req.question or not req.question.strip():
        raise HTTPException(status_code=400, detail="Le champ 'question' est requis.")

    if rag is None:
        raise HTTPException(
            status_code=503,
            detail="RagEngine non initialisé — vérifie config.yaml et les données Parquet.",
        )

    log.info(f"Chat — quinzaine: {req.quinzaine or 'auto'} — question: {req.question[:80]}")

    try:
        reponse = rag.query(req.question, quinzaine=req.quinzaine)
        # Détecter si le LLM a renvoyé une erreur de connexion
        source = "fallback" if reponse.startswith("[") else "llm"
        return ChatResponse(reponse=reponse, quinzaine=req.quinzaine, source=source)

    except Exception as e:
        log.error(f"Erreur lors du traitement de la question : {e}")
        raise HTTPException(status_code=500, detail=f"Erreur interne : {e}")


# ── Point d'entrée standalone ──────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("CHAT_API_PORT", 8000))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=True)
