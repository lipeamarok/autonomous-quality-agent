# API Mocks para Desenvolvimento UI

Este diretório contém mocks das respostas da API para desenvolvimento offline da UI.

## Arquivos

| Arquivo | Endpoint | Descrição |
|---------|----------|-----------|
| `health.json` | `GET /api/v1/health` | Status de saúde da API |
| `generate.json` | `POST /api/v1/generate` | Plano UTDL gerado |
| `validate.json` | `POST /api/v1/validate` | Resultado de validação |
| `execute.json` | `POST /api/v1/execute` | Resultado de execução completo |
| `history.json` | `GET /api/v1/history` | Lista de execuções |
| `history-stats.json` | `GET /api/v1/history/stats` | Estatísticas do histórico |
| `plans.json` | `GET /api/v1/plans` | Lista de planos salvos |
| `websocket-events.json` | `WS /ws/execute/{id}` | Eventos WebSocket de exemplo |

## Uso no Next.js

### Opção 1: Variável de ambiente

```typescript
// lib/api/client.ts
const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === 'true'

export async function fetchWithMock<T>(
  path: string,
  mockFile: string,
  options?: RequestInit
): Promise<T> {
  if (USE_MOCKS) {
    const mock = await import(`@/mocks/${mockFile}`)
    return mock.default as T
  }
  
  const response = await fetch(`${API_URL}${path}`, options)
  return response.json()
}
```

### Opção 2: MSW (Mock Service Worker)

```typescript
// mocks/handlers.ts
import { http, HttpResponse } from 'msw'
import health from './health.json'
import generate from './generate.json'
import execute from './execute.json'
import history from './history.json'
import historyStats from './history-stats.json'
import plans from './plans.json'
import validate from './validate.json'

export const handlers = [
  http.get('/api/v1/health', () => {
    return HttpResponse.json(health)
  }),
  
  http.post('/api/v1/generate', () => {
    return HttpResponse.json(generate)
  }),
  
  http.post('/api/v1/validate', () => {
    return HttpResponse.json(validate)
  }),
  
  http.post('/api/v1/execute', () => {
    return HttpResponse.json(execute)
  }),
  
  http.get('/api/v1/history', () => {
    return HttpResponse.json(history)
  }),
  
  http.get('/api/v1/history/stats', () => {
    return HttpResponse.json(historyStats)
  }),
  
  http.get('/api/v1/plans', () => {
    return HttpResponse.json(plans)
  }),
]
```

### Opção 3: Next.js API Routes (recomendado para dev)

Copie esses arquivos para `ui/app/api/mocks/` e crie route handlers:

```typescript
// ui/app/api/v1/health/route.ts
import { NextResponse } from 'next/server'
import mock from '@/mocks/health.json'

export async function GET() {
  // Simula latência
  await new Promise(resolve => setTimeout(resolve, 200))
  return NextResponse.json(mock)
}
```

## Simulando WebSocket

Para simular eventos WebSocket durante desenvolvimento:

```typescript
// hooks/use-mock-websocket.ts
import events from '@/mocks/websocket-events.json'

export function useMockWebSocket(onEvent: (event: WsEvent) => void) {
  useEffect(() => {
    let index = 0
    
    const interval = setInterval(() => {
      if (index < events.length) {
        onEvent(events[index] as WsEvent)
        index++
      } else {
        clearInterval(interval)
      }
    }, 500) // Emite um evento a cada 500ms
    
    return () => clearInterval(interval)
  }, [onEvent])
}
```

## Cenários de Teste

Os mocks incluem diferentes cenários:

- ✅ **Sucesso**: Maioria dos steps passando
- ❌ **Falha**: Um step falhando com assertion error
- 🔄 **Retry**: Step com 2 tentativas antes de falhar
- ⏭️ **Skip**: Um step pulado por dependência

Isso permite testar a UI em diferentes estados sem backend.
