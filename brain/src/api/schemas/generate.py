"""
================================================================================
Schemas para /generate
================================================================================

Request e Response para geração de planos UTDL.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GenerateRequest(BaseModel):
    """
    Request para gerar um plano UTDL.

    ## Modos de uso:

    1. Via texto livre (requirement):
        ```json
        {
            "requirement": "Testar login com credenciais válidas e inválidas",
            "base_url": "https://api.example.com"
        }
        ```

    2. Via OpenAPI spec (swagger):
        ```json
        {
            "swagger": { "openapi": "3.0.0", ... },
            "base_url": "https://api.example.com"
        }
        ```
    """

    requirement: str | None = Field(
        None,
        description="Descrição em linguagem natural do que testar",
        examples=["Testar endpoint de login com credenciais válidas e inválidas"]
    )
    swagger: dict[str, Any] | None = Field(
        None,
        description="Especificação OpenAPI/Swagger como objeto JSON"
    )
    base_url: str = Field(
        "https://api.example.com",
        description="URL base da API a ser testada",
        examples=["https://api.example.com", "http://localhost:8080"]
    )
    model: str | None = Field(
        None,
        description="Modelo LLM a usar (sobrescreve config). Ex: gpt-4, grok-2"
    )
    include_negative: bool = Field(
        False,
        description="Incluir casos de teste negativos (campos inválidos, etc.)"
    )
    include_auth: bool = Field(
        False,
        description="Detectar e incluir step de autenticação automaticamente"
    )
    skip_cache: bool = Field(
        False,
        description="Ignorar cache e forçar regeneração"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "requirement": "Testar API de login com email e senha",
                    "base_url": "https://api.example.com",
                    "include_auth": True
                },
                {
                    "swagger": {"openapi": "3.0.0", "info": {"title": "API", "version": "1.0"}},
                    "base_url": "https://api.example.com",
                    "include_negative": True
                }
            ]
        }
    }


class GenerateResponse(BaseModel):
    """
    Response da geração de plano UTDL.

    ## Exemplo:

        {
            "success": true,
            "plan": { "spec_version": "0.1", "meta": {...}, "steps": [...] },
            "cached": false,
            "provider": "openai",
            "tokens_used": 1500
        }
    """

    success: bool = Field(True, description="Se a geração foi bem-sucedida")
    plan: dict[str, Any] = Field(..., description="Plano UTDL gerado")
    cached: bool = Field(False, description="Se o plano veio do cache")
    provider: str | None = Field(None, description="Provider LLM usado (ex: openai, xai)")
    model: str | None = Field(None, description="Modelo LLM usado (ex: gpt-4)")
    tokens_used: int | None = Field(None, description="Tokens consumidos na geração")
    generation_time_ms: float | None = Field(None, description="Tempo de geração em ms")


class GenerateErrorResponse(BaseModel):
    """
    Response de erro na geração.
    """

    success: bool = Field(False)
    error: str = Field(..., description="Mensagem de erro")
    error_code: str | None = Field(None, description="Código de erro estruturado")
    validation_errors: list[str] | None = Field(
        None,
        description="Lista de erros de validação do plano gerado"
    )
