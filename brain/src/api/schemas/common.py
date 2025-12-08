"""
================================================================================
Schemas Comuns da API
================================================================================

Modelos base reutilizados em múltiplos endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


T = TypeVar("T")


class ErrorDetail(BaseModel):
    """
    Detalhes de um erro estruturado.

    ## Atributos:

    - `code`: Código de erro (ex: E1001, E2003)
    - `message`: Mensagem legível do erro
    - `path`: Caminho JSON onde o erro ocorreu (opcional)
    - `suggestion`: Sugestão de correção (opcional)
    """

    code: str = Field(..., description="Código de erro estruturado", examples=["E1001"])
    message: str = Field(..., description="Mensagem legível do erro")
    path: str | None = Field(None, description="Caminho JSON do erro (ex: $.steps[0].action)")
    suggestion: str | None = Field(None, description="Sugestão de como corrigir")


class ErrorResponse(BaseModel):
    """
    Resposta de erro padronizada.

    ## Exemplo:

        {
            "success": false,
            "error": {
                "code": "E6001",
                "message": "Falha ao gerar plano",
                "suggestion": "Verifique sua API key"
            }
        }
    """

    success: bool = Field(False, description="Sempre false para erros")
    error: ErrorDetail = Field(..., description="Detalhes do erro")
    request_id: str | None = Field(None, description="ID da requisição para debug")


class SuccessResponse(BaseModel, Generic[T]):
    """
    Resposta de sucesso padronizada.

    ## Exemplo:

        {
            "success": true,
            "data": { ... },
            "message": "Operação concluída"
        }
    """

    success: bool = Field(True, description="Sempre true para sucesso")
    data: T = Field(..., description="Dados da resposta")
    message: str | None = Field(None, description="Mensagem informativa opcional")
    request_id: str | None = Field(None, description="ID da requisição para debug")


class APIResponse(BaseModel):
    """
    Resposta genérica da API (usada quando tipo de data é dinâmico).
    """

    success: bool = Field(..., description="Se a operação foi bem-sucedida")
    data: Any | None = Field(None, description="Dados da resposta")
    error: ErrorDetail | None = Field(None, description="Detalhes do erro, se houver")
    message: str | None = Field(None, description="Mensagem informativa")
    request_id: str | None = Field(None, description="ID da requisição")


class HealthResponse(BaseModel):
    """
    Resposta do health check.
    """

    status: str = Field(..., description="Status do serviço", examples=["healthy"])
    version: str = Field(..., description="Versão do AQA", examples=["0.3.0"])
    timestamp: datetime = Field(..., description="Timestamp do check")
    components: dict[str, str] = Field(
        default_factory=dict,
        description="Status dos componentes internos"
    )


class PaginationParams(BaseModel):
    """
    Parâmetros de paginação para listagens.
    """

    page: int = Field(1, ge=1, description="Número da página (1-indexed)")
    limit: int = Field(20, ge=1, le=100, description="Itens por página")
    
    @property
    def offset(self) -> int:
        """Calcula offset para queries."""
        return (self.page - 1) * self.limit


class PaginatedResponse(BaseModel, Generic[T]):
    """
    Resposta paginada.
    """

    success: bool = True
    data: list[T] = Field(..., description="Lista de itens")
    total: int = Field(..., description="Total de itens (sem paginação)")
    page: int = Field(..., description="Página atual")
    limit: int = Field(..., description="Itens por página")
    pages: int = Field(..., description="Total de páginas")
