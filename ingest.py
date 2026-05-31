#!/usr/bin/env python3
"""
Script d'ingestion des PDFs dans ChromaDB.
Usage: python ingest.py [--dir /chemin/vers/pdfs] [--batch-size 32]
"""
import argparse
import json
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

# Ajouter le répertoire parent au path
sys.path.insert(0, str(Path(__file__).parent))

from rag_system.pipeline import ingest_directory
from rag_system.config import PDF_DIR, REPORT_PATH

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Ingère des fichiers PDF dans ChromaDB"
    )
    parser.add_argument(
        "--dir",
        type=Path,
        default=PDF_DIR,
        help=f"Répertoire PDF (défaut: {PDF_DIR})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Taille des batches (défaut: 32)",
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Ne pas sauvegarder le rapport JSON",
    )
    args = parser.parse_args()

    console.print(Panel.fit(
        "[bold blue]🗃️  Système RAG - Ingestion PDF → ChromaDB[/bold blue]",
        border_style="blue",
    ))
    
    console.print(f"📁 Répertoire: [cyan]{args.dir}[/cyan]")
    console.print(f"🔢 Batch size: [cyan]{args.batch_size}[/cyan]")
    console.print()

    # Lancer l'ingestion
    logging.basicConfig(level=logging.WARNING)  # Silence les logs verbeux
    
    report = ingest_directory(
        pdf_dir=args.dir,
        batch_size=args.batch_size,
        save_report=not args.no_report,
    )

    # Afficher le résumé
    console.print()
    console.print(Panel.fit("[bold green]✅ Ingestion terminée[/bold green]", border_style="green"))

    # Tableau des résultats par type
    table = Table(title="Résultats par type de document", show_header=True, header_style="bold magenta")
    table.add_column("Type de document", style="cyan")
    table.add_column("Nombre", justify="right", style="green")

    for doc_type, count in sorted(report.get("par_type", {}).items()):
        table.add_row(doc_type, str(count))

    console.print(table)
    console.print()

    # Statistiques globales
    console.print(f"📊 Total fichiers    : [bold]{report['total_fichiers']}[/bold]")
    console.print(f"✅ Traités           : [bold green]{report['traites_avec_succes']}[/bold green]")
    console.print(f"🗄️  Indexés ChromaDB : [bold blue]{report['indexes_dans_chroma']}[/bold blue]")

    if report.get("erreurs"):
        console.print(f"\n⚠️  [yellow]{len(report['erreurs'])} erreurs[/yellow]:")
        for err in report["erreurs"][:10]:
            console.print(f"   - {err}")

    if not args.no_report:
        console.print(f"\n📄 Rapport JSON: [cyan]{REPORT_PATH}[/cyan]")

    console.print()
    console.print("[bold]💡 Démarrez l'API avec:[/bold] [cyan]python start_api.py[/cyan]")


if __name__ == "__main__":
    main()
