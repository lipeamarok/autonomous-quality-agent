"""
================================================================================
API Module — FastAPI Backend for AQA UI
================================================================================

Este módulo expõe as funcionalidades do Brain via API REST e WebSocket,
permitindo que uma interface de usuário interaja com o sistema sem
depender do CLI.

## Endpoints disponíveis:

| Método | Endpoint              | Descrição                        |
|--------|----------------------|----------------------------------|
| GET    | /health              | Health check e versão            |
| GET    | /api/v1/auth/status  | Status da autenticação           |
| POST   | /api/v1/auth/keys    | Criar API key (master key)       |
| POST   | /api/v1/generate     | Gerar plano UTDL via LLM         |
| POST   | /api/v1/validate     | Validar plano UTDL               |
| POST   | /api/v1/execute      | Executar plano via Runner        |
| GET    | /api/v1/history      | Listar histórico de execuções    |
| GET    | /api/v1/plans        | Listar planos versionados        |
| POST   | /api/v1/workspace/init | Inicializar workspace          |
| WS     | /ws/execute          | Streaming de execução            |

## Autenticação:

Quando AQA_AUTH_MODE=apikey, endpoints protegidos requerem header X-API-Key.

## Uso:

```python
from src.api import create_app

app = create_app()
# ou via CLI: aqa serve
```
"""

from .app import create_app
from .config import APIConfig
from .auth import AuthConfig, AuthMode, require_api_key, get_auth_config

__all__ = [
    "create_app",
    "APIConfig",
    "AuthConfig",
    "AuthMode",
    "require_api_key",
    "get_auth_config",
]
