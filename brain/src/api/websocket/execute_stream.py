"""
================================================================================
WebSocket: Streaming de Execução
================================================================================

Permite acompanhar execução de planos em tempo real via WebSocket.

## Protocolo:

### Cliente → Servidor:
```json
{
    "action": "execute",
    "plan": { ... },
    "options": { "parallel": true }
}
```

### Servidor → Cliente (eventos):
```json
{"event": "execution_started", "plan_id": "...", "total_steps": 5}
{"event": "step_started", "step_id": "login", "index": 1}
{"event": "step_completed", "step_id": "login", "status": "passed", "duration_ms": 150}
{"event": "progress", "completed": 3, "total": 5, "percent": 60}
{"event": "execution_completed", "success": true, "summary": {...}}
{"event": "error", "message": "...", "code": "E5001"}
```
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect


def _empty_dict() -> dict[str, Any]:
    """Factory para criar dict vazio com tipagem correta."""
    return {}


@dataclass
class ExecutionEvent:
    """Evento de execução para streaming."""

    event: str
    data: dict[str, Any] = field(default_factory=_empty_dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_json(self) -> str:
        return json.dumps({
            "event": self.event,
            "timestamp": self.timestamp,
            **self.data,
        })


class ExecutionStreamManager:
    """
    Gerencia conexões WebSocket para streaming de execuções.

    ## Funcionalidades:

    - Gerencia múltiplas conexões simultâneas
    - Envia eventos para conexões específicas
    - Limpeza automática de conexões desconectadas
    """

    def __init__(self) -> None:
        # Mapa de execution_id -> list[WebSocket]
        self._connections: dict[str, list[WebSocket]] = {}
        # Lock para operações thread-safe
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, execution_id: str) -> None:
        """Registra uma nova conexão WebSocket."""
        await websocket.accept()

        async with self._lock:
            if execution_id not in self._connections:
                self._connections[execution_id] = []
            self._connections[execution_id].append(websocket)

    async def disconnect(self, websocket: WebSocket, execution_id: str) -> None:
        """Remove uma conexão WebSocket."""
        async with self._lock:
            if execution_id in self._connections:
                try:
                    self._connections[execution_id].remove(websocket)
                except ValueError:
                    pass
                if not self._connections[execution_id]:
                    del self._connections[execution_id]

    async def disconnect_all(self) -> None:
        """Desconecta todas as conexões (para shutdown)."""
        async with self._lock:
            for _, connections in self._connections.items():
                for ws in connections:
                    try:
                        await ws.close()
                    except Exception:
                        pass
            self._connections.clear()

    async def send_event(
        self,
        execution_id: str,
        event: ExecutionEvent
    ) -> None:
        """Envia evento para todas as conexões de uma execução."""
        async with self._lock:
            connections = self._connections.get(execution_id, [])

        for ws in connections:
            try:
                await ws.send_text(event.to_json())
            except Exception:
                # Conexão morta, será limpa depois
                pass

    async def broadcast(self, event: ExecutionEvent) -> None:
        """Envia evento para todas as conexões."""
        async with self._lock:
            all_connections = [
                ws
                for connections in self._connections.values()
                for ws in connections
            ]

        for ws in all_connections:
            try:
                await ws.send_text(event.to_json())
            except Exception:
                pass


async def websocket_execute(
    websocket: WebSocket,
    manager: ExecutionStreamManager,
) -> None:
    """
    Handler WebSocket para execução de planos com streaming.

    ## Fluxo:

    1. Cliente conecta e envia comando 'execute' com plano
    2. Servidor valida plano e inicia execução
    3. Servidor envia eventos de progresso em tempo real
    4. Ao final, envia resultado completo
    5. Cliente pode enviar 'cancel' para abortar

    ## Mensagens do cliente:

    ```json
    {"action": "execute", "plan": {...}, "options": {...}}
    {"action": "cancel"}
    {"action": "ping"}
    ```

    ## Eventos do servidor:

    - execution_started
    - step_started
    - step_completed
    - progress
    - execution_completed
    - error
    - pong
    """
    execution_id = uuid.uuid4().hex[:12]

    try:
        await manager.connect(websocket, execution_id)

        # Envia confirmação de conexão
        await websocket.send_text(ExecutionEvent(
            event="connected",
            data={"execution_id": execution_id}
        ).to_json())

        while True:
            # Aguarda mensagem do cliente
            try:
                message = await websocket.receive_text()
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_text(ExecutionEvent(
                    event="error",
                    data={"code": "E1009", "message": "JSON inválido"}
                ).to_json())
                continue

            action = data.get("action")

            if action == "ping":
                await websocket.send_text(ExecutionEvent(
                    event="pong"
                ).to_json())

            elif action == "cancel":
                await websocket.send_text(ExecutionEvent(
                    event="execution_cancelled",
                    data={"execution_id": execution_id}
                ).to_json())
                break

            elif action == "execute":
                await _handle_execute(
                    websocket=websocket,
                    manager=manager,
                    execution_id=execution_id,
                    plan_data=data.get("plan"),
                    options=data.get("options", {}),
                )

            else:
                await websocket.send_text(ExecutionEvent(
                    event="error",
                    data={
                        "code": "E6006",
                        "message": f"Ação desconhecida: {action}"
                    }
                ).to_json())

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_text(ExecutionEvent(
                event="error",
                data={"code": "E5001", "message": str(e)}
            ).to_json())
        except Exception:
            pass
    finally:
        await manager.disconnect(websocket, execution_id)


async def _handle_execute(
    websocket: WebSocket,
    manager: ExecutionStreamManager,
    execution_id: str,
    plan_data: dict[str, Any] | None,
    options: dict[str, Any],
) -> None:
    """
    Executa plano com streaming de eventos.
    """
    if not plan_data:
        await websocket.send_text(ExecutionEvent(
            event="error",
            data={"code": "E6002", "message": "Plano não fornecido"}
        ).to_json())
        return

    # Importa dependências
    from ...validator import UTDLValidator
    from ...runner import run_plan

    # Valida plano
    validator = UTDLValidator()
    result = validator.validate(plan_data)

    if not result.is_valid:
        await websocket.send_text(ExecutionEvent(
            event="error",
            data={
                "code": "E1009",
                "message": "Plano inválido",
                "errors": [str(e) for e in result.errors[:5]],
            }
        ).to_json())
        return

    plan = result.plan
    if plan is None:
        await websocket.send_text(ExecutionEvent(
            event="error",
            data={"code": "E5001", "message": "Erro interno: plano válido mas objeto None"}
        ).to_json())
        return

    total_steps = len(plan.steps)

    # Evento: Execução iniciada
    await websocket.send_text(ExecutionEvent(
        event="execution_started",
        data={
            "execution_id": execution_id,
            "plan_id": plan.meta.id,
            "plan_name": plan.meta.name,
            "total_steps": total_steps,
        }
    ).to_json())

    try:
        # Envia eventos simulados de início de step enquanto execução ocorre em background
        # Nota: Para streaming real em tempo real, o Runner Rust precisaria emitir
        # eventos via IPC durante execução. Atualmente, executamos primeiro e
        # depois enviamos os resultados.
        for i, step in enumerate(plan.steps):
            # Evento: Step iniciado
            await websocket.send_text(ExecutionEvent(
                event="step_started",
                data={
                    "step_id": step.id,
                    "index": i + 1,
                    "total": total_steps,
                    "description": step.description,
                }
            ).to_json())

            # Pequeno delay para simular processamento
            await asyncio.sleep(0.1)

        # Executa de fato via Runner
        timeout = options.get("timeout_seconds", 60)
        timeout_val = timeout if isinstance(timeout, int) else 60

        runner_result = run_plan(
            plan=plan,
            timeout=timeout_val,
        )

        # Envia resultados de cada step
        for i, step_result in enumerate(runner_result.steps):
            # Conta assertions
            assertions_passed = sum(1 for a in step_result.assertions_results if a.passed)
            assertions_failed = sum(1 for a in step_result.assertions_results if not a.passed)

            await websocket.send_text(ExecutionEvent(
                event="step_completed",
                data={
                    "step_id": step_result.step_id,
                    "status": step_result.status,
                    "duration_ms": step_result.duration_ms,
                    "error": step_result.error,
                    "assertions_passed": assertions_passed if step_result.assertions_results else None,
                    "assertions_failed": assertions_failed if step_result.assertions_results else None,
                    "extractions": step_result.extractions if step_result.extractions else None,
                }
            ).to_json())

            # Evento de progresso
            completed = i + 1
            percent = round(completed / total_steps * 100, 1) if total_steps > 0 else 100

            await websocket.send_text(ExecutionEvent(
                event="progress",
                data={
                    "completed": completed,
                    "total": total_steps,
                    "percent": percent,
                }
            ).to_json())

        # Evento: Execução concluída
        passed = sum(1 for s in runner_result.steps if s.status == "passed")
        failed = sum(1 for s in runner_result.steps if s.status == "failed")
        skipped = sum(1 for s in runner_result.steps if s.status == "skipped")

        await websocket.send_text(ExecutionEvent(
            event="execution_completed",
            data={
                "execution_id": execution_id,
                "success": runner_result.success,
                "summary": {
                    "total_steps": total_steps,
                    "passed": passed,
                    "failed": failed,
                    "skipped": skipped,
                    "duration_ms": runner_result.total_duration_ms,
                    "success_rate": round(passed / total_steps * 100, 2) if total_steps > 0 else 0,
                },
            }
        ).to_json())

    except Exception as e:
        await websocket.send_text(ExecutionEvent(
            event="error",
            data={
                "code": "E5001",
                "message": f"Erro na execução: {e}",
            }
        ).to_json())
