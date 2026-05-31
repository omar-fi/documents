#!/usr/bin/env python3
"""
Test rapide : vérifie l'extraction sur quelques PDFs avant l'ingestion complète.
Usage: python3 test_extraction.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_system.pdf_extractor import extract_text
from rag_system.document_classifier import classify_document
from rag_system.field_extractor import extract_fields

# Sélectionner un PDF de chaque type
TEST_FILES = [
    "Facture F2605-10.pdf",
    "bc(1).pdf",
    "bl(10).pdf",
    "Devis D2605-101.pdf",
]

PDF_DIR = Path(__file__).parent


def test_file(filename: str):
    pdf_path = PDF_DIR / filename
    if not pdf_path.exists():
        print(f"❌ Fichier non trouvé: {filename}")
        return

    print(f"\n{'='*60}")
    print(f"📄 Fichier: {filename}")
    print(f"{'='*60}")

    # Extraction texte
    text = extract_text(pdf_path)
    print(f"📝 Texte extrait: {len(text)} caractères")
    if text:
        print(f"   Aperçu: {text[:200].replace(chr(10), ' ')[:200]}...")

    # Classification
    doc_type, method = classify_document(filename, text)
    print(f"🏷️  Type détecté: {doc_type} (via {method})")

    # Extraction des champs (avec pdf_path pour extraction par position)
    fields = extract_fields(doc_type, text, filename, pdf_path=pdf_path)
    print(f"📋 Champs extraits:")
    for key, value in fields.items():
        status = "✅" if value else "⚠️ "
        print(f"   {status} {key}: {value or '(non trouvé)'}")


if __name__ == "__main__":
    print("🔍 Test d'extraction RAG\n")
    for f in TEST_FILES:
        test_file(f)
    print(f"\n{'='*60}")
    print("✅ Test terminé")
