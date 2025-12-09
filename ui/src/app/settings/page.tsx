"use client"

import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { Badge } from "@/components/ui/badge"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useHealth } from "@/lib/hooks/queries"
import { useSettings, defaultSettings } from "@/lib/hooks/use-settings"
import { useTheme } from "@/lib/hooks/use-theme"
import {
  Server,
  Palette,
  Bell,
  Database,
  RefreshCw,
  CheckCircle,
  XCircle,
  Loader2,
  Save,
  RotateCcw,
  Brain,
  Zap,
} from "lucide-react"

const AVAILABLE_MODELS = [
  { value: "gpt-4-turbo", label: "GPT-4 Turbo" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 Turbo" },
  { value: "claude-3-opus", label: "Claude 3 Opus" },
  { value: "claude-3-sonnet", label: "Claude 3 Sonnet" },
]

export default function SettingsPage() {
  const { data: health, isLoading: healthLoading, refetch: refetchHealth } = useHealth()
  const { settings, updateSettings, resetSettings, isLoaded } = useSettings()
  const { theme, setTheme } = useTheme()

  const handleSaveSettings = () => {
    // Settings are auto-saved via updateSettings, this is just for UX
    toast.success("Settings saved successfully")
  }

  const handleResetSettings = () => {
    resetSettings()
    setTheme("system")
    toast.info("Settings reset to defaults")
  }

  if (!isLoaded) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-semibold">Settings</h1>
        <p className="text-muted-foreground">
          Configure application preferences
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Server className="h-5 w-5" />
            <CardTitle className="text-lg">API Connection</CardTitle>
          </div>
          <CardDescription>
            Configure the connection to the AQA API server
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="api-url">API Base URL</Label>
            <Input
              id="api-url"
              value={settings.apiUrl}
              onChange={(e) => updateSettings({ apiUrl: e.target.value })}
              placeholder="http://localhost:8080"
            />
          </div>

          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Connection Status</Label>
              <p className="text-sm text-muted-foreground">
                Current API server status
              </p>
            </div>
            <div className="flex items-center gap-2">
              {healthLoading ? (
                <Badge variant="outline">
                  <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  Checking...
                </Badge>
              ) : health?.status === "healthy" ? (
                <Badge className="bg-green-100 text-green-700">
                  <CheckCircle className="h-3 w-3 mr-1" />
                  Connected
                </Badge>
              ) : (
                <Badge className="bg-red-100 text-red-700">
                  <XCircle className="h-3 w-3 mr-1" />
                  Disconnected
                </Badge>
              )}
              <Button
                variant="ghost"
                size="icon"
                onClick={() => refetchHealth()}
                disabled={healthLoading}
              >
                <RefreshCw className={`h-4 w-4 ${healthLoading ? "animate-spin" : ""}`} />
              </Button>
            </div>
          </div>

          {health && (
            <div className="bg-muted rounded-lg p-3 space-y-1 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Version:</span>
                <span className="font-mono">{health.version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Runner:</span>
                <span className="font-mono">{health.runner_available ? "Available" : "Unavailable"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Brain:</span>
                <span className="font-mono">{health.brain_available ? "Available" : "Unavailable"}</span>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5" />
            <CardTitle className="text-lg">LLM Defaults</CardTitle>
          </div>
          <CardDescription>
            Configure default settings for plan generation
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Default Model</Label>
              <Select
                value={settings.defaultModel}
                onValueChange={(value) => updateSettings({ defaultModel: value })}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select model" />
                </SelectTrigger>
                <SelectContent>
                  {AVAILABLE_MODELS.map((model) => (
                    <SelectItem key={model.value} value={model.value}>
                      {model.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Default LLM Mode</Label>
              <Select
                value={settings.defaultLlmMode}
                onValueChange={(value: "real" | "mock") => updateSettings({ defaultLlmMode: value })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="real">Real (API calls)</SelectItem>
                  <SelectItem value="mock">Mock (testing)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5" />
            <CardTitle className="text-lg">Execution Defaults</CardTitle>
          </div>
          <CardDescription>
            Configure default settings for plan execution
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="default-timeout">Default Timeout (seconds)</Label>
              <Input
                id="default-timeout"
                type="number"
                min={1}
                max={3600}
                value={settings.defaultTimeout}
                onChange={(e) => updateSettings({ defaultTimeout: Number(e.target.value) })}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="default-retries">Default Max Retries</Label>
              <Input
                id="default-retries"
                type="number"
                min={0}
                max={10}
                value={settings.defaultMaxRetries}
                onChange={(e) => updateSettings({ defaultMaxRetries: Number(e.target.value) })}
              />
            </div>
          </div>
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Live Streaming</Label>
              <p className="text-sm text-muted-foreground">
                Enable WebSocket streaming for real-time results
              </p>
            </div>
            <Switch
              checked={settings.useStreaming}
              onCheckedChange={(value) => updateSettings({ useStreaming: value })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Palette className="h-5 w-5" />
            <CardTitle className="text-lg">Appearance</CardTitle>
          </div>
          <CardDescription>
            Customize the look and feel of the application
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>Theme</Label>
            <Select value={theme} onValueChange={setTheme}>
              <SelectTrigger className="w-48">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="light">Light</SelectItem>
                <SelectItem value="dark">Dark</SelectItem>
                <SelectItem value="system">System</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Bell className="h-5 w-5" />
            <CardTitle className="text-lg">Notifications</CardTitle>
          </div>
          <CardDescription>
            Configure notification preferences
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Enable Notifications</Label>
              <p className="text-sm text-muted-foreground">
                Show toast notifications for actions
              </p>
            </div>
            <Switch
              checked={settings.notifications}
              onCheckedChange={(value) => updateSettings({ notifications: value })}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Database className="h-5 w-5" />
            <CardTitle className="text-lg">Data & Refresh</CardTitle>
          </div>
          <CardDescription>
            Configure data fetching behavior
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <Label>Auto-Refresh Data</Label>
              <p className="text-sm text-muted-foreground">
                Automatically refresh data in the background
              </p>
            </div>
            <Switch
              checked={settings.autoRefresh}
              onCheckedChange={(value) => updateSettings({ autoRefresh: value })}
            />
          </div>

          {settings.autoRefresh && (
            <div className="space-y-2">
              <Label htmlFor="refresh-interval">Refresh Interval (seconds)</Label>
              <Input
                id="refresh-interval"
                type="number"
                min={10}
                max={300}
                value={settings.refreshInterval}
                onChange={(e) => updateSettings({ refreshInterval: Number(e.target.value) })}
                className="w-32"
              />
            </div>
          )}
        </CardContent>
      </Card>

      <Separator />

      <div className="flex justify-between">
        <Button variant="outline" onClick={handleResetSettings}>
          <RotateCcw className="h-4 w-4 mr-2" />
          Reset to Defaults
        </Button>
        <Button onClick={handleSaveSettings}>
          <Save className="h-4 w-4 mr-2" />
          Save Settings
        </Button>
      </div>
    </div>
  )
}
