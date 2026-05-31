"""
API FastAPI pour le système RAG.
Expose des endpoints pour l'ingestion, la recherche et la consultation des documents.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .config import API_TITLE, API_VERSION, PDF_DIR, DOC_TYPES
from .chroma_indexer import get_indexer
from .pipeline import ingest_directory, ingest_single_pdf

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ─── Application FastAPI ────────────────────────────────────────────────────

app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description="API RAG pour l'extraction et la recherche de documents financiers (Factures, BC, BL, Devis)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Modèles Pydantic ────────────────────────────────────────────────────────

class SearchRequest(BaseModel):
    query: str
    n_results: int = 10
    doc_type: Optional[str] = None
    filters: Optional[Dict[str, str]] = None


class SearchResult(BaseModel):
    id: str
    score: float
    metadata: Dict[str, Any]
    text_preview: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


class IngestResponse(BaseModel):
    message: str
    total_fichiers: int
    traites: int
    par_type: Dict[str, int]
    erreurs: List[str]


class StatsResponse(BaseModel):
    total_documents: int
    par_type: Dict[str, int]
    collection: str
    chroma_dir: str


# ─── État de l'ingestion ─────────────────────────────────────────────────────

ingestion_status = {"running": False, "progress": "", "last_report": None}


# ─── Endpoints ───────────────────────────────────────────────────────────────

@app.get("/", tags=["Général"])
async def root():
    """Informations de base sur l'API."""
    return {
        "titre": API_TITLE,
        "version": API_VERSION,
        "endpoints": {
            "stats": "/stats",
            "recherche": "/search",
            "ingestion": "/ingest",
            "documents": "/documents",
            "upload": "/upload",
        },
    }


@app.get("/stats", response_model=StatsResponse, tags=["Général"])
async def get_stats():
    """Statistiques de la base ChromaDB."""
    try:
        indexer = get_indexer()
        stats = indexer.get_stats()
        return StatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", response_model=SearchResponse, tags=["Recherche"])
async def search_documents(request: SearchRequest):
    """
    Recherche sémantique dans les documents.
    
    Exemples de requêtes :
    - "factures du fournisseur SOGEA"
    - "bons de commande avec montant supérieur à 10000"
    - "livraisons de janvier 2024"
    """
    try:
        indexer = get_indexer()
        
        results = indexer.query(
            query_text=request.query,
            n_results=request.n_results,
            doc_type=request.doc_type,
            where=request.filters,
        )
        
        formatted = [
            SearchResult(
                id=r["id"],
                score=round(r["score"], 4),
                metadata=r["metadata"],
                text_preview=r["text"][:300] + "..." if len(r["text"]) > 300 else r["text"],
            )
            for r in results
        ]
        
        return SearchResponse(
            query=request.query,
            results=formatted,
            total=len(formatted),
        )
    except Exception as e:
        logger.error(f"Erreur recherche: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/search", tags=["Recherche"])
async def search_get(
    q: str = Query(..., description="Requête de recherche"),
    type: Optional[str] = Query(None, description="Type de document (FACTURE, BON_DE_COMMANDE, BON_DE_LIVRAISON, DEVIS)"),
    n: int = Query(10, description="Nombre de résultats"),
):
    """Recherche simplifiée via GET."""
    request = SearchRequest(query=q, doc_type=type, n_results=n)
    return await search_documents(request)


@app.post("/ingest", response_model=IngestResponse, tags=["Ingestion"])
async def ingest_documents(background_tasks: BackgroundTasks):
    """
    Lance l'ingestion de tous les PDFs du répertoire Documents.
    S'exécute en arrière-plan. Consulter /ingest/status pour le suivi.
    """
    if ingestion_status["running"]:
        raise HTTPException(status_code=409, detail="Une ingestion est déjà en cours")

    def run_ingestion():
        ingestion_status["running"] = True
        ingestion_status["progress"] = "Démarrage..."
        try:
            report = ingest_directory(pdf_dir=PDF_DIR, save_report=True)
            ingestion_status["last_report"] = report
            ingestion_status["progress"] = "Terminé"
        except Exception as e:
            ingestion_status["progress"] = f"Erreur: {e}"
            logger.error(f"Erreur ingestion: {e}", exc_info=True)
        finally:
            ingestion_status["running"] = False

    background_tasks.add_task(run_ingestion)

    return IngestResponse(
        message="Ingestion lancée en arrière-plan. Consultez /ingest/status",
        total_fichiers=0,
        traites=0,
        par_type={},
        erreurs=[],
    )


@app.post("/ingest/sync", tags=["Ingestion"])
async def ingest_documents_sync():
    """
    Lance l'ingestion synchrone (attend la fin avant de répondre).
    Adapté pour les petits volumes ou les tests.
    """
    if ingestion_status["running"]:
        raise HTTPException(status_code=409, detail="Une ingestion est déjà en cours")

    ingestion_status["running"] = True
    try:
        report = ingest_directory(pdf_dir=PDF_DIR, save_report=True)
        ingestion_status["last_report"] = report
        return {
            "message": "Ingestion terminée",
            "rapport": {
                "total_fichiers": report["total_fichiers"],
                "traites": report["traites_avec_succes"],
                "indexes": report["indexes_dans_chroma"],
                "par_type": report["par_type"],
                "erreurs": report["erreurs"],
            },
        }
    finally:
        ingestion_status["running"] = False


@app.get("/ingest/status", tags=["Ingestion"])
async def get_ingest_status():
    """Statut de l'ingestion en cours ou du dernier rapport."""
    return {
        "en_cours": ingestion_status["running"],
        "progression": ingestion_status["progress"],
        "dernier_rapport": (
            {
                k: v
                for k, v in (ingestion_status["last_report"] or {}).items()
                if k != "documents"
            }
            if ingestion_status["last_report"]
            else None
        ),
    }


@app.get("/documents", tags=["Documents"])
async def list_documents(
    type: Optional[str] = Query(None, description="Filtrer par type"),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
):
    """Liste les documents indexés avec pagination."""
    try:
        indexer = get_indexer()
        result = indexer.list_documents(doc_type=type, limit=limit, offset=offset)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/{doc_id}", tags=["Documents"])
async def get_document(doc_id: str):
    """Récupère un document par son ID (nom du fichier sans extension)."""
    indexer = get_indexer()
    doc = indexer.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' non trouvé")
    return doc


@app.delete("/documents/{doc_id}", tags=["Documents"])
async def delete_document(doc_id: str):
    """Supprime un document de ChromaDB."""
    indexer = get_indexer()
    success = indexer.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' non trouvé")
    return {"message": f"Document '{doc_id}' supprimé"}


@app.post("/upload", tags=["Documents"])
async def upload_and_ingest(file: UploadFile = File(...)):
    """
    Upload un PDF et l'ingère immédiatement dans ChromaDB.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Seuls les fichiers PDF sont acceptés")

    # Sauvegarder temporairement dans le répertoire PDF
    save_path = PDF_DIR / file.filename
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    try:
        result = ingest_single_pdf(save_path)
        if result is None:
            raise HTTPException(status_code=422, detail="Impossible de traiter ce PDF")

        return {
            "message": f"PDF '{file.filename}' ingéré avec succès",
            "champs_extraits": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/types", tags=["Général"])
async def get_document_types():
    """Liste les types de documents supportés et leurs champs."""
    from .config import SCHEMAS
    return {
        "types_supportes": list(DOC_TYPES.keys()),
        "schemas": SCHEMAS,
    }
