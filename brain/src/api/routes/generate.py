"""
================================================================================
Rota: /generate
================================================================================

Geração de planos UTDL via LLM.

## Funcionalidades:

- Gerar plano a partir de descrição textual
- Gerar plano a partir de especificação OpenAPI/Swagger
- Cache de planos gerados
"""

from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from ..deps import get_generator
from typing import Any

from ..schemas.generate import GenerateRequest, GenerateResponse, GenerateErrorResponse
from ...generator import UTDLGenerator
from ...ingestion import parse_openapi
from ...ingestion.swagger import spec_to_requirement_text


def _extract_base_url_from_swagger(swagger: dict[str, Any], default: str) -> str:
    """
    Extrai base_url da especificação OpenAPI.

    ## Parâmetros:
        swagger: Dict com especificação OpenAPI
        default: URL padrão se não encontrar

    ## Retorna:
        URL do primeiro server ou o default
    """
    servers = swagger.get("servers")
    # servers vem de dict[str, Any], então precisa de validação runtime
    if not isinstance(servers, list) or len(servers) == 0:  # type: ignore[arg-type]
        return default

    first_server = servers[0]  # type: ignore[index]
    if not isinstance(first_server, dict):
        return default

    url = first_server.get("url")  # type: ignore[union-attr]
    if not isinstance(url, str):
        return default

    return url


router = APIRouter()


@router.post(
    "",
    response_model=GenerateResponse,
    responses={
        400: {"model": GenerateErrorResponse, "description": "Erro na geração"},
        422: {"description": "Erro de validação do request"},
    },
    summary="Gerar Plano UTDL",
    description="""
Gera um plano de teste UTDL usando LLM.

## Modos de uso:

1. **Via texto livre**: Forneça `requirement` com descrição em linguagem natural
2. **Via OpenAPI**: Forneça `swagger` com a especificação da API

## Exemplo:

```json
{
    "requirement": "Testar endpoint de login com credenciais válidas e inválidas",
    "base_url": "https://api.example.com",
    "include_auth": true
}
```
    """,
)
async def generate_plan(
    request: GenerateRequest,
    generator: UTDLGenerator = Depends(get_generator),
) -> GenerateResponse:
    """
    Gera um plano de teste UTDL.

    ## Parâmetros:

    - **requirement**: Descrição em linguagem natural
    - **swagger**: Especificação OpenAPI (alternativa ao requirement)
    - **base_url**: URL base da API
    - **include_negative**: Incluir casos de teste negativos
    - **include_auth**: Detectar e incluir autenticação

    ## Retorna:

    Plano UTDL gerado e validado, pronto para execução.
    """
    start_time = time.time()

    # Valida que pelo menos um input foi fornecido
    if not request.requirement and not request.swagger:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "E6002",
                "message": "Forneça 'requirement' ou 'swagger' para gerar o plano",
            },
        )

    try:
        # Se swagger foi fornecido, converte para requirement text
        requirement = request.requirement
        base_url = request.base_url

        if request.swagger:
            # Parseia e converte swagger para texto
            parsed = parse_openapi(request.swagger, validate_spec=False)
            requirement = spec_to_requirement_text(parsed)

            # Se base_url não foi fornecida, tenta extrair do swagger
            if base_url == "https://api.example.com":
                base_url = _extract_base_url_from_swagger(request.swagger, base_url)

        if not requirement:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "E6003",
                    "message": "Não foi possível extrair requisitos do input fornecido",
                },
            )

        # Gera o plano
        plan = generator.generate(
            requirement=requirement,
            base_url=base_url,
            skip_cache=request.skip_cache,
        )

        # Calcula tempo de geração
        generation_time_ms = (time.time() - start_time) * 1000

        # Obtém metadados da geração
        metadata = generator.get_last_generation_metadata()

        return GenerateResponse(
            success=True,
            plan=plan.to_dict(),
            cached=metadata.cached if metadata else False,
            provider=metadata.provider if metadata else None,
            model=metadata.model if metadata else None,
            tokens_used=metadata.tokens_used if metadata else None,
            generation_time_ms=generation_time_ms,
        )

    except HTTPException:
        raise
    except Exception as e:
        # Trata erros de geração
        error_message = str(e)

        # Verifica se é erro de validação
        if "validation" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "E6004",
                    "message": f"Erro de validação no plano gerado: {error_message}",
                },
            )

        # Verifica se é erro de LLM
        if "api" in error_message.lower() or "key" in error_message.lower():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "E6005",
                    "message": f"Erro de comunicação com LLM: {error_message}",
                },
            )

        # Erro genérico
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "E6001",
                "message": f"Erro ao gerar plano: {error_message}",
            },
        )
