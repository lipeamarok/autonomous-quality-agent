const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8080"

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown
  ) {
    super(message)
    this.name = "ApiError"
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  const data = await response.json().catch(() => ({}))

  if (!response.ok) {
    throw new ApiError(
      response.status,
      data.code || "UNKNOWN",
      data.message || data.detail || "An error occurred",
      data.details
    )
  }

  return data as T
}

export const api = {
  get: async <T>(path: string): Promise<T> => {
    const response = await fetch(`${API_URL}${path}`, {
      headers: {
        Accept: "application/json",
      },
    })
    return handleResponse<T>(response)
  },

  post: async <T>(path: string, body?: unknown): Promise<T> => {
    const response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    })
    return handleResponse<T>(response)
  },

  delete: async <T>(path: string): Promise<T> => {
    const response = await fetch(`${API_URL}${path}`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    })
    return handleResponse<T>(response)
  },
}

// API Endpoints
export const endpoints = {
  health: "/api/v1/health",
  generate: "/api/v1/generate",
  validate: "/api/v1/validate",
  execute: "/api/v1/execute",
  history: "/api/v1/history",
  historyStats: "/api/v1/history/stats",
  plans: "/api/v1/plans",
} as const
