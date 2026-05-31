"""
Extraction des champs structurés par regex selon le type de document.
Chaque extracteur retourne un dict avec les champs définis dans le schéma.
"""
import re
from typing import Dict, Optional


# ─── Patterns communs ──────────────────────────────────────────────────────

def _find_date(text: str) -> Optional[str]:
    """Cherche une date au format DD/MM/YYYY, DD-MM-YYYY, ou YYYY-MM-DD."""
    patterns = [
        r"\b(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})\b",
        r"\b(\d{4}[\/\-\.]\d{2}[\/\-\.]\d{2})\b",
        r"\b(\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _find_amount(text: str) -> Optional[str]:
    """Cherche un montant TTC (format: 1 234,56 ou 1234.56 DH/MAD/€)."""
    patterns = [
        # "TTC : 12 345,67 DH" ou "Montant TTC 12345.67"
        r"(?:montant\s*ttc|total\s*ttc|ttc)[^\d]*(\d[\d\s]*[\.,]\d{2})\s*(?:dh|mad|€|eur)?",
        r"(?:total|montant)[^\d]*(\d[\d\s]*[\.,]\d{2})\s*(?:dh|mad|€|eur)?",
        # Dernier montant en bas de page avec devise
        r"(\d[\d\s]{2,}[\.,]\d{2})\s*(?:dh|mad|€|eur)\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _find_fournisseur(text: str) -> Optional[str]:
    """Cherche le nom du fournisseur."""
    patterns = [
        r"(?:fournisseur|vendeur|prestataire|émetteur)[^\n:]*[:\s]+([A-ZÉÈÀÂ][A-Za-zéèàâùûîôäëïöüç\s\-&\.,']+?)(?:\n|$|,\s*\d)",
        r"(?:société|sarl|sa|sas|earl|snc|sca)\s+([A-ZÉÈÀÂ][A-Za-zéèàâùûîôäëïöüç\s\-&\.,']+?)(?:\n|$)",
        r"^([A-ZÉÈÀÂ][A-ZÉÈÀÂ\s\-&\.,']{5,40})$",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def _find_filiale(text: str) -> Optional[str]:
    """Cherche le nom de la filiale (destinataire/client)."""
    patterns = [
        r"(?:filiale|client|destinataire|à\s*:|adressé\s*à)[^\n:]*[:\s]+([A-ZÉÈÀÂ][A-Za-zéèàâùûîôäëïöüç\s\-&\.,']+?)(?:\n|$)",
        r"(?:facturé\s*à|livré\s*à)[^\n:]*[:\s]+([A-ZÉÈÀÂ][A-Za-zéèàâùûîôäëïöüç\s\-&\.,']+?)(?:\n|$)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None


def _find_num_contrat(text: str) -> Optional[str]:
    """Cherche un numéro de contrat."""
    patterns = [
        r"(?:n[°º]?\s*contrat|num[eé]ro\s+contrat|contrat\s*n[°º]?)[^\n:]*[:\s#]*([A-Z0-9\-\/]+)",
        r"(?:contrat)[^\n:]*[:\s#]+([A-Z0-9\-\/]{3,20})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


# ─── Extracteurs par type ──────────────────────────────────────────────────

def extract_facture(text: str, filename: str) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'une FACTURE :
    TYPE_DOCUMENT, NUM_FACTURE, DATE, FOURNISSEUR, FILIALE,
    MONTANT_TTC, NUM_CONTRAT, NUM_BON_COMMANDE
    """
    # Numéro de facture
    num_facture = None
    num_patterns = [
        r"(?:facture\s*n[°º]?|n[°º]?\s*facture|n[°º]?\s*:)\s*([A-Z0-9\-\/\.]+)",
        r"(?:^|\s)([FfFCT]\d{3,}[-\/]\d{2,})",
        r"(?:num[eé]ro|n[°º]?)[^\n:]*:\s*([A-Z0-9\-\/\.]{4,20})",
    ]
    for p in num_patterns:
        m = re.search(p, text, re.IGNORECASE | re.MULTILINE)
        if m:
            num_facture = m.group(1).strip()
            break

    # Numéro de bon de commande référencé
    num_bc = None
    bc_patterns = [
        r"(?:bon\s+de\s+commande|n[°º]?\s*commande|commande\s*n[°º]?)[^\n:]*[:\s#]+([A-Z0-9\-\/\.]+)",
        r"(?:bc|b\.c\.)[^\n:]*[:\s#]+([A-Z0-9\-\/\.]{3,20})",
    ]
    for p in bc_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            num_bc = m.group(1).strip()
            break

    return {
        "TYPE_DOCUMENT": "FACTURE",
        "NUM_FACTURE": num_facture or _extract_from_filename(filename, r"[Ff][-_]?(\d{3,}-\d{2,})"),
        "DATE": _find_date(text),
        "FOURNISSEUR": _find_fournisseur(text),
        "FILIALE": _find_filiale(text),
        "MONTANT_TTC": _find_amount(text),
        "NUM_CONTRAT": _find_num_contrat(text),
        "NUM_BON_COMMANDE": num_bc,
    }


def extract_bon_commande(text: str, filename: str) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'un BON DE COMMANDE :
    NUM_BON_COMMANDE, FOURNISSEUR, FILIALE, DATE, MONTANT_TTC
    """
    num_bc = None
    patterns = [
        r"(?:bon\s+de\s+commande|commande)\s*n[°º]?\s*[:\s]*([A-Z0-9\-\/\.]+)",
        r"(?:n[°º]?\s*:?\s*)([A-Z0-9]{2,}\-\d{2,})",
        r"(?:bc|b\.c\.)\s*[:\-#]?\s*([A-Z0-9\-\/\.]{3,20})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            num_bc = m.group(1).strip()
            break

    return {
        "NUM_BON_COMMANDE": num_bc or _extract_from_filename(filename, r"bc[\s_\-]?(\d+)", re.IGNORECASE),
        "FOURNISSEUR": _find_fournisseur(text),
        "FILIALE": _find_filiale(text),
        "DATE": _find_date(text),
        "MONTANT_TTC": _find_amount(text),
    }


def extract_bon_livraison(text: str, filename: str) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'un BON DE LIVRAISON :
    TYPE_DOCUMENT, FOURNISSEUR, DATE, NUM_BON_LIVRAISON, FILIALE, MONTANT_TTC
    """
    num_bl = None
    patterns = [
        r"(?:bon\s+de\s+livraison|livraison)\s*n[°º]?\s*[:\s]*([A-Z0-9\-\/\.]+)",
        r"(?:bl|b\.l\.)\s*[:\-#]?\s*([A-Z0-9\-\/\.]{3,20})",
        r"(?:n[°º]?\s*:?\s*)([A-Z0-9]{2,}\-\d{2,})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            num_bl = m.group(1).strip()
            break

    return {
        "TYPE_DOCUMENT": "BON_DE_LIVRAISON",
        "FOURNISSEUR": _find_fournisseur(text),
        "DATE": _find_date(text),
        "NUM_BON_LIVRAISON": num_bl or _extract_from_filename(filename, r"bl[\s_\-]?(\d+)", re.IGNORECASE),
        "FILIALE": _find_filiale(text),
        "MONTANT_TTC": _find_amount(text),
    }


def extract_devis(text: str, filename: str) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'un DEVIS :
    TYPE_DOCUMENT, FOURNISSEUR, DATE, NUM_DEVIS, FILIALE, MONTANT_TTC
    """
    num_devis = None
    patterns = [
        r"(?:devis)\s*n[°º]?\s*[:\s]*([A-Z0-9\-\/\.]+)",
        r"(?:n[°º]?\s*:?\s*)([D]\d{4}\-\d{3,})",
        r"(?:ref[eé]rence|r[eé]f\.?)[^\n:]*[:\s]+([A-Z0-9\-\/\.]{4,20})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            num_devis = m.group(1).strip()
            break

    return {
        "TYPE_DOCUMENT": "DEVIS",
        "FOURNISSEUR": _find_fournisseur(text),
        "DATE": _find_date(text),
        "NUM_DEVIS": num_devis or _extract_from_filename(filename, r"[Dd](\d{4}-\d{3,})"),
        "FILIALE": _find_filiale(text),
        "MONTANT_TTC": _find_amount(text),
    }


def _extract_from_filename(filename: str, pattern: str, flags: int = 0) -> Optional[str]:
    """Extrait une valeur depuis le nom de fichier."""
    m = re.search(pattern, filename, flags)
    return m.group(1) if m else None


# ─── Dispatcher principal ──────────────────────────────────────────────────

EXTRACTORS = {
    "FACTURE": extract_facture,
    "BON_DE_COMMANDE": extract_bon_commande,
    "BON_DE_LIVRAISON": extract_bon_livraison,
    "DEVIS": extract_devis,
}


def extract_fields(doc_type: str, text: str, filename: str) -> Dict[str, Optional[str]]:
    """
    Extrait les champs structurés selon le type de document.

    Args:
        doc_type: Type parmi FACTURE, BON_DE_COMMANDE, BON_DE_LIVRAISON, DEVIS
        text: Texte brut du document
        filename: Nom du fichier source

    Returns:
        Dict avec les champs extraits (valeurs None si non trouvées)
    """
    extractor = EXTRACTORS.get(doc_type)
    if extractor is None:
        return {"TYPE_DOCUMENT": "INCONNU"}
    return extractor(text, filename)
