import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api, endpoints } from "@/lib/api/client"
import type {
  HealthResponse,
  GenerateRequest,
  GenerateResponse,
  ValidateRequest,
  ValidateResponse,
  ExecuteRequest,
  ExecuteResponse,
  HistoryResponse,
  HistoryStatsResponse,
  PlansResponse,
} from "@/types/api"

// Health
export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<HealthResponse>(endpoints.health),
    refetchInterval: 30000, // Check every 30s
  })
}

// Generate
export function useGenerate() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: GenerateRequest) =>
      api.post<GenerateResponse>(endpoints.generate, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] })
    },
  })
}

// Validate
export function useValidate() {
  return useMutation({
    mutationFn: (data: ValidateRequest) =>
      api.post<ValidateResponse>(endpoints.validate, data),
  })
}

// Execute
export function useExecute() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (data: ExecuteRequest) =>
      api.post<ExecuteResponse>(endpoints.execute, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["history"] })
    },
  })
}

// History
export function useHistory(options?: { limit?: number; page?: number; status?: string }) {
  const { limit = 20, page = 1, status } = options || {}

  return useQuery({
    queryKey: ["history", limit, page, status],
    queryFn: () => {
      let url = `${endpoints.history}?limit=${limit}&page=${page}`
      if (status && status !== "all") {
        url += `&status=${status}`
      }
      return api.get<HistoryResponse>(url)
    },
  })
}

export function useHistoryStats() {
  return useQuery({
    queryKey: ["history", "stats"],
    queryFn: () => api.get<HistoryStatsResponse>(endpoints.historyStats),
  })
}

export function useExecutionDetails(executionId: string | null) {
  return useQuery({
    queryKey: ["history", executionId],
    queryFn: () =>
      api.get<ExecuteResponse>(`${endpoints.history}/${executionId}`),
    enabled: !!executionId,
  })
}

// Plans
export function usePlans() {
  return useQuery({
    queryKey: ["plans"],
    queryFn: () => api.get<PlansResponse>(endpoints.plans),
  })
}

export function usePlan(planId: string | null) {
  return useQuery({
    queryKey: ["plans", planId],
    queryFn: () => api.get<{ success: boolean; plan: import("@/types/api").Plan }>(
      `${endpoints.plans}/${planId}`
    ),
    enabled: !!planId,
  })
}
