"use client";

import { useEffect, useState } from "react";
import type { TopModel } from "@/lib/api";

interface ModelRow {
  model: string;
  cost_usd: number | string;
  requests: number;
  pct: number;
  avgContext?: number | string | null;
}

export function TopModelsTable() {
  const [data, setData] = useState<ModelRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/dashboard/top-models?limit=10")
      .then((r) => r.json())
      .then((rows: TopModel[]) => {
        const total = rows.reduce((s, r) => s + Number(r.total_cost_usd), 0);
        const mapped: ModelRow[] = rows.map((r) => ({
          model: r.model_name,
          cost_usd: r.total_cost_usd,
          requests: r.total_requests,
          pct: total > 0 ? Number(r.total_cost_usd) / total : 0,
          avgContext: r.avg_context_usage,
        }));
        setData(mapped);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Top Models</h2>
        <div className="h-40 animate-pulse text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Top Models by Cost</h2>
      {data.length === 0 ? (
        <div className="text-sm text-muted-foreground">
          No model data yet. Models will appear once the proxy starts reporting usage.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Model</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground">Cost</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground">Requests</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground">Share</th>
                {data[0].avgContext != null && (
                  <th className="px-3 py-2 text-right font-medium text-muted-foreground">Avg Context</th>
                )}
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.model} className="border-t">
                  <td className="px-3 py-2 font-mono text-xs">{row.model}</td>
                  <td className="px-3 py-2 text-right">
                    ${typeof row.cost_usd === "string" ? parseFloat(row.cost_usd).toFixed(4) : row.cost_usd.toFixed(4)}
                  </td>
                  <td className="px-3 py-2 text-right">{row.requests}</td>
                  <td className="px-3 py-2 text-right">{(row.pct * 100).toFixed(1)}%</td>
                  {row.avgContext != null && (
                    <td className="px-3 py-2 text-right">
                      {(typeof row.avgContext === "string" ? parseFloat(row.avgContext) : row.avgContext) * 100}%
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
