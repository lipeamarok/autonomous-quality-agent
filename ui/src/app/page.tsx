import { StatsCards } from "@/components/dashboard/stats-cards"
import { RecentExecutions } from "@/components/dashboard/recent-executions"
import { QuickActions } from "@/components/dashboard/quick-actions"

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="text-muted-foreground">
          Overview of your API testing activity
        </p>
      </div>

      <StatsCards />

      <div className="grid gap-6 lg:grid-cols-2">
        <RecentExecutions />
        <QuickActions />
      </div>
    </div>
  )
}
