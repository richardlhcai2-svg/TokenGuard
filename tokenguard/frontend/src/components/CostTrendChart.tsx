"use client";

import { useEffect, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface TrendPoint {
  date: string;
  cost: number | string;
  tokens: number;
}

export function CostTrendChart() {
  const [data, setData] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/dashboard/trends?days=30")
      .then((r) => r.json())
      .then((rows: TrendPoint[]) => {
        setData(rows);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Cost Trend</h2>
      {loading ? (
        <div className="h-52 animate-pulse text-sm text-muted-foreground">Loading...</div>
      ) : data.length === 0 ? (
        <div className="h-52 flex items-center justify-center text-sm text-muted-foreground">
          No data yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
            <XAxis
              dataKey="date"
              tickFormatter={(v: string) => v.slice(5)}
              fontSize={12}
              className="text-muted-foreground"
            />
            <YAxis
              tickFormatter={(v: number | string) => `$${typeof v === "string" ? parseFloat(v) : v}`}
              fontSize={12}
              className="text-muted-foreground"
            />
            <Tooltip
              formatter={(value: number | string, name: string) => {
                const n = typeof value === "string" ? parseFloat(value) : value;
                if (name === "cost") return [`$${n.toFixed(2)}`, "Cost"];
                return [n, "Tokens"];
              }}
              labelFormatter={(label) => `Date: ${label}`}
            />
            <Area
              type="monotone"
              dataKey="cost"
              stroke="hsl(var(--primary))"
              fill="hsl(var(--primary))"
              fillOpacity={0.15}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
