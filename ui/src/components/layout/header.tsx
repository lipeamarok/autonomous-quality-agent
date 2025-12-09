"use client"

import { usePathname } from "next/navigation"
import Link from "next/link"
import { useHealth } from "@/lib/hooks/queries"
import { Badge } from "@/components/ui/badge"
import { Circle, ChevronRight, Home } from "lucide-react"
import { ThemeToggle } from "./theme-toggle"

// Route label mapping
const routeLabels: Record<string, string> = {
  "": "Dashboard",
  "generate": "Generate",
  "execute": "Execute",
  "history": "History",
  "plans": "Plans",
  "settings": "Settings",
  "edit": "Edit",
}

function Breadcrumbs() {
  const pathname = usePathname()
  const segments = pathname.split("/").filter(Boolean)

  if (segments.length === 0) {
    return (
      <div className="flex items-center gap-2 text-sm">
        <Home className="h-4 w-4" />
        <span className="font-medium">Dashboard</span>
      </div>
    )
  }

  return (
    <nav className="flex items-center gap-1 text-sm">
      <Link
        href="/"
        className="flex items-center gap-1 text-muted-foreground hover:text-foreground transition-colors"
      >
        <Home className="h-4 w-4" />
      </Link>
      
      {segments.map((segment, index) => {
        const path = "/" + segments.slice(0, index + 1).join("/")
        const isLast = index === segments.length - 1
        
        // Determine label - use mapping or capitalize segment
        const label = routeLabels[segment] || 
          (segment.match(/^[a-f0-9-]+$/i) 
            ? `#${segment.slice(0, 8)}...` // IDs get truncated
            : segment.charAt(0).toUpperCase() + segment.slice(1))

        return (
          <div key={path} className="flex items-center gap-1">
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            {isLast ? (
              <span className="font-medium">{label}</span>
            ) : (
              <Link
                href={path}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {label}
              </Link>
            )}
          </div>
        )
      })}
    </nav>
  )
}

export function Header() {
  const { data: health, isLoading } = useHealth()

  return (
    <header className="h-14 border-b bg-card px-6 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <Breadcrumbs />
      </div>

      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          {isLoading ? (
            <Badge variant="outline" className="gap-1.5">
              <Circle className="h-2 w-2 fill-muted-foreground text-muted-foreground" />
              Connecting...
            </Badge>
          ) : health?.status === "healthy" ? (
            <Badge variant="outline" className="gap-1.5">
              <Circle className="h-2 w-2 fill-green-500 text-green-500" />
              API Online
            </Badge>
          ) : (
            <Badge variant="destructive" className="gap-1.5">
              <Circle className="h-2 w-2 fill-current" />
              API Offline
            </Badge>
          )}
        </div>
        <ThemeToggle />
      </div>
    </header>
  )
}
