"""
Pipeline principal d'ingestion des documents PDF.
Orchestre : extraction → classification → extraction champs → indexation ChromaDB.
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from tqdm import tqdm

from .config import PDF_DIR, REPORT_PATH, SCHEMAS
from .pdf_extractor import extract_text
from .document_classifier import classify_document
from .field_extractor import extract_fields
from .chroma_indexer import get_indexer

logger = logging.getLogger(__name__)


def process_pdf(pdf_path: Path) -> Optional[Dict]:
    """
    Traite un seul fichier PDF : extraction → classification → champs → retour dict.

    Returns:
        Dict avec toutes les infos, ou None si erreur fatale
    """
    try:
        filename = pdf_path.name

        # 1. Extraction du texte
        text = extract_text(pdf_path)
        if not text:
            logger.warning(f"Texte vide pour {filename}")

        # 2. Classification du type
        doc_type, classification_method = classify_document(filename, text)

        # 3. Extraction des champs
        fields = extract_fields(doc_type, text, filename)

        # 4. Métadonnées enrichies
        metadata = {
            **fields,
            "TYPE_DOCUMENT": doc_type,
            "FICHIER": filename,
            "TAILLE_TEXTE": len(text),
            "METHODE_CLASSIFICATION": classification_method,
            "DATE_INGESTION": datetime.now().isoformat(),
        }

        return {
            "id": pdf_path.stem,  # Nom sans extension = ID unique
            "text": text,
            "metadata": metadata,
            "filename": filename,
            "doc_type": doc_type,
            "fields": fields,
        }

    except Exception as e:
        logger.error(f"Erreur sur {pdf_path.name}: {e}", exc_info=True)
        return None


def ingest_directory(
    pdf_dir: Optional[Path] = None,
    batch_size: int = 32,
    overwrite: bool = True,
    save_report: bool = True,
) -> Dict:
    """
    Ingère tous les PDFs d'un répertoire dans ChromaDB.

    Args:
        pdf_dir: Répertoire contenant les PDFs (défaut: config.PDF_DIR)
        batch_size: Taille des batches pour l'indexation
        overwrite: Si True, réindexe les documents existants
        save_report: Si True, sauvegarde un rapport JSON

    Returns:
        Rapport d'ingestion avec statistiques
    """
    pdf_dir = pdf_dir or PDF_DIR
    pdf_files = sorted(pdf_dir.glob("*.pdf"))

    if not pdf_files:
        logger.warning(f"Aucun PDF trouvé dans {pdf_dir}")
        return {"total": 0, "success": 0, "errors": []}

    logger.info(f"Traitement de {len(pdf_files)} fichiers PDF...")

    # Phase 1 : Extraction et classification
    processed_docs = []
    errors = []
    type_counts: Dict[str, int] = {}

    for pdf_path in tqdm(pdf_files, desc="Extraction PDF", unit="doc"):
        result = process_pdf(pdf_path)
        if result is not None:
            processed_docs.append(result)
            doc_type = result["doc_type"]
            type_counts[doc_type] = type_counts.get(doc_type, 0) + 1
        else:
            errors.append(pdf_path.name)

    logger.info(f"Extraction terminée : {len(processed_docs)}/{len(pdf_files)} réussis")

    # Phase 2 : Indexation en batch dans ChromaDB
    indexer = get_indexer()
    
    docs_for_chroma = [
        {
            "id": doc["id"],
            "text": doc["text"],
            "metadata": doc["metadata"],
        }
        for doc in processed_docs
    ]

    logger.info(f"Indexation dans ChromaDB ({len(docs_for_chroma)} docs)...")
    added = indexer.add_documents_batch(docs_for_chroma, batch_size=batch_size)

    # Rapport final
    report = {
        "timestamp": datetime.now().isoformat(),
        "pdf_directory": str(pdf_dir),
        "total_fichiers": len(pdf_files),
        "traites_avec_succes": len(processed_docs),
        "indexes_dans_chroma": added,
        "erreurs": errors,
        "par_type": type_counts,
        "statistiques_chroma": indexer.get_stats(),
        "documents": [
            {
                "fichier": doc["filename"],
                "type": doc["doc_type"],
                "champs": doc["fields"],
            }
            for doc in processed_docs
        ],
    }

    if save_report:
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        logger.info(f"Rapport sauvegardé : {REPORT_PATH}")

    return report


def ingest_single_pdf(pdf_path: Path) -> Optional[Dict]:
    """
    Ingère un seul PDF dans ChromaDB.

    Returns:
        Dict avec les champs extraits, ou None si erreur
    """
    result = process_pdf(pdf_path)
    if result is None:
        return None

    indexer = get_indexer()
    success = indexer.add_document(
        doc_id=result["id"],
        text=result["text"],
        metadata=result["metadata"],
        overwrite=True,
    )

    if success:
        return result["fields"]
    return None
