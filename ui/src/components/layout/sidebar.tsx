"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  LayoutDashboard,
  Wand2,
  FileJson,
  Play,
  History,
  Settings,
  Zap,
} from "lucide-react"

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/generate", label: "Generate", icon: Wand2 },
  { href: "/plans", label: "Plans", icon: FileJson },
  { href: "/execute", label: "Execute", icon: Play },
  { href: "/history", label: "History", icon: History },
  { href: "/settings", label: "Settings", icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-64 border-r bg-card h-screen sticky top-0 flex flex-col">
      <div className="p-6 border-b">
        <div className="flex items-center gap-2">
          <div className="p-2 rounded-lg bg-primary">
            <Zap className="h-5 w-5 text-primary-foreground" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">AQA</h1>
            <p className="text-xs text-muted-foreground">Quality Agent</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/" && pathname.startsWith(item.href))
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          )
        })}
      </nav>

      <div className="p-4 border-t">
        <div className="text-xs text-muted-foreground text-center">
          <p className="truncate">AQA v0.5.0</p>
        </div>
      </div>
    </aside>
  )
}
