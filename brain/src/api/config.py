"""
================================================================================
Configuração da API
================================================================================

Centraliza configurações do servidor FastAPI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class APIConfig:
    """
    Configuração do servidor API.

    ## Atributos:

    - `host`: Host para bind do servidor
    - `port`: Porta do servidor
    - `debug`: Modo debug (reload automático)
    - `cors_origins`: Lista de origens permitidas para CORS
    - `api_prefix`: Prefixo das rotas da API
    - `docs_enabled`: Se True, habilita /docs e /redoc

    ## Variáveis de ambiente:

    - `AQA_API_HOST`: Host (padrão: 0.0.0.0)
    - `AQA_API_PORT`: Porta (padrão: 8000)
    - `AQA_API_DEBUG`: Debug mode (padrão: false)
    - `AQA_API_CORS_ORIGINS`: Origens CORS separadas por vírgula
    """

    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True

    @classmethod
    def from_env(cls) -> "APIConfig":
        """
        Cria configuração a partir de variáveis de ambiente.

        ## Exemplo:

            >>> import os
            >>> os.environ["AQA_API_PORT"] = "3000"
            >>> config = APIConfig.from_env()
            >>> config.port
            3000
        """
        cors_origins_str = os.environ.get("AQA_API_CORS_ORIGINS", "*")
        cors_origins = [origin.strip() for origin in cors_origins_str.split(",")]

        return cls(
            host=os.environ.get("AQA_API_HOST", "0.0.0.0"),
            port=int(os.environ.get("AQA_API_PORT", "8000")),
            debug=os.environ.get("AQA_API_DEBUG", "false").lower() == "true",
            cors_origins=cors_origins,
            api_prefix=os.environ.get("AQA_API_PREFIX", "/api/v1"),
            docs_enabled=os.environ.get("AQA_API_DOCS", "true").lower() == "true",
        )
