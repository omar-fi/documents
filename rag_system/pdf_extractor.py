"""
Extraction du texte depuis les fichiers PDF.
Utilise pdfplumber en priorité, PyMuPDF en fallback.
"""
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


def extract_text_pdfplumber(pdf_path: Path) -> Optional[str]:
    """Extrait le texte d'un PDF via pdfplumber."""
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
        return "\n".join(pages_text) if pages_text else None
    except Exception as e:
        logger.warning(f"pdfplumber échoué sur {pdf_path.name}: {e}")
        return None


def extract_text_pymupdf(pdf_path: Path) -> Optional[str]:
    """Extrait le texte d'un PDF via PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
        pages_text = []
        doc = fitz.open(str(pdf_path))
        for page in doc:
            text = page.get_text()
            if text.strip():
                pages_text.append(text)
        doc.close()
        return "\n".join(pages_text) if pages_text else None
    except Exception as e:
        logger.warning(f"PyMuPDF échoué sur {pdf_path.name}: {e}")
        return None


def extract_text(pdf_path: Path) -> str:
    """
    Extrait le texte d'un PDF.
    Essaie pdfplumber d'abord, puis PyMuPDF en fallback.
    
    Returns:
        Texte extrait (peut être vide si le PDF est image-only)
    """
    pdf_path = Path(pdf_path)
    
    # Tentative 1 : pdfplumber
    text = extract_text_pdfplumber(pdf_path)
    
    # Tentative 2 : PyMuPDF
    if not text or len(text.strip()) < 20:
        text = extract_text_pymupdf(pdf_path)
    
    if not text:
        logger.warning(f"Impossible d'extraire le texte de {pdf_path.name} (PDF image ?)")
        return ""
    
    return text.strip()
