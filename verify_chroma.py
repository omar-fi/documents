#!/usr/bin/env python3
"""
Vérification complète : extraction PDF + stockage ChromaDB
Usage: python verify_chroma.py
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# ── 1. Vérifier si ChromaDB existe déjà ──────────────────────────────────────
print("=" * 65)
print("🔍  VÉRIFICATION EXTRACTION & STOCKAGE CHROMADB")
print("=" * 65)

CHROMA_DIR = Path(__file__).parent / "chroma_db"
REPORT_PATH = Path(__file__).parent / "extraction_report.json"

print(f"\n📁 Répertoire ChromaDB : {CHROMA_DIR}")
print(f"   Existe : {'✅ OUI' if CHROMA_DIR.exists() else '❌ NON'}")

if CHROMA_DIR.exists():
    chroma_files = list(CHROMA_DIR.rglob("*"))
    total_size = sum(f.stat().st_size for f in chroma_files if f.is_file())
    print(f"   Fichiers : {len([f for f in chroma_files if f.is_file()])}")
    print(f"   Taille totale : {total_size / 1024:.1f} KB")

# ── 2. Connexion à ChromaDB ───────────────────────────────────────────────────
print("\n" + "─" * 65)
print("🗄️  CONNEXION CHROMADB")
print("─" * 65)

try:
    import chromadb
    from rag_system.config import CHROMA_DIR, CHROMA_COLLECTION_NAME

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collections = client.list_collections()
    print(f"✅ ChromaDB connecté")
    print(f"   Collections disponibles : {[c.name for c in collections]}")

    if not collections:
        print("\n⚠️  AUCUNE COLLECTION TROUVÉE — ChromaDB est vide.")
        print("   👉 Lance d'abord l'ingestion : python ingest.py")
        sys.exit(0)

    # Ouvrir la collection principale
    collection = client.get_collection(name=CHROMA_COLLECTION_NAME)
    total_docs = collection.count()
    print(f"\n📊 Collection '{CHROMA_COLLECTION_NAME}' : {total_docs} documents indexés")

except Exception as e:
    print(f"❌ Erreur ChromaDB : {e}")
    sys.exit(1)

if total_docs == 0:
    print("\n⚠️  LA COLLECTION EST VIDE — Aucun document indexé.")
    print("   👉 Lance d'abord l'ingestion : python ingest.py")
    sys.exit(0)

# ── 3. Statistiques par type ──────────────────────────────────────────────────
print("\n" + "─" * 65)
print("📊 DOCUMENTS PAR TYPE")
print("─" * 65)

type_counts = {}
for doc_type in ["FACTURE", "BON_DE_COMMANDE", "BON_DE_LIVRAISON", "DEVIS", "INCONNU"]:
    try:
        results = collection.get(where={"TYPE_DOCUMENT": doc_type}, include=[])
        count = len(results["ids"])
        type_counts[doc_type] = count
        icon = {"FACTURE": "🧾", "BON_DE_COMMANDE": "📋", "BON_DE_LIVRAISON": "🚚",
                "DEVIS": "📝", "INCONNU": "❓"}.get(doc_type, "📄")
        bar = "█" * min(count, 30) + ("+" if count > 30 else "")
        print(f"   {icon} {doc_type:<20} : {count:>4} docs  {bar}")
    except Exception as e:
        print(f"   ⚠️  {doc_type}: erreur - {e}")

# ── 4. Échantillon de documents ───────────────────────────────────────────────
print("\n" + "─" * 65)
print("🔎 ÉCHANTILLON DE DOCUMENTS (5 premiers)")
print("─" * 65)

try:
    sample = collection.get(limit=5, include=["metadatas", "documents"])
    for i, (doc_id, meta, doc) in enumerate(
        zip(sample["ids"], sample["metadatas"], sample["documents"])
    ):
        print(f"\n  [{i+1}] ID : {doc_id}")
        print(f"       Type    : {meta.get('TYPE_DOCUMENT', 'N/A')}")
        print(f"       Fichier : {meta.get('FICHIER', 'N/A')}")
        print(f"       Taille texte : {meta.get('TAILLE_TEXTE', 'N/A')} chars")
        # Champs spécifiques selon le type
        for champ in ["NUM_FACTURE", "NUM_BON_COMMANDE", "NUM_BON_LIVRAISON", "NUM_DEVIS"]:
            val = meta.get(champ)
            if val:
                print(f"       {champ} : {val}")
        for champ in ["FOURNISSEUR", "FILIALE", "DATE", "MONTANT_TTC"]:
            val = meta.get(champ, "")
            status = "✅" if val else "⚠️ "
            print(f"       {status} {champ:<20} : {val or '(vide)'}")
        print(f"       📄 Texte (100 chars) : {doc[:100].replace(chr(10), ' ')}...")
except Exception as e:
    print(f"❌ Erreur lecture échantillon : {e}")

# ── 5. Vérification qualité des métadonnées ───────────────────────────────────
print("\n" + "─" * 65)
print("🏆 QUALITÉ DES MÉTADONNÉES")
print("─" * 65)

try:
    all_docs = collection.get(include=["metadatas"])
    total = len(all_docs["ids"])
    
    champs_importants = ["FOURNISSEUR", "FILIALE", "DATE", "MONTANT_TTC"]
    for champ in champs_importants:
        remplis = sum(1 for m in all_docs["metadatas"] if m.get(champ, "").strip())
        pct = (remplis / total * 100) if total > 0 else 0
        barre = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"   {champ:<20} : {barre} {pct:.0f}% ({remplis}/{total})")
except Exception as e:
    print(f"❌ Erreur qualité : {e}")

# ── 6. Test de recherche sémantique ───────────────────────────────────────────
print("\n" + "─" * 65)
print("🔍 TEST RECHERCHE SÉMANTIQUE")
print("─" * 65)

try:
    from rag_system.chroma_indexer import get_indexer
    indexer = get_indexer()

    test_queries = [
        ("montant facture fournisseur", None),
        ("bon de commande matériaux", "BON_DE_COMMANDE"),
    ]

    for query, doc_type in test_queries:
        print(f"\n  🔎 Requête : \"{query}\"" + (f" [filtre: {doc_type}]" if doc_type else ""))
        results = indexer.query(query, n_results=3, doc_type=doc_type)
        if results:
            for r in results:
                score = r.get("score", 0)
                meta = r.get("metadata", {})
                print(f"     ➤ [{score:.3f}] {r['id']} | {meta.get('TYPE_DOCUMENT','?')} | "
                      f"{meta.get('FOURNISSEUR','?')[:30]} | {meta.get('MONTANT_TTC','?')}")
        else:
            print("     ⚠️  Aucun résultat")
except Exception as e:
    print(f"❌ Erreur recherche : {e}")

# ── 7. Rapport JSON ────────────────────────────────────────────────────────────
print("\n" + "─" * 65)
print("📄 RAPPORT D'INGESTION")
print("─" * 65)

if REPORT_PATH.exists():
    try:
        with open(REPORT_PATH, encoding="utf-8") as f:
            report = json.load(f)
        print(f"✅ Rapport trouvé : {REPORT_PATH}")
        print(f"   Timestamp        : {report.get('timestamp', 'N/A')}")
        print(f"   Total PDFs       : {report.get('total_fichiers', 'N/A')}")
        print(f"   Traités OK       : {report.get('traites_avec_succes', 'N/A')}")
        print(f"   Indexés Chroma   : {report.get('indexes_dans_chroma', 'N/A')}")
        erreurs = report.get("erreurs", [])
        if erreurs:
            print(f"   ⚠️  Erreurs ({len(erreurs)}) : {erreurs[:5]}")
        else:
            print(f"   Erreurs          : ✅ Aucune")
        par_type = report.get("par_type", {})
        print(f"   Distribution     : {par_type}")
    except Exception as e:
        print(f"❌ Erreur lecture rapport : {e}")
else:
    print(f"⚠️  Rapport non trouvé : {REPORT_PATH}")
    print("   (Normal si l'ingestion n'a pas encore été exécutée)")

# ── Résumé final ───────────────────────────────────────────────────────────────
print("\n" + "=" * 65)
print("✅ RÉSUMÉ FINAL")
print("=" * 65)
print(f"   Documents dans ChromaDB : {total_docs}")
print(f"   Distribution : {type_counts}")
if total_docs > 0:
    print("\n✅ ChromaDB est opérationnel et contient des données.")
else:
    print("\n❌ ChromaDB est vide. Lance python ingest.py pour indexer les PDFs.")
print()
