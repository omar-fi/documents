#!/usr/bin/env python3
"""
Démarrage de l'API FastAPI.
Usage: python start_api.py [--host 0.0.0.0] [--port 8000]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from rag_system.config import API_HOST, API_PORT


def main():
    parser = argparse.ArgumentParser(description="Démarre l'API RAG FastAPI")
    parser.add_argument("--host", default=API_HOST)
    parser.add_argument("--port", type=int, default=API_PORT)
    parser.add_argument("--reload", action="store_true", help="Auto-reload (développement)")
    args = parser.parse_args()

    import uvicorn

    print(f"\n🚀 API RAG démarrée sur http://{args.host}:{args.port}")
    print(f"📖 Documentation: http://localhost:{args.port}/docs")
    print(f"🔍 Recherche:     http://localhost:{args.port}/search?q=votre+requete")
    print(f"📊 Stats:         http://localhost:{args.port}/stats\n")

    uvicorn.run(
        "rag_system.api:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
