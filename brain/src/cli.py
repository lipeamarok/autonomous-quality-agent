"""
================================================================================
CLI DO BRAIN — Interface de Linha de Comando
================================================================================

Este módulo fornece uma interface de linha de comando (CLI) completa para
o Brain, permitindo gerar e executar planos de teste diretamente do terminal.

## Para todos entenderem:

CLI = Command Line Interface (Interface de Linha de Comando)
É o programa que você roda no terminal/prompt de comando.
Em vez de clicar em botões, você digita comandos.

## Comandos disponíveis:

### 1. generate - Gerar plano de teste
```bash
# A partir de descrição em linguagem natural
python -m brain.src.cli generate --requirement "Testar API de login" --base-url https://api.example.com

# A partir de spec OpenAPI
python -m brain.src.cli generate --swagger ./openapi.json --output plan.json
```

### 2. run - Fluxo completo (gerar + executar)
```bash
# Gera plano e executa automaticamente
python -m brain.src.cli run --requirement "Testar API de usuários" --base-url https://api.example.com

# Com salvamento de artefatos
python -m brain.src.cli run --swagger ./api.yaml --save-plan plan.json --save-report report.json
```

## Fluxo de execução:

```
              ┌─────────────────┐
              │   CLI (este)    │
              └────────┬────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌────────┐    ┌──────────┐   ┌──────────┐
   │generate│    │ swagger  │   │   run    │
   └───┬────┘    │ (parser) │   └────┬─────┘
       │         └────┬─────┘        │
       │              │              │
       ▼              ▼              ▼
   ┌─────────────────────────────────────┐
   │         UTDLGenerator (LLM)         │
   └───────────────┬─────────────────────┘
                   │
                   ▼
   ┌─────────────────────────────────────┐
   │         run_plan (Runner)           │
   └─────────────────────────────────────┘
```

## Funcionalidades:
- Gerar planos UTDL a partir de requisitos em linguagem natural
- Gerar planos a partir de especificações OpenAPI/Swagger
- Executar o fluxo completo: geração + execução via Runner Rust
"""

# =============================================================================
# IMPORTS
# =============================================================================

from __future__ import annotations

# argparse: Biblioteca padrão para parsing de argumentos de linha de comando
import argparse

# json: Para serialização do relatório
import json

# sys: Para exit codes e stderr
import sys

# Path: Manipulação de caminhos
from pathlib import Path

# TYPE_CHECKING: Importações apenas para checagem de tipos (não em runtime)
from typing import TYPE_CHECKING

# Nossos módulos
from .generator import UTDLGenerator
from .ingestion import parse_openapi
from .ingestion.swagger import spec_to_requirement_text
from .runner import run_plan

# Importações condicionais para type checking
if TYPE_CHECKING:
    from argparse import ArgumentParser, Namespace


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================


def main() -> None:
    """
    Ponto de entrada principal do CLI.

    ## Para todos entenderem:
    Esta é a função que roda quando você executa:
    `python -m brain.src.cli`

    Ela:
    1. Configura o parser de argumentos (quais flags aceitar)
    2. Parseia os argumentos que o usuário digitou
    3. Chama a função apropriada (generate ou run)
    """
    # Cria parser principal
    parser = argparse.ArgumentParser(
        description="Brain CLI - Gera e executa planos de teste UTDL usando IA"
    )

    # subparsers permite ter comandos diferentes (generate, run)
    subparsers = parser.add_subparsers(dest="command", required=True)

    # -----------------------------------------------------------------
    # Comando: generate
    # -----------------------------------------------------------------
    gen_parser = subparsers.add_parser("generate", help="Gera um plano de teste UTDL")
    _add_common_args(gen_parser)
    gen_parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Caminho do arquivo de saída (padrão: stdout)",
    )

    # -----------------------------------------------------------------
    # Comando: run (generate + execute)
    # -----------------------------------------------------------------
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

    # Parseia os argumentos da linha de comando
    args = parser.parse_args()

    # Despacha para o comando apropriado
    if args.command == "generate":
        run_generate(args)
    elif args.command == "run":
        run_full(args)


# =============================================================================
# FUNÇÕES DE CONFIGURAÇÃO
# =============================================================================


