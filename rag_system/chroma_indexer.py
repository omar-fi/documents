"""
Indexation des documents dans ChromaDB.
Gère les embeddings sentence-transformers et le stockage des métadonnées.
"""
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

from .config import (
    CHROMA_DIR,
    CHROMA_COLLECTION_NAME,
    EMBEDDING_MODEL,
)

logger = logging.getLogger(__name__)


class ChromaIndexer:
    """Gère l'indexation et la recherche dans ChromaDB."""

    def __init__(self):
        self._client: Optional[chromadb.PersistentClient] = None
        self._collection = None
        self._embedding_model: Optional[SentenceTransformer] = None

    def _get_client(self) -> chromadb.PersistentClient:
        if self._client is None:
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            logger.info(f"ChromaDB initialisé à : {CHROMA_DIR}")
        return self._client

    def _get_collection(self):
        if self._collection is None:
            client = self._get_client()
            self._collection = client.get_or_create_collection(
                name=CHROMA_COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"Collection '{CHROMA_COLLECTION_NAME}' prête ({self._collection.count()} docs)")
        return self._collection

    def _get_embedding_model(self) -> SentenceTransformer:
        if self._embedding_model is None:
            logger.info(f"Chargement du modèle d'embedding : {EMBEDDING_MODEL}")
            self._embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        return self._embedding_model

    def embed(self, texts: List[str]) -> List[List[float]]:
        """Génère les embeddings pour une liste de textes."""
        model = self._get_embedding_model()
        embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return embeddings.tolist()

    def _clean_metadata(self, metadata: Dict[str, Any]) -> Dict[str, str]:
        """Nettoie les métadonnées pour ChromaDB (valeurs doivent être str/int/float/bool)."""
        cleaned = {}
        for key, value in metadata.items():
            if value is None:
                cleaned[key] = ""
            elif isinstance(value, (str, int, float, bool)):
                cleaned[key] = value
            else:
                cleaned[key] = str(value)
        return cleaned

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any],
        overwrite: bool = True,
    ) -> bool:
        """
        Ajoute un document dans ChromaDB.

        Args:
            doc_id: Identifiant unique du document
            text: Texte complet à vectoriser
            metadata: Champs extraits + infos du document
            overwrite: Si True, met à jour si le doc existe déjà

        Returns:
            True si ajouté, False si ignoré
        """
        collection = self._get_collection()

        # Vérifier si le document existe déjà
        if overwrite:
            try:
                collection.delete(ids=[doc_id])
            except Exception:
                pass  # Pas encore présent, c'est normal

        # Texte tronqué si trop long (ChromaDB a des limites)
        text_to_embed = text[:8000] if len(text) > 8000 else text

        if not text_to_embed.strip():
            logger.warning(f"Document {doc_id} : texte vide, ignoré")
            return False

        embeddings = self.embed([text_to_embed])
        clean_meta = self._clean_metadata(metadata)

        collection.add(
            ids=[doc_id],
            embeddings=embeddings,
            documents=[text_to_embed],
            metadatas=[clean_meta],
        )
        return True

    def add_documents_batch(
        self,
        documents: List[Dict[str, Any]],
        batch_size: int = 32,
    ) -> int:
        """
        Ajoute plusieurs documents en batch.

        Args:
            documents: Liste de dicts avec keys: id, text, metadata
            batch_size: Taille des batches pour l'embedding

        Returns:
            Nombre de documents ajoutés
        """
        collection = self._get_collection()
        added = 0

        for i in range(0, len(documents), batch_size):
            batch = documents[i : i + batch_size]
            
            # Filtrer les documents vides
            valid = [d for d in batch if d.get("text", "").strip()]
            if not valid:
                continue

            ids = [d["id"] for d in valid]
            texts = [d["text"][:8000] for d in valid]
            metadatas = [self._clean_metadata(d.get("metadata", {})) for d in valid]

            # Supprimer les existants
            try:
                collection.delete(ids=ids)
            except Exception:
                pass

            embeddings = self.embed(texts)
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            added += len(valid)
            logger.debug(f"Batch {i//batch_size + 1} : {len(valid)} documents ajoutés")

        return added

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        doc_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Recherche sémantique dans ChromaDB.

        Args:
            query_text: Question en langage naturel
            n_results: Nombre de résultats à retourner
            where: Filtre ChromaDB (ex: {"TYPE_DOCUMENT": "FACTURE"})
            doc_type: Raccourci pour filtrer par type de document

        Returns:
            Liste de documents avec leurs métadonnées et score
        """
        collection = self._get_collection()
        
        # Construire le filtre
        where_filter = {}
        if doc_type:
            where_filter["TYPE_DOCUMENT"] = doc_type
        if where:
            where_filter.update(where)

        query_embedding = self.embed([query_text])[0]
        
        query_kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, collection.count() or 1),
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            query_kwargs["where"] = where_filter

        results = collection.query(**query_kwargs)

        # Formater les résultats
        formatted = []
        if results["ids"] and results["ids"][0]:
            for idx, doc_id in enumerate(results["ids"][0]):
                formatted.append({
                    "id": doc_id,
                    "score": 1 - results["distances"][0][idx],  # cosine similarity
                    "text": results["documents"][0][idx] if results["documents"] else "",
                    "metadata": results["metadatas"][0][idx] if results["metadatas"] else {},
                })

        return formatted

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de la collection."""
        collection = self._get_collection()
        total = collection.count()
        
        # Compter par type
        type_counts = {}
        for doc_type in ["FACTURE", "BON_DE_COMMANDE", "BON_DE_LIVRAISON", "DEVIS", "INCONNU"]:
            try:
                results = collection.get(where={"TYPE_DOCUMENT": doc_type})
                type_counts[doc_type] = len(results["ids"])
            except Exception:
                type_counts[doc_type] = 0

        return {
            "total_documents": total,
            "par_type": type_counts,
            "collection": CHROMA_COLLECTION_NAME,
            "chroma_dir": str(CHROMA_DIR),
        }

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Récupère un document par son ID."""
        collection = self._get_collection()
        result = collection.get(ids=[doc_id], include=["documents", "metadatas"])
        if result["ids"]:
            return {
                "id": result["ids"][0],
                "text": result["documents"][0] if result["documents"] else "",
                "metadata": result["metadatas"][0] if result["metadatas"] else {},
            }
        return None

    def list_documents(
        self,
        doc_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Liste les documents avec pagination."""
        collection = self._get_collection()
        
        get_kwargs: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
            "include": ["metadatas"],
        }
        if doc_type:
            get_kwargs["where"] = {"TYPE_DOCUMENT": doc_type}

        results = collection.get(**get_kwargs)
        
        docs = []
        if results["ids"]:
            for idx, doc_id in enumerate(results["ids"]):
                docs.append({
                    "id": doc_id,
                    "metadata": results["metadatas"][idx] if results["metadatas"] else {},
                })

        return {
            "documents": docs,
            "count": len(docs),
            "total": collection.count(),
        }

    def delete_document(self, doc_id: str) -> bool:
        """Supprime un document de ChromaDB."""
        collection = self._get_collection()
        try:
            collection.delete(ids=[doc_id])
            return True
        except Exception as e:
            logger.error(f"Erreur suppression {doc_id}: {e}")
            return False


# Singleton global
_indexer: Optional[ChromaIndexer] = None


def get_indexer() -> ChromaIndexer:
    """Retourne l'instance singleton du ChromaIndexer."""
    global _indexer
    if _indexer is None:
        _indexer = ChromaIndexer()
    return _indexer
