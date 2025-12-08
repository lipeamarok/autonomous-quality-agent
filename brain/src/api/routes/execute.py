"""
================================================================================
Rota: /execute
================================================================================

Execução de planos UTDL via Runner.

## Responsabilidades:

1. Receber planos (inline, arquivo ou gerar via LLM)
2. Validar antes de executar
3. Invocar o Runner Rust
4. Registrar no histórico
5. Retornar resultados formatados
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_generator, get_validator, get_execution_history
from ..schemas.execute import (
    ExecuteRequest,
    ExecuteResponse,
    ExecuteSummary,
    StepResultSchema,
)
from ...generator import UTDLGenerator
from ...validator import UTDLValidator
from ...runner import run_plan, RunnerResult
from ...cache import ExecutionHistory


router = APIRouter()


def _create_summary(result: RunnerResult) -> ExecuteSummary:
    """
    Cria resumo estatístico da execução.

    ## Parâmetros:
        result: Resultado do Runner com steps executados

    ## Retorna:
        ExecuteSummary com contadores e taxa de sucesso
    """
    total = len(result.steps)
    passed = sum(1 for s in result.steps if s.status == "passed")
    failed = sum(1 for s in result.steps if s.status == "failed")
    skipped = sum(1 for s in result.steps if s.status == "skipped")

    success_rate = (passed / total * 100) if total > 0 else 0.0

    return ExecuteSummary(
        total_steps=total,
        passed=passed,
        failed=failed,
        skipped=skipped,
        total_duration_ms=result.total_duration_ms,
        success_rate=round(success_rate, 2),
    )


def _create_step_results(result: RunnerResult) -> list[StepResultSchema]:
    """
    Converte resultados do Runner para schema da API.

    ## Parâmetros:
        result: Resultado do Runner

    ## Retorna:
        Lista de StepResultSchema para serialização
    """
    step_results: list[StepResultSchema] = []

    for step in result.steps:
        # Garante que status é um dos valores válidos
        step_status: Literal["passed", "failed", "skipped"]
        if step.status == "passed":
            step_status = "passed"
        elif step.status == "skipped":
            step_status = "skipped"
        else:
            step_status = "failed"

        step_results.append(
            StepResultSchema(
                step_id=step.step_id,
                status=step_status,
                duration_ms=step.duration_ms,
                error=step.error,
                assertions_passed=None,  # TODO: extrair do raw_report
                assertions_failed=None,
                extractions=None,
            )
        )

    return step_results


@router.post(
    "",
    response_model=ExecuteResponse,
    summary="Executar Plano UTDL",
    description="""
Executa um plano de teste UTDL usando o Runner de alta performance.

## Modos de execução:

1. **Plano inline**: Forneça `plan` com o plano completo
2. **Arquivo de plano**: Forneça `plan_file` com o caminho
3. **Gerar e executar**: Forneça `requirement` ou `swagger`

## Opções:

