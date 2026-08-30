import { DashboardSummaryCard } from "@/components/DashboardSummaryCard";
import { CostTrendChart } from "@/components/CostTrendChart";
import { TopModelsTable } from "@/components/TopModelsTable";
import { TopUsersTable } from "@/components/TopUsersTable";
import { SavingsCard } from "@/components/SavingsCard";
import { RecommendationsCard } from "@/components/RecommendationsCard";
import { OptimizationPanel } from "@/components/OptimizationPanel";

export default function HomePage() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
      <DashboardSummaryCard />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SavingsCard />
        <OptimizationPanel />
      </div>
      <RecommendationsCard />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CostTrendChart />
        <TopModelsTable />
      </div>
      <TopUsersTable />
    </div>
  );
}
