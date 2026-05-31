"""
Configuration du système RAG
"""
import os
from pathlib import Path

# ─── Chemins ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
PDF_DIR = BASE_DIR  # Répertoire contenant les PDFs
CHROMA_DIR = BASE_DIR / "chroma_db"
REPORT_PATH = BASE_DIR / "extraction_report.json"

# ─── ChromaDB ───────────────────────────────────────────────────────────────
CHROMA_COLLECTION_NAME = "documents_financiers"

# ─── Embedding ──────────────────────────────────────────────────────────────
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ─── Types de documents ─────────────────────────────────────────────────────
DOC_TYPES = {
    "FACTURE": "FACTURE",
    "BON_DE_COMMANDE": "BON_DE_COMMANDE",
    "BON_DE_LIVRAISON": "BON_DE_LIVRAISON",
    "DEVIS": "DEVIS",
    "INCONNU": "INCONNU",
}

# ─── Schémas des champs par type ────────────────────────────────────────────
SCHEMAS = {
    "FACTURE": [
        "TYPE_DOCUMENT",
        "NUM_FACTURE",
        "DATE",
        "FOURNISSEUR",
        "FILIALE",
        "MONTANT_TTC",
        "NUM_CONTRAT",
        "NUM_BON_COMMANDE",
    ],
    "BON_DE_COMMANDE": [
        "NUM_BON_COMMANDE",
        "FOURNISSEUR",
        "FILIALE",
        "DATE",
        "MONTANT_TTC",
    ],
    "BON_DE_LIVRAISON": [
        "TYPE_DOCUMENT",
        "FOURNISSEUR",
        "DATE",
        "NUM_BON_LIVRAISON",
        "FILIALE",
        "MONTANT_TTC",
    ],
    "DEVIS": [
        "TYPE_DOCUMENT",
        "FOURNISSEUR",
        "DATE",
        "NUM_DEVIS",
        "FILIALE",
        "MONTANT_TTC",
    ],
    "INCONNU": [],
}

# ─── FastAPI ─────────────────────────────────────────────────────────────────
API_HOST = "0.0.0.0"
API_PORT = 8000
API_TITLE = "RAG Système - Documents Financiers"
API_VERSION = "1.0.0"
