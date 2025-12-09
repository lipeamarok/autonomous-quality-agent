"use client"

import { useState } from "react"
import Link from "next/link"
import { toast } from "sonner"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Input } from "@/components/ui/input"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { usePlans } from "@/lib/hooks/queries"
import {
  FileJson,
  Play,
  Search,
  MoreVertical,
  Eye,
  Edit,
  Trash2,
  Copy,
  Clock,
  CheckCircle,
  AlertCircle,
  Plus,
  Loader2,
} from "lucide-react"
import type { PlanSummary } from "@/types/api"

function PlanCard({ plan }: { plan: PlanSummary }) {
  const lastRunStatus = plan.last_run_status

  const statusBadge = lastRunStatus ? (
    lastRunStatus === "passed" ? (
      <Badge className="bg-green-100 text-green-700">
        <CheckCircle className="h-3 w-3 mr-1" />
        Passed
      </Badge>
    ) : (
      <Badge className="bg-red-100 text-red-700">
        <AlertCircle className="h-3 w-3 mr-1" />
        Failed
      </Badge>
    )
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      <Clock className="h-3 w-3 mr-1" />
      Never Run
    </Badge>
  )

  const handleDelete = () => {
    toast.info("Delete plan", {
      description: "This feature is not yet implemented",
    })
  }

  const handleDuplicate = () => {
    toast.info("Duplicate plan", {
      description: "This feature is not yet implemented",
    })
  }

  return (
    <Card className="hover:shadow-md transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2">
            <FileJson className="h-5 w-5 text-primary" />
            <CardTitle className="text-base">{plan.name}</CardTitle>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-8 w-8">
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/plans/${plan.id}`}>
                  <Eye className="h-4 w-4 mr-2" />
                  View
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem asChild>
                <Link href={`/plans/${plan.id}/edit`}>
                  <Edit className="h-4 w-4 mr-2" />
                  Edit
                </Link>
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleDuplicate}>
                <Copy className="h-4 w-4 mr-2" />
                Duplicate
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem
                onClick={handleDelete}
                className="text-red-600 focus:text-red-600"
              >
                <Trash2 className="h-4 w-4 mr-2" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
        {plan.description && (
          <CardDescription className="line-clamp-2">
            {plan.description}
          </CardDescription>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-4 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <FileJson className="h-3.5 w-3.5" />
              {plan.step_count} steps
            </span>
            {plan.version && (
              <span className="flex items-center gap-1">
                v{plan.version}
              </span>
            )}
          </div>
          {statusBadge}
        </div>

        <div className="flex gap-2">
          <Button asChild variant="outline" size="sm" className="flex-1">
            <Link href={`/plans/${plan.id}`}>
              <Eye className="h-4 w-4 mr-2" />
              View
            </Link>
          </Button>
          <Button asChild size="sm" className="flex-1">
            <Link href={`/execute?plan=${plan.id}`}>
              <Play className="h-4 w-4 mr-2" />
              Execute
            </Link>
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export default function PlansPage() {
  const [search, setSearch] = useState("")
  const { data, isLoading, error } = usePlans()

  const filteredPlans = data?.plans.filter((plan) =>
    plan.name.toLowerCase().includes(search.toLowerCase()) ||
    plan.description?.toLowerCase().includes(search.toLowerCase())
  ) ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Test Plans</h1>
          <p className="text-muted-foreground">
            Manage and execute your UTDL test plans
          </p>
        </div>
        <Button asChild>
          <Link href="/generate">
            <Plus className="h-4 w-4 mr-2" />
            Generate Plan
          </Link>
        </Button>
      </div>

      <div className="flex items-center gap-4">
        <div className="relative flex-1 max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search plans..."
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        </div>
      ) : error ? (
        <Card className="py-12">
          <div className="flex flex-col items-center justify-center text-center">
            <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
            <h3 className="text-lg font-medium">Error loading plans</h3>
            <p className="text-muted-foreground mb-4">
              {error instanceof Error ? error.message : "Unknown error"}
            </p>
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => window.location.reload()}>
                <Loader2 className="h-4 w-4 mr-2" />
                Retry
              </Button>
              <Button asChild>
                <Link href="/generate">
                  <Plus className="h-4 w-4 mr-2" />
                  Generate Plan
                </Link>
              </Button>
            </div>
          </div>
        </Card>
      ) : filteredPlans.length === 0 ? (
        <Card className="py-12">
          <div className="flex flex-col items-center justify-center text-center">
            <FileJson className="h-12 w-12 text-muted-foreground opacity-50 mb-4" />
            {search ? (
              <>
                <h3 className="text-lg font-medium">No plans found</h3>
                <p className="text-muted-foreground">
                  Try a different search term
                </p>
              </>
            ) : (
              <>
                <h3 className="text-lg font-medium">No plans yet</h3>
                <p className="text-muted-foreground mb-4">
                  Generate your first test plan to get started
                </p>
                <Button asChild>
                  <Link href="/generate">
                    <Plus className="h-4 w-4 mr-2" />
                    Generate Plan
                  </Link>
                </Button>
              </>
            )}
          </div>
        </Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredPlans.map((plan) => (
            <PlanCard key={plan.id} plan={plan} />
          ))}
        </div>
      )}
    </div>
  )
}
