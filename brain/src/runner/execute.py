"""
================================================================================
MÓDULO DE INTEGRAÇÃO COM O RUNNER
================================================================================

Este módulo é a "cola" entre o Brain (Python) e o Runner (Rust).
Ele executa planos UTDL chamando o binário Rust via subprocess.

## Para todos entenderem:

O Brain gera planos de teste em Python, mas quem executa de verdade
é o Runner (escrito em Rust, para performance). Este módulo:

1. Pega o plano gerado pelo Brain
2. Salva em arquivo temporário
3. Chama o executável do Runner
4. Lê o relatório de resultados
5. Retorna os resultados em formato Python

## Por que separar Brain e Runner?

- **Python (Brain)**: Ótimo para IA/ML, fácil de escrever
- **Rust (Runner)**: Muito rápido, seguro para concorrência

## Fluxo de execução:

```
    Brain (Python)         Runner (Rust)
         │                      │
    [Gera Plano]                │
         │                      │
    [Salva JSON] ─────────> [Lê JSON]
         │                      │
         │                 [Executa HTTP]
         │                      │
    [Lê Relatório] <─────── [Gera Relatório]
         │                      │
    [Retorna Resultados]        │
```

## Funcionalidades:
- Serialização automática do plano para arquivo temporário
- Execução do Runner com timeout configurável
- Parsing do relatório de execução JSON
- Limpeza automática de arquivos temporários
"""

# =============================================================================
# IMPORTS - Bibliotecas necessárias
# =============================================================================

from __future__ import annotations

# json: Para ler o relatório de resultados
import json

# subprocess: Para executar o binário do Runner
import subprocess

# tempfile: Para criar arquivos temporários seguros
import tempfile

# dataclass: Simplifica criação de classes de dados
from dataclasses import dataclass, field

# Path: Manipulação de caminhos cross-platform
from pathlib import Path

# typing: Anotações de tipo
from typing import Any

# Plan: Nosso modelo de plano UTDL
from ..validator import Plan


# =============================================================================
# CLASSES DE RESULTADO
# =============================================================================


@dataclass
class StepResult:
    """
    Resultado da execução de um único step.

    ## Para todos entenderem:
    Cada step (requisição HTTP, wait, etc.) gera um resultado.
    Esta classe guarda as informações desse resultado.

    ## Atributos:
        step_id: Identificador único do step executado.
            Exemplo: "login", "get_users", "step_1"

        status: Status da execução.
            Valores: "passed" (sucesso), "failed" (falhou), "skipped" (pulado)

        duration_ms: Tempo de execução em milissegundos.
            Exemplo: 150.5 (= 150.5ms = 0.15 segundos)

        error: Mensagem de erro, se houver falha.
            Exemplo: "Connection refused" ou None se sucesso
    """

    step_id: str
    status: str
    duration_ms: float
    error: str | None = None


@dataclass
class RunnerResult:
    """
    Resultado da execução de um plano completo.

    ## Para todos entenderem:
    Quando executamos um plano inteiro (vários steps), queremos saber:
    - Quantos passaram? Quantos falharam?
    - Quanto tempo levou no total?
    - Quais foram os erros específicos?

    Esta classe agrega todas essas informações.

    ## Atributos:
        plan_id: ID único do plano executado (UUID).
        plan_name: Nome legível do plano (ex: "Teste de Login").
        total_steps: Número total de steps no plano.
        passed: Número de steps que passaram.
        failed: Número de steps que falharam.
        skipped: Número de steps pulados (dependência falhou).
        total_duration_ms: Tempo total de execução em ms.
        steps: Lista de resultados individuais de cada step.
        raw_report: Relatório JSON bruto do Runner (para debug).
    """

    plan_id: str
    plan_name: str
    total_steps: int
    passed: int
    failed: int
    skipped: int
    total_duration_ms: float
    # default_factory cria nova lista para cada instância
    steps: list[StepResult] = field(default_factory=list)  # type: ignore[var-annotated]
    raw_report: dict[str, Any] = field(default_factory=dict)  # type: ignore[var-annotated]

    @property
    def success(self) -> bool:
        """
        Retorna True se nenhum step falhou.

        ## Para todos entenderem:
        @property transforma um método em um atributo.
        Em vez de chamar `result.success()`, chamamos `result.success`.
        """
        return self.failed == 0

    def summary(self) -> str:
        """
        Gera um resumo formatado da execução.

        ## Para todos entenderem:
        Cria uma string bonita para exibir no terminal:
        ```
        ✓ PASSOU | Teste de Login
        Steps: 5/5 passaram, 0 falharam, 0 pulados
        Duração: 1234.56ms
        ```

        ## Retorna:
            String multilinha com status, contadores e duração
        """
        # Escolhe emoji baseado no resultado
        status = "✓ PASSOU" if self.success else "✗ FALHOU"

        return (
            f"{status} | {self.plan_name}\n"
            f"Steps: {self.passed}/{self.total_steps} passaram, "
            f"{self.failed} falharam, {self.skipped} pulados\n"
            f"Duração: {self.total_duration_ms:.2f}ms"
        )


