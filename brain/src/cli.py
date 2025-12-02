"""
CLI do Brain — Interface de linha de comando para geração e execução de planos UTDL.

Este módulo fornece uma interface CLI completa para:
- Gerar planos UTDL a partir de requisitos em linguagem natural
- Gerar planos a partir de especificações OpenAPI/Swagger
- Executar o fluxo completo: geração + execução via Runner Rust

Uso:
    # Gerar plano a partir de requisito em linguagem natural
    python -m brain.src.cli generate --requirement "Testar API de login" --base-url https://api.example.com

    # Gerar a partir de spec OpenAPI
    python -m brain.src.cli generate --swagger ./openapi.json --output plan.json

    # Fluxo completo autônomo (gerar + executar)
    python -m brain.src.cli run --requirement "Testar API de usuários" --base-url https://api.example.com
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from .generator import UTDLGenerator
from .ingestion import parse_openapi
from .ingestion.swagger import spec_to_requirement_text
from .runner import run_plan

if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


def main() -> None:
    """
    Ponto de entrada principal do CLI.

    Configura o parser de argumentos e despacha para o comando apropriado.
    """
    parser = argparse.ArgumentParser(
        description="Brain CLI - Gera e executa planos de teste UTDL usando IA"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Comando generate
    gen_parser = subparsers.add_parser("generate", help="Gera um plano de teste UTDL")
    _add_common_args(gen_parser)
    gen_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Caminho do arquivo de saída (padrão: stdout)",
    )

    # Comando run (generate + execute)
    run_parser = subparsers.add_parser("run", help="Gera e executa um plano de teste")
    _add_common_args(run_parser)
    run_parser.add_argument(
        "--save-plan",
        "-p",
        type=str,
        help="Salva o plano gerado neste arquivo",
    )
    run_parser.add_argument(
        "--save-report",
        "-o",
        type=str,
        help="Salva o relatório de execução neste arquivo",
    )

    args = parser.parse_args()

    if args.command == "generate":
        run_generate(args)
    elif args.command == "run":
        run_full(args)


def _add_common_args(parser: ArgumentParser) -> None:
    """
    Adiciona argumentos comuns a um subparser.

    Args:
        parser: Subparser ao qual adicionar os argumentos
    """
    parser.add_argument(
        "--requirement",
        "-r",
        type=str,
        help="Descrição em linguagem natural do que testar",
    )
    parser.add_argument(
        "--swagger",
        "-s",
        type=str,
        help="Caminho ou URL para especificação OpenAPI/Swagger",
    )
    parser.add_argument(
        "--base-url",
        "-u",
        type=str,
        default="https://api.example.com",
        help="URL base da API sob teste",
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default="gpt-4",
        help="Modelo LLM a usar (padrão: gpt-4)",
    )


def run_generate(args: Namespace) -> None:
    """
    Executa o comando generate.

    Gera um plano UTDL e o imprime no stdout ou salva em arquivo.

    Args:
        args: Argumentos parseados do CLI
    """
    requirement, base_url = _get_requirement(args)

    print(f"Gerando plano UTDL usando {args.model}...", file=sys.stderr)

    try:
        generator = UTDLGenerator(model=args.model)
        plan = generator.generate(requirement, base_url)

        json_output = plan.to_json()

        if args.output:
            Path(args.output).write_text(json_output, encoding="utf-8")
            print(f"Plano salvo em: {args.output}", file=sys.stderr)
        else:
            print(json_output)

    except ValueError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erro inesperado: {e}", file=sys.stderr)
        sys.exit(1)


def run_full(args: Namespace) -> None:
    """
    Executa o fluxo completo: geração + execução.

    Este é o modo autônomo principal do Brain, onde:
    1. Gera um plano UTDL usando LLM
    2. Executa o plano usando o Runner Rust
    3. Exibe o resumo dos resultados

    Args:
        args: Argumentos parseados do CLI
    """
    requirement, base_url = _get_requirement(args)

    # Passo 1: Gerar plano
    print(f"🧠 Gerando plano UTDL usando {args.model}...", file=sys.stderr)

    try:
        generator = UTDLGenerator(model=args.model)
        plan = generator.generate(requirement, base_url)

        # Opcionalmente salva o plano
        if args.save_plan:
            Path(args.save_plan).write_text(plan.to_json(), encoding="utf-8")
            print(f"📄 Plano salvo em: {args.save_plan}", file=sys.stderr)

        # Passo 2: Executar plano
        print(f"🚀 Executando plano: {plan.meta.name}...", file=sys.stderr)
        result = run_plan(plan)

        # Exibe resumo
        print("\n" + "=" * 50, file=sys.stderr)
        print(result.summary(), file=sys.stderr)
        print("=" * 50 + "\n", file=sys.stderr)

        # Opcionalmente salva relatório
        if args.save_report:
            Path(args.save_report).write_text(
                json.dumps(result.raw_report, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            print(f"📊 Relatório salvo em: {args.save_report}", file=sys.stderr)

        # Sai com código apropriado
        sys.exit(0 if result.success else 1)

    except ValueError as e:
        print(f"❌ Erro de geração: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"❌ Erro de execução: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Erro inesperado: {e}", file=sys.stderr)
        sys.exit(1)


def _get_requirement(args: Namespace) -> tuple[str, str]:
    """
    Extrai texto de requisito e base_url dos argumentos.

    Args:
        args: Argumentos parseados do CLI

    Returns:
        Tupla (requirement_text, base_url)

    Raises:
        SystemExit: Se nem --requirement nem --swagger forem fornecidos
    """
    if args.swagger:
        print(f"Parseando spec OpenAPI: {args.swagger}", file=sys.stderr)
        spec = parse_openapi(args.swagger)
        requirement = spec_to_requirement_text(spec)
        base_url: str = spec.get("base_url") or args.base_url
    elif args.requirement:
        requirement = args.requirement
        base_url = args.base_url
    else:
        print(
            "Erro: É necessário fornecer --requirement ou --swagger",
            file=sys.stderr,
        )
        sys.exit(1)
    return requirement, base_url


if __name__ == "__main__":
    main()
