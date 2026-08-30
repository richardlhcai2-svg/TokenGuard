"use client";

import { useEffect, useState } from "react";

interface SummaryData {
  total_cost_usd: number | string;
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  avg_context_usage: number | string | null;
  cost_today: number | string;
  cost_yesterday: number | string;
  cost_last_7_days: number | string;
  cost_last_30_days: number | string;
}

const StatCard = ({
  title,
  value,
  sub,
  trend,
}: {
  title: string;
  value: string;
  sub?: string;
  trend?: "up" | "down" | "neutral";
}) => (
  <div className="rounded-xl border bg-card p-5 shadow-sm">
    <dt className="text-sm text-muted-foreground">{title}</dt>
    <dd className="mt-1 flex items-baseline gap-2">
      <dd className="text-2xl font-bold">{value}</dd>
      {trend === "up" && <span className="text-xs text-destructive">↑</span>}
      {trend === "down" && <span className="text-xs text-green-600">↓</span>}
    </dd>
    {sub && <dd className="mt-0.5 text-xs text-muted-foreground">{sub}</dd>}
  </div>
);

function fmt(n: number | string): string {
  return `$${typeof n === "string" ? parseFloat(n).toFixed(2) : n.toFixed(2)}`;
}

export function DashboardSummaryCard() {
  const [data, setData] = useState<SummaryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/dashboard/summary")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setLoading(false))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="animate-pulse rounded-xl border bg-card p-5">
            <div className="h-4 w-20 rounded bg-muted" />
            <div className="mt-2 h-7 w-24 rounded bg-muted" />
          </div>
        ))}
      </div>
    );
  }
  if (!data) return null;

  const cy = Number(data.cost_yesterday);
  const ct = Number(data.cost_today);
  const momPct = cy > 0 ? ((ct - cy) / cy) * 100 : 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      <StatCard
        title="Total Cost (30d)"
        value={fmt(data.cost_last_30_days)}
        sub={`This month: ${fmt(data.total_cost_usd)}`}
        trend={momPct > 0 ? "up" : "down"}
      />
      <StatCard
        title="Today"
        value={fmt(data.cost_today)}
        sub={cy > 0 ? `${momPct >= 0 ? "+" : ""}${momPct.toFixed(1)}% vs yesterday` : "No data"}
        trend={momPct > 0 ? "up" : momPct < 0 ? "down" : "neutral"}
      />
      <StatCard
        title="Requests"
        value={data.total_requests.toLocaleString()}
        sub={`${Number(data.total_input_tokens).toLocaleString()} in / ${Number(data.total_output_tokens).toLocaleString()} out`}
        trend="neutral"
      />
      <StatCard
        title="Avg Context Usage"
        value={
          data.avg_context_usage != null
            ? `${(typeof data.avg_context_usage === "string" ? parseFloat(data.avg_context_usage) : data.avg_context_usage) * 100}%`
            : "—"
        }
        sub={
          data.avg_context_usage != null &&
          Number(data.avg_context_usage) >= 0.9
            ? "Warning: near limit"
            : "Healthy"
        }
        trend={data.avg_context_usage != null && Number(data.avg_context_usage) >= 0.9 ? "up" : "down"}
      />
    </div>
  );
}
