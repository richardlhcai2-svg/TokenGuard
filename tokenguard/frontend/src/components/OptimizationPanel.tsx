"use client";

import { useEffect, useState } from "react";
import { getOptimizations, getBudgetStatus, type OptimizationAction, type OptimizationReport, type BudgetStatus } from "@/lib/api";

function fmt(n: number | string): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  return `$${v.toFixed(2)}`;
}

const priorityColors: Record<string, string> = {
  high: "text-red-600 bg-red-50",
  medium: "text-yellow-600 bg-yellow-50",
  low: "text-blue-600 bg-blue-50",
};

export function OptimizationPanel() {
  const [report, setReport] = useState<OptimizationReport | null>(null);
  const [budget, setBudget] = useState<BudgetStatus | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      getOptimizations(30, 1),
      getBudgetStatus(),
    ])
      .then(([r, b]) => {
        setReport(r);
        setBudget(b);
      })
      .catch(() => setLoading(false))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Cost Optimization</h2>
        <div className="h-40 animate-pulse text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  const noData = !report || report.action_count === 0;
  const savings = report ? parseFloat(String(report.total_savings_usd)) : 0;

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold">Cost Optimization</h2>
        {savings > 0 && (
          <span className="rounded-full bg-green-100 px-3 py-1 text-sm font-medium text-green-700">
            Save up to {fmt(report!.total_savings_usd)}/mo
          </span>
        )}
      </div>

      {noData ? (
        <div className="text-sm text-muted-foreground">
          No optimization opportunities found. Your model usage is already efficient.
        </div>
      ) : (
        <div className="space-y-4">
          {/* Budget gauge */}
          {budget && parseFloat(String(budget.monthly_limit_usd)) > 0 && (
            <BudgetGauge budget={budget} />
          )}

          {/* Actions */}
          <div className="space-y-2">
            {report!.actions.slice(0, 5).map((action) => (
              <OptimizationActionCard
                key={`${action.current_model}-${action.task_type}`}
                action={action}
              />
            ))}
            {report!.action_count > 5 && (
              <p className="text-xs text-muted-foreground text-center pt-1">
                +{report!.action_count - 5} more optimization{report!.action_count - 5 > 1 ? "s" : ""}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function BudgetGauge({ budget }: { budget: BudgetStatus }) {
  const pct = budget.usage_pct;
  const barColor =
    pct >= 1.0 ? "bg-destructive" :
    pct >= 0.9 ? "bg-orange-500" :
    pct >= 0.7 ? "bg-yellow-500" :
    "bg-green-500";

  return (
    <div className="rounded-lg border p-3">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-muted-foreground">Budget Used</span>
        <span className="font-medium">
          ${String(budget.current_spend_usd)} / ${String(budget.monthly_limit_usd)}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${Math.min(pct * 100, 100)}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-muted-foreground mt-1">
        <span>{budget.status === "exceeded" ? "Exceeded!" : `${(pct * 100).toFixed(0)}% used`}</span>
        <span>{budget.days_remaining}d remaining</span>
      </div>
    </div>
  );
}

function OptimizationActionCard({ action }: { action: OptimizationAction }) {
  return (
    <div className="rounded-lg border p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className={`inline-block rounded px-1.5 py-0.5 text-xs font-medium ${priorityColors[action.priority] || priorityColors.low}`}>
              {action.priority}
            </span>
            <span className="text-xs text-muted-foreground capitalize">{action.task_type}</span>
          </div>
          <div className="mt-1 flex items-center gap-2 text-sm">
            <span className="font-mono text-xs opacity-70">{action.current_model}</span>
            <span className="text-muted-foreground">→</span>
            <span className="rounded bg-green-50 px-1.5 py-0.5 text-xs font-medium text-green-700">
              {action.recommended_model}
            </span>
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">
            {action.request_count} requests · Save {fmt(action.savings_usd)}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <div className="text-sm font-medium text-green-600">-{fmt(action.savings_usd)}</div>
          <div className="text-xs text-muted-foreground">({action.savings_pct.toFixed(0)}%)</div>
        </div>
      </div>
    </div>
  );
}
