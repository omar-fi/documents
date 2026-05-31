"""
Extraction des champs structurés par regex selon le type de document.
Utilise pdfplumber (avec positions) pour séparer les colonnes, et regex sur le texte brut.

Structure réelle des PDFs (colonnes sur une même ligne) :
  FACTURE  : "DE :" | "À L'ATTENTION DE :"  → fournisseur | filiale
  BC       : "FOURNISSEUR :" | "LIVRAISON :"  → fournisseur | filiale
  BL       : émetteur en haut, "DESTINATAIRE :" | "MODE DE RÈGLEMENT :"
  DEVIS    : "DE :" | "FILIALE :"  → fournisseur | filiale
"""
import re
from pathlib import Path
from typing import Dict, Optional, Tuple


# ─── Utilitaires communs ──────────────────────────────────────────────────────

def _clean(s: str) -> str:
    """Nettoie une chaîne extraite."""
    if not s:
        return s
    return s.strip().strip(",").strip()


def _find_date(text: str) -> Optional[str]:
    """Cherche la première date au format DD/MM/YYYY ou similaire."""
    patterns = [
        r"\b(\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4})\b",
        r"\b(\d{4}[\/\-\.]\d{2}[\/\-\.]\d{2})\b",
        r"\b(\d{1,2}\s+(?:janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)\s+\d{4})\b",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _find_amount(text: str) -> Optional[str]:
    """
    Cherche le montant TTC.
    Priorité : TOTAL TTC > TOTAL > TTC seul.
    """
    # Patron 1 : "TOTAL TTC (MAD) 9,451,760.30" ou "TOTAL TTC : 58,200 MAD"
    m = re.search(
        r"TOTAL\s+TTC\s*(?:\([^)]*\))?\s*[:\s]\s*([\d\s,\.]+)",
        text, re.IGNORECASE
    )
    if m:
        return _clean(m.group(1).split()[0])  # premier token = montant

    # Patron 2 : "TOTAL : 134,400 MAD"
    m = re.search(
        r"^TOTAL\s*[:\s]\s*([\d\s,\.]+)\s*(?:MAD|DH|€)",
        text, re.IGNORECASE | re.MULTILINE
    )
    if m:
        return _clean(m.group(1).strip())

    # Patron 3 : ligne TOTAL TTC sans ponctuation
    m = re.search(
        r"TOTAL\s+TTC\s+([\d][\d\s,\.]+)",
        text, re.IGNORECASE
    )
    if m:
        return _clean(m.group(1).split()[0])

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


def _extract_from_filename(filename: str, pattern: str, flags: int = 0) -> Optional[str]:
    """Extrait une valeur depuis le nom de fichier."""
    m = re.search(pattern, filename, flags)
    return m.group(1) if m else None


# ─── Séparation de colonnes par position X ───────────────────────────────────

def _split_two_columns_by_position(pdf_path: Path, left_label: str, right_label: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Ouvre le PDF avec pdfplumber.
    Cherche la ligne d'en-tête contenant left_label ET right_label (ex: "DE :" et "FILIALE :").
    Détermine la position X de séparation (x0 du right_label).
    Extrait les valeurs de la ligne suivante de chaque côté de cette séparation.
    Retourne (valeur_gauche, valeur_droite).
    """
    try:
        import pdfplumber
    except ImportError:
        return None, None

    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                lines_by_y = {}
                for w in words:
                    y = round(w["top"] / 3) * 3  # grouper par blocs de 3pt
                    lines_by_y.setdefault(y, []).append(w)

                sorted_ys = sorted(lines_by_y.keys())

                # Chercher la ligne d'en-tête contenant les deux labels
                header_y = None
                sep_x = None
                for y in sorted_ys:
                    line_words = sorted(lines_by_y[y], key=lambda w: w["x0"])
                    line_text = " ".join(w["text"] for w in line_words)
                    # Vérifier que la ligne contient les deux labels
                    left_key = left_label.split()[0].rstrip(":")
                    right_key = right_label.split()[0].rstrip(":")
                    if (re.search(re.escape(left_key), line_text, re.IGNORECASE) and
                            re.search(re.escape(right_key), line_text, re.IGNORECASE)):
                        header_y = y
                        # La position X de séparation = x0 du premier mot du right_label
                        right_key_words = [
                            w for w in line_words
                            if re.match(re.escape(right_key), w["text"], re.IGNORECASE)
                        ]
                        if right_key_words:
                            sep_x = min(w["x0"] for w in right_key_words)
                        else:
                            # Fallback : milieu de page
                            sep_x = page.width * 0.45
                        break

                if header_y is None or sep_x is None:
                    continue

                # Ligne suivante après l'en-tête
                next_ys = [y for y in sorted_ys if y > header_y]
                if not next_ys:
                    continue

                next_y = next_ys[0]
                next_words = sorted(lines_by_y[next_y], key=lambda w: w["x0"])

                left_words = [w["text"] for w in next_words if w["x0"] < sep_x]
                right_words = [w["text"] for w in next_words if w["x0"] >= sep_x]

                left_val = _clean(" ".join(left_words)) if left_words else None
                right_val = _clean(" ".join(right_words)) if right_words else None

                return left_val, right_val

    except Exception:
        pass

    return None, None


# ─── Extracteur FACTURE ───────────────────────────────────────────────────────

def extract_facture(text: str, filename: str, pdf_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'une FACTURE.
    En-tête colonnes : "DE :  |  À L'ATTENTION DE :"
    """
    # Numéro de facture
    num_facture = None
    num_patterns = [
        r"(?:facture\s*n[°º]?|n[°º]?\s*facture)\s*[:\s]+([A-Z0-9\-\/\.]+)",
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
        r"(?:bc|b\.c\.)\s*[:\-#]?\s*([A-Z0-9\-\/\.]{3,20})",
    ]
    for p in bc_patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            num_bc = m.group(1).strip()
            break

    # Fournisseur et Filiale via positions X
    fournisseur, filiale = None, None
    if pdf_path:
        fournisseur, filiale = _split_two_columns_by_position(
            pdf_path, "DE :", "ATTENTION"
        )

    # Fallback regex : "Paiement à l'ordre de : NOM"
    if not fournisseur:
        m = re.search(r"paiement\s+[àa]\s+l.ordre\s+de\s*:\s*(.+)", text, re.IGNORECASE)
        if m:
            fournisseur = _clean(m.group(1))

    # Fallback filiale regex
    if not filiale:
        m = re.search(
            r"(?:À L'ATTENTION DE|attention de|destinataire)\s*:\s*([A-Z][A-Za-z\s&\-\.]+?)(?:\n|$)",
            text, re.IGNORECASE
        )
        if m:
            filiale = _clean(m.group(1))

    return {
        "TYPE_DOCUMENT": "FACTURE",
        "NUM_FACTURE": num_facture or _extract_from_filename(filename, r"[Ff][-_]?(\d{3,}-\d{2,})"),
        "DATE": _find_date(text),
        "FOURNISSEUR": fournisseur,
        "FILIALE": filiale,
        "MONTANT_TTC": _find_amount(text),
        "NUM_CONTRAT": _find_num_contrat(text),
        "NUM_BON_COMMANDE": num_bc,
    }


# ─── Extracteur BON DE COMMANDE ───────────────────────────────────────────────

def extract_bon_commande(text: str, filename: str, pdf_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'un BON DE COMMANDE.
    En-tête colonnes : "FOURNISSEUR :  |  LIVRAISON :"
    """
    num_bc = None
    patterns = [
        r"N[°º]\s*:\s*([A-Z0-9\-\/\.]{4,30})",
        r"(?:bon\s+de\s+commande)\s*n[°º]?\s*[:\s]*([A-Z0-9\-\/\.]{4,30})",
        r"(?:bc|b\.c\.)\s*[:\-#]?\s*([A-Z0-9\-\/\.]{3,20})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            if re.match(r"[A-Z0-9]{2,}-\d{2,}", val):
                num_bc = val
                break

    # Fournisseur et Filiale via positions X (pdfplumber)
    fournisseur, filiale = None, None
    if pdf_path:
        fournisseur, filiale = _split_two_columns_by_position(
            pdf_path, "FOURNISSEUR :", "LIVRAISON :"
        )

    # Fallback regex multi-ligne : "FOURNISSEUR :\nBELTS & CONVEYORS SOLUTIONS\n..."
    if not fournisseur:
        m = re.search(
            r"FOURNISSEUR\s*:\s*\n?\s*([A-Z][A-ZÉÈÀÂÙÎÔÄËÏÖÜ][A-Za-zéèàâùûîôäëïöü\s\&\.,'\-]+?)(?:\n|Z\.I\.|ICE:|$)",
            text, re.IGNORECASE
        )
        if m:
            fournisseur = _clean(m.group(1))

    # Fallback filiale : "LIVRAISON :\nSMI (Société...)\n..."
    if not filiale:
        m = re.search(
            r"LIVRAISON\s*:\s*\n?\s*([A-Z][A-Za-zéèàâùûîôäëïöü\s\&\.,'\-\(\)]+?)(?:\n|Site\s|Projet:|$)",
            text, re.IGNORECASE
        )
        if m:
            filiale = _clean(m.group(1))

    return {
        "NUM_BON_COMMANDE": num_bc or _extract_from_filename(filename, r"bc[\s_\-]?(\d+)", re.IGNORECASE),
        "FOURNISSEUR": fournisseur,
        "FILIALE": filiale,
        "DATE": _find_date(text),
        "MONTANT_TTC": _find_amount(text),
    }


# ─── Extracteur BON DE LIVRAISON ─────────────────────────────────────────────

def extract_bon_livraison(text: str, filename: str, pdf_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'un BON DE LIVRAISON.
    Structure : émetteur en haut (ligne 0), DESTINATAIRE | MODE DE RÈGLEMENT
    """
    # Numéro BL
    num_bl = None
    patterns = [
        r"NUM[EÉ]RO\s*:\s*([A-Z0-9\-\/\.]+)",
        r"(?:bon\s+de\s+livraison|livraison)\s*n[°º]?\s*[:\s]*([A-Z0-9\-\/\.]+)",
        r"(?:bl|b\.l\.)\s*[:\-#]?\s*([A-Z0-9\-\/\.]{3,20})",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            num_bl = m.group(1).strip()
            break

    # Fournisseur : première ligne avant "BON DE LIVRAISON"
    fournisseur = None
    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Première ligne non-vide = émetteur. On enlève la date si collée.
        fournisseur = re.sub(r'\s+DATE\s*:.*$', '', line, flags=re.IGNORECASE).strip()
        break

    # Filiale : à GAUCHE de la colonne "DESTINATAIRE : | MODE DE RÈGLEMENT :"
    filiale = None
    if pdf_path:
        filiale, _ = _split_two_columns_by_position(
            pdf_path, "DESTINATAIRE :", "MODE"
        )

    if not filiale:
        m = re.search(
            r"DESTINATAIRE\s*:[^\n]*\n\s*([A-Z][^\n]+)",
            text, re.IGNORECASE
        )
        if m:
            val = m.group(1)
            parts = re.split(r'\s{3,}', val)
            filiale = _clean(parts[0])

    return {
        "TYPE_DOCUMENT": "BON_DE_LIVRAISON",
        "FOURNISSEUR": fournisseur,
        "DATE": _find_date(text),
        "NUM_BON_LIVRAISON": num_bl or _extract_from_filename(filename, r"bl[\s_\-]?(\d+)", re.IGNORECASE),
        "FILIALE": filiale,
        "MONTANT_TTC": _find_amount(text),
    }


# ─── Extracteur DEVIS ─────────────────────────────────────────────────────────

def extract_devis(text: str, filename: str, pdf_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """
    Extrait les champs d'un DEVIS.
    En-tête colonnes : "DE :  |  FILIALE :"
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

    # Fournisseur et Filiale via positions X (pdfplumber)
    fournisseur, filiale = None, None
    if pdf_path:
        fournisseur, filiale = _split_two_columns_by_position(
            pdf_path, "DE :", "FILIALE"
        )

    # Fallback fournisseur : "Paiement à l'ordre de : NOM" ou "DE :\nNOM"
    if not fournisseur:
        m = re.search(r"paiement\s+[\u00e0a]\s+l.ordre\s+de\s*:\s*(.+)", text, re.IGNORECASE)
        if m:
            fournisseur = _clean(m.group(1))
    if not fournisseur:
        # Dans le texte PyMuPDF, "DE :" est suivi directement de la valeur sur la même ligne
        # ex: "DE : MAROC ÉTUDES & PROJETS"
        m = re.search(r"^DE\s*:\s+([A-Z][A-ZÉÈÀ\s\&\.,'\-]+?)(?:\n|Avenue|Route|Rue|$)",
                      text, re.IGNORECASE | re.MULTILINE)
        if m:
            fournisseur = _clean(m.group(1))

    # Fallback filiale : "FILIALE :\nCTT (...)" ou "FILIALE : CTT (...)"
    if not filiale:
        m = re.search(
            r"FILIALE\s*:\s*\n?\s*([A-Z][A-Za-zéèàâùûîôäëïöü\s\&\.,'\-\(\)]+?)(?:\n|Bou-|Site\s|$)",
            text, re.IGNORECASE
        )
        if m:
            filiale = _clean(m.group(1))

    return {
        "TYPE_DOCUMENT": "DEVIS",
        "FOURNISSEUR": fournisseur,
        "DATE": _find_date(text),
        "NUM_DEVIS": num_devis or _extract_from_filename(filename, r"[Dd](\d{4}-\d{3,})"),
        "FILIALE": filiale,
        "MONTANT_TTC": _find_amount(text),
    }


# ─── Dispatcher principal ─────────────────────────────────────────────────────

EXTRACTORS = {
    "FACTURE": extract_facture,
    "BON_DE_COMMANDE": extract_bon_commande,
    "BON_DE_LIVRAISON": extract_bon_livraison,
    "DEVIS": extract_devis,
}


def extract_fields(doc_type: str, text: str, filename: str, pdf_path: Optional[Path] = None) -> Dict[str, Optional[str]]:
    """
    Extrait les champs structurés selon le type de document.

    Args:
        doc_type: Type parmi FACTURE, BON_DE_COMMANDE, BON_DE_LIVRAISON, DEVIS
        text: Texte brut du document
        filename: Nom du fichier source
        pdf_path: Chemin complet du PDF (pour l'extraction par position X)

    Returns:
        Dict avec les champs extraits (valeurs None si non trouvées)
    """
    extractor = EXTRACTORS.get(doc_type)
    if extractor is None:
        return {"TYPE_DOCUMENT": "INCONNU"}
    return extractor(text, filename, pdf_path)