- **parallel**: Executar steps em paralelo (quando possível)
- **timeout_seconds**: Timeout global
- **dry_run**: Validar sem executar
- **save_report**: Salvar no histórico
    """,
)
async def execute_plan(
    request: ExecuteRequest,
    generator: UTDLGenerator = Depends(get_generator),
    validator: UTDLValidator = Depends(get_validator),
    history: ExecutionHistory = Depends(get_execution_history),
) -> ExecuteResponse:
    """
    Executa um plano de teste UTDL.

    ## Fluxo:

    1. Obtém plano (inline, arquivo ou gerado)
    2. Valida o plano
    3. Executa via Runner Rust
    4. Opcionalmente salva no histórico
    5. Retorna resultados
    """
    generated_plan = False
    plan_dict: dict[str, Any] | None = None

    # Determina a fonte do plano
    if request.plan:
        # Plano inline
        plan_dict = request.plan

    elif request.plan_file:
        # Arquivo de plano
        plan_path = Path(request.plan_file)
        if not plan_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "E4001",
                    "message": f"Arquivo de plano não encontrado: {request.plan_file}",
                },
            )
        try:
            with open(plan_path) as f:
                plan_dict = json.load(f)
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "E1009",
                    "message": f"JSON inválido no arquivo: {e}",
                },
            )

    elif request.requirement or request.swagger:
        # Gerar e executar
        from ...ingestion import parse_openapi
        from ...ingestion.swagger import spec_to_requirement_text

        requirement = request.requirement
        base_url = request.base_url or "https://api.example.com"

        if request.swagger:
            parsed = parse_openapi(request.swagger, validate_spec=False)
            requirement = spec_to_requirement_text(parsed)

            servers = request.swagger.get("servers", [])
            if servers and not request.base_url:
                base_url = servers[0].get("url", base_url)

        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "E6003",
                    "message": "Não foi possível extrair requisitos",
                },
            )

        try:
            plan = generator.generate(requirement=requirement, base_url=base_url)
            plan_dict = plan.to_dict()
            generated_plan = True
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "E6001",
                    "message": f"Erro ao gerar plano: {e}",
                },
            )

    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "E6002",
                "message": "Forneça 'plan', 'plan_file', 'requirement' ou 'swagger'",
            },
        )

    # Valida o plano
    if plan_dict is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "E6002",
                "message": "Nenhum plano foi fornecido ou gerado",
            },
        )

    validation_result = validator.validate(plan_dict)
    if not validation_result.is_valid:
        error_messages = validation_result.errors[:5]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "E1009",
                "message": "Plano inválido",
                "validation_errors": error_messages,
            },
        )

    # O plano validado é garantidamente não-None aqui
    plan_obj = validation_result.plan
    if plan_obj is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "E5001",
                "message": "Erro interno: plano válido mas objeto None",
            },
        )

    # Se dry_run, retorna sem executar
    if request.dry_run:
        steps_count = len(plan_obj.steps)

        return ExecuteResponse(
            success=True,
            execution_id=None,
            plan_id=plan_obj.meta.id,
            plan_name=plan_obj.meta.name,
            summary=ExecuteSummary(
                total_steps=steps_count,
                passed=0,
                failed=0,
                skipped=steps_count,
                total_duration_ms=0,
                success_rate=0,
            ),
            steps=[],
            report_saved=False,
            generated_plan=generated_plan,
        )

    try:
        # Executa via Runner - run_plan aceita Plan diretamente
        result = run_plan(
            plan=plan_obj,
            timeout=request.timeout_seconds,
        )

        # Salva no histórico se solicitado
        report_saved = False
        execution_id: str | None = None

        if request.save_report:
            try:
                # Determina status final
                exec_status: Literal["success", "failure", "error"] = (
                    "success" if result.success else "failure"
                )

                record = history.record_execution(
                    plan_file=request.plan_file or "inline",
                    duration_ms=int(result.total_duration_ms),
                    total_steps=len(result.steps),
                    passed_steps=sum(1 for s in result.steps if s.status == "passed"),
                    failed_steps=sum(1 for s in result.steps if s.status == "failed"),
                    status=exec_status,
                    runner_report=result.raw_report,
                )
                execution_id = record.id
                report_saved = True
            except Exception:
                # Não falha se histórico der erro
                pass

        # Monta resposta
        return ExecuteResponse(
            success=result.success,
            execution_id=execution_id,
            plan_id=plan_obj.meta.id,
            plan_name=plan_obj.meta.name,
            summary=_create_summary(result),
            steps=_create_step_results(result),
            report_saved=report_saved,
            generated_plan=generated_plan,
        )

    except RuntimeError as e:
        # Erro do Runner (não encontrado, timeout, etc.)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "E5002",
                "message": f"Erro no Runner: {e}",
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "E5001",
                "message": f"Erro na execução: {e}",
            },
        )
