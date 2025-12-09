"use client"

import Link from "next/link"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Wand2, Play, FileJson, Upload } from "lucide-react"

const actions = [
  {
    title: "Generate Plan",
    description: "Create a test plan from requirements or OpenAPI spec",
    icon: Wand2,
    href: "/generate",
    variant: "default" as const,
  },
  {
    title: "Execute Plan",
    description: "Run an existing test plan",
    icon: Play,
    href: "/execute",
    variant: "outline" as const,
  },
  {
    title: "View Plans",
    description: "Browse and manage saved plans",
    icon: FileJson,
    href: "/plans",
    variant: "outline" as const,
  },
  {
    title: "Import OpenAPI",
    description: "Import an OpenAPI specification",
    icon: Upload,
    href: "/generate?mode=import",
    variant: "outline" as const,
  },
]

export function QuickActions() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base font-medium">Quick Actions</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2">
          {actions.map((action) => (
            <Link key={action.href} href={action.href}>
              <Button
                variant={action.variant}
                className="w-full h-auto py-4 flex-col items-start gap-1"
              >
                <div className="flex items-center gap-2">
                  <action.icon className="h-4 w-4" />
                  <span className="font-medium">{action.title}</span>
                </div>
                <span className="text-xs font-normal text-muted-foreground">
                  {action.description}
                </span>
              </Button>
            </Link>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
