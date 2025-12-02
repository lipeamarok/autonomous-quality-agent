"""
Ponto de Entrada do Brain — Autonomous Quality Agent.

Este módulo serve como ponto de entrada principal para o subsistema Brain,
responsável por gerar planos de teste UTDL a partir de requisitos.

Uso:
    python -m brain.src.main generate --requirement "Testar API de login"
    python -m brain.src.main run --swagger ./openapi.json
"""

from .cli import main

if __name__ == "__main__":
    main()