def _add_common_args(parser: ArgumentParser) -> None:
    """
    Adiciona argumentos comuns a um subparser.

    ## Para todos entenderem:
    Os comandos "generate" e "run" compartilham alguns argumentos
    (--requirement, --swagger, etc.). Esta função evita repetição.

    ## Parâmetros:
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


# =============================================================================
# COMANDOS
# =============================================================================


def run_generate(args: Namespace) -> None:
    """
    Executa o comando generate.

    ## Para todos entenderem:
    Este comando:
    1. Obtém os requisitos (de --requirement ou --swagger)
    2. Chama o LLM para gerar o plano
    3. Imprime o JSON no stdout ou salva em arquivo

    ## Parâmetros:
        args: Argumentos parseados do CLI

    ## Exit codes:
        0: Sucesso
        1: Erro (mensagem impressa no stderr)
    """
    # Obtém texto do requisito e URL base
    requirement, base_url = _get_requirement(args)

    # Informa ao usuário (stderr para não misturar com output)
    print(f"Gerando plano UTDL usando {args.model}...", file=sys.stderr)

    try:
        # Cria gerador e gera plano
        generator = UTDLGenerator(provider=args.model)
        plan = generator.generate(requirement, base_url)

        # Serializa para JSON
        json_output = plan.to_json()

        # Salva em arquivo ou imprime no stdout
        if args.output:
            Path(args.output).write_text(json_output, encoding="utf-8")
            print(f"Plano salvo em: {args.output}", file=sys.stderr)
        else:
            print(json_output)

    except ValueError as e:
        # Erro de validação ou geração
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        # Erro inesperado
        print(f"Erro inesperado: {e}", file=sys.stderr)
        sys.exit(1)


def run_full(args: Namespace) -> None:
    """
    Executa o fluxo completo: geração + execução.

    ## Para todos entenderem:
    Este é o modo "autônomo" principal do Brain:
    1. Gera um plano UTDL usando LLM
    2. Executa o plano usando o Runner Rust
    3. Exibe o resumo dos resultados
    4. Sai com código apropriado (0=sucesso, 1=falha)

    ## Parâmetros:
        args: Argumentos parseados do CLI

    ## Exit codes:
        0: Todos os testes passaram
        1: Algum teste falhou ou erro na execução
    """
    requirement, base_url = _get_requirement(args)

    # -----------------------------------------------------------------
    # Passo 1: Gerar plano
    # -----------------------------------------------------------------

    print(f"🧠 Gerando plano UTDL usando {args.model}...", file=sys.stderr)

    try:
        generator = UTDLGenerator(provider=args.model)
        plan = generator.generate(requirement, base_url)

        # Opcionalmente salva o plano
        if args.save_plan:
            Path(args.save_plan).write_text(plan.to_json(), encoding="utf-8")
            print(f"📄 Plano salvo em: {args.save_plan}", file=sys.stderr)

        # -----------------------------------------------------------------
        # Passo 2: Executar plano
        # -----------------------------------------------------------------

        print(f"🚀 Executando plano: {plan.meta.name}...", file=sys.stderr)
        result = run_plan(plan)

        # Exibe resumo formatado
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
        # 0 = sucesso (todos passaram), 1 = falha (algum falhou)
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


# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================


def _get_requirement(args: Namespace) -> tuple[str, str]:
    """
    Extrai texto de requisito e base_url dos argumentos.

    ## Para todos entenderem:
    O usuário pode fornecer requisitos de duas formas:
    1. --requirement "Texto em linguagem natural"
    2. --swagger arquivo.yaml (converte spec para texto)

    Esta função lida com ambos os casos.

    ## Parâmetros:
        args: Argumentos parseados do CLI

    ## Retorna:
        Tupla (requirement_text, base_url)

    ## Erros:
        SystemExit: Se nem --requirement nem --swagger forem fornecidos
    """
    if args.swagger:
        # Carrega spec OpenAPI e converte para texto
        print(f"Parseando spec OpenAPI: {args.swagger}", file=sys.stderr)
        spec = parse_openapi(args.swagger)
        requirement = spec_to_requirement_text(spec)
        # Usa base_url da spec se disponível, senão usa o argumento
        base_url: str = spec.get("base_url") or args.base_url
    elif args.requirement:
        # Usa requisito direto do argumento
        requirement = args.requirement
        base_url = args.base_url
    else:
        # Nenhum dos dois foi fornecido
        print(
            "Erro: É necessário fornecer --requirement ou --swagger",
            file=sys.stderr,
        )
        sys.exit(1)

    return requirement, base_url


# =============================================================================
# PONTO DE ENTRADA
# =============================================================================

if __name__ == "__main__":
    main()
