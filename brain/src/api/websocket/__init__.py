"""
================================================================================
WebSocket Handlers
================================================================================

Handlers para conexões WebSocket, especialmente streaming de execução.
"""

from .execute_stream import ExecutionStreamManager, websocket_execute

__all__ = ["ExecutionStreamManager", "websocket_execute"]