# =============================================================================
# FUNÇÃO PRINCIPAL DE EXECUÇÃO
# =============================================================================


def run_plan(
    plan: Plan,
    runner_path: str | None = None,
    timeout: int = 60,
    max_steps: int | None = None,
    max_retries: int = 3,
) -> RunnerResult:
    """
    Executa um plano UTDL usando o Runner Rust.

    ## Para todos entenderem:
    Esta é a função principal! Ela:
    1. Pega o plano Python e salva como JSON
    2. Executa o Runner (programa Rust)
    3. Lê os resultados e retorna em Python

    ## Como funciona internamente:
    1. Se runner_path não foi dado, procura o executável automaticamente
    2. Serializa o plano para um arquivo temporário
    3. Executa: `runner execute --file plan.json --output report.json`
    4. Parseia o report.json para RunnerResult
    5. Limpa os arquivos temporários

    ## Parâmetros:
        plan: Objeto Plan validado (do módulo validator).
            Já passou por todas as validações Pydantic.

        runner_path: Caminho para o executável do Runner.
            Se None, procura automaticamente em:
            - runner/target/release/runner.exe (produção)
            - runner/target/debug/runner.exe (desenvolvimento)

        timeout: Timeout de execução em segundos.
            Default: 60 segundos. Após isso, aborta.

        max_steps: Máximo de steps a executar.
            None = sem limite. Útil para debug parcial.

        max_retries: Número de retries para steps falhando.
            Default: 3. O Runner pode tentar novamente steps
            com falhas transitórias (ex: 503 Service Unavailable).

    ## Retorna:
        RunnerResult com detalhes da execução.

    ## Erros possíveis:
        RuntimeError: Se o Runner não for encontrado,
                     timeout excedido, ou falha no parse.

    ## Exemplo:
        >>> plan = Plan(...)
        >>> result = run_plan(plan)
        >>> if result.success:
        ...     print("Todos os testes passaram!")
        ... else:
        ...     for step in result.steps:
        ...         if step.error:
        ...             print(f"{step.step_id}: {step.error}")
    """
    # -----------------------------------------------------------------
    # Passo 1: Encontrar o executável do Runner
    # -----------------------------------------------------------------

    if runner_path is None:
        # Calcula o caminho do projeto
        # __file__ = este arquivo (execute.py)
        # .parent = runner/ -> src/ -> brain/ -> project_root/
        project_root = Path(__file__).parent.parent.parent.parent.parent

        # Tenta release primeiro (mais rápido)
        release_path = project_root / "runner" / "target" / "release" / "runner.exe"
        debug_path = project_root / "runner" / "target" / "debug" / "runner.exe"

        if release_path.exists():
            runner_path = str(release_path)
        elif debug_path.exists():
            runner_path = str(debug_path)
        else:
            raise RuntimeError(
                "Runner não encontrado. Por favor, compile o Runner primeiro:\n"
                "  cd runner && cargo build --release"
            )

    # -----------------------------------------------------------------
    # Passo 1.5: Aplicar limite de steps (se configurado)
    # -----------------------------------------------------------------

    execution_plan = plan
    if max_steps is not None and max_steps > 0:
        if max_steps < len(plan.steps):
            # Cria cópia do plano com apenas os primeiros N steps
            limited_steps = plan.steps[:max_steps]
            execution_plan = Plan(
                spec_version=plan.spec_version,
                meta=plan.meta,
                config=plan.config,
                steps=limited_steps,
            )

    # -----------------------------------------------------------------
    # Passo 2: Criar arquivo temporário para o plano
    # -----------------------------------------------------------------

    # NamedTemporaryFile cria arquivo com nome único
    # delete=False porque precisamos do arquivo após fechar
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as plan_file:
        # Serializa o plano para JSON e escreve no arquivo
        plan_file.write(execution_plan.to_json())
        plan_path = plan_file.name  # Guarda o caminho

    # -----------------------------------------------------------------
    # Passo 3: Criar arquivo temporário para o relatório
    # -----------------------------------------------------------------

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".json",
        delete=False,
        encoding="utf-8",
    ) as report_file:
        report_path = report_file.name

    # -----------------------------------------------------------------
    # Passo 4: Executar o Runner
    # -----------------------------------------------------------------

    try:
        # Monta comando base
        cmd = [
            runner_path,  # Executável
            "execute",  # Comando
            "--file",  # Flag
            plan_path,  # Arquivo de entrada
            "--output",  # Flag
            report_path,  # Arquivo de saída
        ]

        # Adiciona max_retries se diferente do default
        if max_retries != 3:
            cmd.extend(["--max-retries", str(max_retries)])

        # subprocess.run executa comando externo
        subprocess.run(
            cmd,
            capture_output=True,  # Captura stdout/stderr
            text=True,  # Retorna como string (não bytes)
            timeout=timeout,  # Timeout em segundos
            check=False,  # Não lança exceção em exit code != 0
        )

        # -----------------------------------------------------------------
        # Passo 5: Ler e parsear o relatório
        # -----------------------------------------------------------------

        report_text = Path(report_path).read_text(encoding="utf-8")
        report: dict[str, Any] = json.loads(report_text)

        # Converte o relatório bruto para nosso objeto tipado
        return _parse_report(report)

    except subprocess.TimeoutExpired as exc:
        # Runner demorou demais
        raise RuntimeError(f"Runner excedeu timeout de {timeout} segundos") from exc

    except json.JSONDecodeError as exc:
        # Relatório não é JSON válido
        raise RuntimeError(f"Falha ao parsear relatório do Runner: {exc}") from exc

    except FileNotFoundError as exc:
        # Executável não encontrado
        raise RuntimeError(f"Executável do Runner não encontrado: {runner_path}") from exc

    finally:
        # -----------------------------------------------------------------
        # Limpeza: Remove arquivos temporários
        # -----------------------------------------------------------------
        # finally executa SEMPRE, mesmo se houver exceção
        # missing_ok=True evita erro se o arquivo não existir
        Path(plan_path).unlink(missing_ok=True)
        Path(report_path).unlink(missing_ok=True)


