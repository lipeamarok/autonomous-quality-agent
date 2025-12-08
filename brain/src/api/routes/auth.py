"""
================================================================================
Rota: /auth
================================================================================

Endpoints para gerenciamento de autenticação e API keys.

## Endpoints:

- GET /auth/status - Status da autenticação
- POST /auth/keys - Criar nova API key (requer master key)
- GET /auth/keys - Listar API keys (requer master key)
- DELETE /auth/keys/{prefix} - Revogar API key (requer master key)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..auth import (
    AuthMode,
    get_auth_config,
    get_key_store,
    require_master_key,
)


router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================


class AuthStatusResponse(BaseModel):
    """Status da autenticação."""

    enabled: bool = Field(..., description="Se autenticação está habilitada")
    mode: str = Field(..., description="Modo de autenticação: none, apikey")
    message: str = Field(..., description="Mensagem descritiva")


class CreateKeyRequest(BaseModel):
    """Request para criar API key."""

    description: str = Field(
        default="",
        description="Descrição da key (ex: 'CI/CD Pipeline')",
        examples=["CI/CD Pipeline", "Development Key"],
    )


class CreateKeyResponse(BaseModel):
    """Response com a API key criada."""

    success: bool = Field(True)
    api_key: str = Field(..., description="API key (mostrada apenas uma vez!)")
    prefix: str = Field(..., description="Prefixo para identificação")
    message: str = Field(default="Guarde esta key em local seguro. Ela não será mostrada novamente.")


class KeyInfo(BaseModel):
    """Informações de uma API key."""

    prefix: str = Field(..., description="Prefixo da key (primeiros 8 chars)")
    description: str = Field(..., description="Descrição da key")
    created_at: str = Field(..., description="Data de criação (ISO)")
    last_used_at: str | None = Field(None, description="Último uso (ISO)")
    usage_count: int = Field(..., description="Total de usos")


class ListKeysResponse(BaseModel):
    """Response da listagem de keys."""

    success: bool = Field(True)
    keys: list[KeyInfo] = Field(default=[], description="Lista de API keys")
    total: int = Field(..., description="Total de keys")


class RevokeKeyResponse(BaseModel):
    """Response da revogação de key."""

    success: bool = Field(True)
    message: str = Field(..., description="Mensagem de confirmação")


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get(
    "/status",
    response_model=AuthStatusResponse,
    summary="Status da Autenticação",
    description="Retorna informações sobre o modo de autenticação configurado.",
)
async def get_auth_status() -> AuthStatusResponse:
    """Retorna status da autenticação."""
    config = get_auth_config()

    if config.mode == AuthMode.NONE:
        message = "Autenticação desabilitada. Todos os endpoints são públicos."
    else:
        message = f"Autenticação via {config.mode.value}. Endpoints protegidos requerem X-API-Key."

    return AuthStatusResponse(
        enabled=config.is_enabled,
        mode=config.mode.value,
        message=message,
    )


@router.post(
    "/keys",
    response_model=CreateKeyResponse,
    summary="Criar API Key",
    description="""
Cria uma nova API key.

**⚠️ Importante**: A key completa é mostrada apenas uma vez nesta resposta.
Guarde-a em local seguro.

**Requer**: Master key no header X-API-Key
    """,
    responses={
        401: {"description": "Master key não fornecida"},
        403: {"description": "Master key inválida"},
        503: {"description": "Gerenciamento de keys não configurado"},
    },
)
async def create_api_key(
    request: CreateKeyRequest,
    _master_key: str = Depends(require_master_key),
) -> CreateKeyResponse:
    """Cria uma nova API key."""
    store = get_key_store()
    key = store.create_key(request.description)

    return CreateKeyResponse(
        success=True,
        api_key=key,
        prefix=key[:8] + "...",
        message="Guarde esta key em local seguro. Ela não será mostrada novamente.",
    )


@router.get(
    "/keys",
    response_model=ListKeysResponse,
    summary="Listar API Keys",
    description="""
Lista todas as API keys cadastradas.

**Nota**: Os valores das keys não são revelados, apenas os prefixos.

**Requer**: Master key no header X-API-Key
    """,
    responses={
        401: {"description": "Master key não fornecida"},
        403: {"description": "Master key inválida"},
    },
)
async def list_api_keys(
    _master_key: str = Depends(require_master_key),
) -> ListKeysResponse:
    """Lista todas as API keys."""
    store = get_key_store()
    keys_data = store.list_keys()

    keys: list[KeyInfo] = []
    for k in keys_data:
        created_at = datetime.fromtimestamp(k["created_at"], tz=timezone.utc).isoformat()
        last_used_at = None
        if k["last_used_at"]:
            last_used_at = datetime.fromtimestamp(k["last_used_at"], tz=timezone.utc).isoformat()

        keys.append(KeyInfo(
            prefix=k["prefix"],
            description=k["description"],
            created_at=created_at,
            last_used_at=last_used_at,
            usage_count=k["usage_count"],
        ))

    return ListKeysResponse(
        success=True,
        keys=keys,
        total=len(keys),
    )


@router.delete(
    "/keys/{key_value}",
    response_model=RevokeKeyResponse,
    summary="Revogar API Key",
    description="""
Revoga uma API key existente.

**Nota**: Após revogada, a key não pode ser recuperada.

**Requer**: Master key no header X-API-Key
    """,
    responses={
        401: {"description": "Master key não fornecida"},
        403: {"description": "Master key inválida"},
        404: {"description": "Key não encontrada"},
    },
)
async def revoke_api_key(
    key_value: str,
    _master_key: str = Depends(require_master_key),
) -> RevokeKeyResponse:
    """Revoga uma API key."""
    store = get_key_store()

    if not store.revoke(key_value):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "E4004",
                "message": "API key não encontrada",
                "hint": "Verifique se a key existe e está correta",
            },
        )

    return RevokeKeyResponse(
        success=True,
        message=f"API key revogada com sucesso",
    )
