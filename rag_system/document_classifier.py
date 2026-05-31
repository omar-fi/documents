"""
Classification du type de document.
Détecte : FACTURE, BON_DE_COMMANDE, BON_DE_LIVRAISON, DEVIS
via le nom du fichier ET le contenu du texte.
"""
import re
from pathlib import Path
from typing import Tuple

from .config import DOC_TYPES


# ─── Règles de classification par nom de fichier ───────────────────────────

FILENAME_RULES = [
    # (pattern_regex, type_document)
    (r"(?i)(facture|fct|fact|FCT|Facture)", "FACTURE"),
    (r"(?i)^devis", "DEVIS"),
    (r"(?i)(devis|dv|D\d{4})", "DEVIS"),
    (r"(?i)(bon[_\s-]?de[_\s-]?commande|bc[\s_(]|^bc\b|^BC)", "BON_DE_COMMANDE"),
    (r"(?i)(bon[_\s-]?de[_\s-]?livraison|bl[\s_(]|^bl\b|^BL)", "BON_DE_LIVRAISON"),
]

# ─── Règles de classification par contenu ──────────────────────────────────

CONTENT_RULES = [
    (r"(?i)\bfacture\b", "FACTURE"),
    (r"(?i)\bbon\s+de\s+commande\b", "BON_DE_COMMANDE"),
    (r"(?i)\bbon\s+de\s+livraison\b", "BON_DE_LIVRAISON"),
    (r"(?i)\bdevis\b", "DEVIS"),
    (r"(?i)\bnum[eé]ro\s+de\s+commande\b", "BON_DE_COMMANDE"),
    (r"(?i)\bnum[eé]ro\s+de\s+livraison\b", "BON_DE_LIVRAISON"),
]


def classify_by_filename(filename: str) -> str:
    """Classifie le document selon son nom de fichier."""
    for pattern, doc_type in FILENAME_RULES:
        if re.search(pattern, filename):
            return doc_type
    return "INCONNU"


def classify_by_content(text: str) -> str:
    """Classifie le document selon son contenu texte."""
    if not text:
        return "INCONNU"

    scores = {
        "FACTURE": 0,
        "BON_DE_COMMANDE": 0,
        "BON_DE_LIVRAISON": 0,
        "DEVIS": 0,
    }

    for pattern, doc_type in CONTENT_RULES:
        matches = len(re.findall(pattern, text))
        if doc_type in scores:
            scores[doc_type] += matches

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "INCONNU"


def classify_document(filename: str, text: str) -> Tuple[str, str]:
    """
    Classifie un document en combinant nom de fichier + contenu.

    Returns:
        (type_document, méthode_utilisée)
    """
    # Priorité au nom de fichier
    doc_type = classify_by_filename(filename)
    method = "filename"

    if doc_type == "INCONNU":
        # Fallback : contenu texte
        doc_type = classify_by_content(text)
        method = "content"

    return doc_type, method
