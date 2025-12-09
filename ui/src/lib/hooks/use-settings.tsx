"use client"

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react"

// Settings schema
export interface AppSettings {
  apiUrl: string
  notifications: boolean
  autoRefresh: boolean
  refreshInterval: number
  defaultTimeout: number
  defaultMaxRetries: number
  defaultLlmMode: "real" | "mock"
  defaultModel: string
  useStreaming: boolean
}

const defaultSettings: AppSettings = {
  apiUrl: "http://localhost:8080",
  notifications: true,
  autoRefresh: true,
  refreshInterval: 30,
  defaultTimeout: 300,
  defaultMaxRetries: 3,
  defaultLlmMode: "real",
  defaultModel: "gpt-4-turbo",
  useStreaming: true,
}

const STORAGE_KEY = "aqa-settings"

// Load settings from localStorage
function loadSettings(): AppSettings {
  if (typeof window === "undefined") return defaultSettings
  
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) {
      const parsed = JSON.parse(stored)
      // Merge with defaults to handle new fields
      return { ...defaultSettings, ...parsed }
    }
  } catch (e) {
    console.error("Failed to load settings:", e)
  }
  return defaultSettings
}

// Save settings to localStorage
function saveSettings(settings: AppSettings): void {
  if (typeof window === "undefined") return
  
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings))
  } catch (e) {
    console.error("Failed to save settings:", e)
  }
}

interface SettingsContextValue {
  settings: AppSettings
  updateSettings: (updates: Partial<AppSettings>) => void
  resetSettings: () => void
  isLoaded: boolean
}

const SettingsContext = createContext<SettingsContextValue | null>(null)

export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<AppSettings>(defaultSettings)
  const [isLoaded, setIsLoaded] = useState(false)

  // Load settings on mount
  useEffect(() => {
    const loaded = loadSettings()
    setSettings(loaded)
    setIsLoaded(true)
  }, [])

  const updateSettings = useCallback((updates: Partial<AppSettings>) => {
    setSettings((prev) => {
      const newSettings = { ...prev, ...updates }
      saveSettings(newSettings)
      return newSettings
    })
  }, [])

  const resetSettings = useCallback(() => {
    setSettings(defaultSettings)
    saveSettings(defaultSettings)
  }, [])

  return (
    <SettingsContext.Provider value={{ settings, updateSettings, resetSettings, isLoaded }}>
      {children}
    </SettingsContext.Provider>
  )
}

export function useSettings() {
  const context = useContext(SettingsContext)
  if (!context) {
    throw new Error("useSettings must be used within a SettingsProvider")
  }
  return context
}

// Export defaults for use in components
export { defaultSettings }
