"use client"

import { useEffect, useRef, useState, useCallback } from "react"
import type { WsEvent } from "@/types/api"

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8080"

interface UseWebSocketOptions {
  onEvent?: (event: WsEvent) => void
  autoConnect?: boolean
}

export function useExecutionWebSocket(
  executionId: string | null,
  options: UseWebSocketOptions = {}
) {
  const { onEvent, autoConnect = true } = options
  const ws = useRef<WebSocket | null>(null)
  const [events, setEvents] = useState<WsEvent[]>([])
  const [isConnected, setIsConnected] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const connect = useCallback(() => {
    if (!executionId) return

    try {
      ws.current = new WebSocket(`${WS_URL}/ws/execute/${executionId}`)

      ws.current.onopen = () => {
        setIsConnected(true)
        setError(null)
      }

      ws.current.onclose = () => {
        setIsConnected(false)
      }

      ws.current.onerror = () => {
        setIsConnected(false)
        setError("WebSocket connection failed")
      }

      ws.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as WsEvent
          setEvents((prev) => [...prev, data])
          onEvent?.(data)
        } catch {
          console.error("Failed to parse WebSocket message")
        }
      }
    } catch {
      setError("Failed to connect to WebSocket")
    }
  }, [executionId, onEvent])

  const disconnect = useCallback(() => {
    ws.current?.close()
    ws.current = null
    setIsConnected(false)
  }, [])

  const reset = useCallback(() => {
    setEvents([])
    setError(null)
  }, [])

  useEffect(() => {
    if (autoConnect && executionId) {
      connect()
    }
    return () => disconnect()
  }, [autoConnect, executionId, connect, disconnect])

  return {
    events,
    isConnected,
    error,
    connect,
    disconnect,
    reset,
  }
}
