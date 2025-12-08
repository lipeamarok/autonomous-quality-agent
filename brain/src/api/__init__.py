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
| POST   | /api/v1/generate     | Gerar plano UTDL via LLM         |
| POST   | /api/v1/validate     | Validar plano UTDL               |
| POST   | /api/v1/execute      | Executar plano via Runner        |
| GET    | /api/v1/history      | Listar histórico de execuções    |
| POST   | /api/v1/workspace/init | Inicializar workspace          |
| WS     | /ws/execute          | Streaming de execução            |

## Uso:

```python
from src.api import create_app

app = create_app()
# ou via CLI: aqa serve
```
"""

from .app import create_app
from .config import APIConfig

__all__ = ["create_app", "APIConfig"]