# =============================================================================
# FUNÇÕES AUXILIARES (Internas)
# =============================================================================


def _parse_report(report: dict[str, Any]) -> RunnerResult:
    """
    Parseia o relatório JSON do Runner para um RunnerResult.

    ## Para todos entenderem:
    O Runner gera um JSON com a estrutura:
    ```json
    {
      "plan": {"id": "...", "name": "..."},
      "summary": {"total": 5, "passed": 4, "failed": 1},
      "results": [{"step_id": "...", "status": "..."}]
    }
    ```

    Esta função converte isso para nossos objetos Python tipados.

    ## Parâmetros:
        report: Dicionário com o relatório bruto do Runner

    ## Retorna:
        Objeto RunnerResult com os dados estruturados
    """
    # Extrai seções do relatório
    plan_info: dict[str, Any] = report.get("plan", {})
    summary: dict[str, Any] = report.get("summary", {})

    # Converte cada resultado de step
    steps: list[StepResult] = []
    for step_result in report.get("results", []):
        steps.append(
            StepResult(
                step_id=step_result.get("step_id", "unknown"),
                status=step_result.get("status", "unknown"),
                duration_ms=step_result.get("duration_ms", 0),
                error=step_result.get("error"),
            )
        )

    # Monta o objeto final
    return RunnerResult(
        plan_id=plan_info.get("id", "unknown"),
        plan_name=plan_info.get("name", "Plano Desconhecido"),
        total_steps=summary.get("total", len(steps)),
        passed=summary.get("passed", 0),
        failed=summary.get("failed", 0),
        skipped=summary.get("skipped", 0),
        total_duration_ms=summary.get("total_duration_ms", 0),
        steps=steps,
        raw_report=report,
    )
