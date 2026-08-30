"use client";

import { useEffect, useState } from "react";
import { getModelRecommendations, type ModelRecommendation } from "@/lib/api";

function fmt(n: number | string): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  return `$${v.toFixed(4)}`;
}

export function RecommendationsCard() {
  const [data, setData] = useState<ModelRecommendation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getModelRecommendations(30)
      .then(setData)
      .catch(() => setLoading(false))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Model Recommendations</h2>
        <div className="h-40 animate-pulse text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (data.length === 0) return null;

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Model Recommendations</h2>
      <div className="space-y-3">
        {data.map((rec) => (
          <div key={rec.current_model} className="rounded-lg border p-4">
            <div className="flex items-start justify-between gap-4">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs opacity-70">{rec.current_model}</span>
                  <span className="text-muted-foreground">→</span>
                  <span className="rounded bg-green-50 px-1.5 py-0.5 text-xs font-medium text-green-700">
                    {rec.recommended_model}
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-muted-foreground">{rec.reason}</p>
              </div>
              <div className="text-right shrink-0">
                <div className="text-xs text-muted-foreground">{rec.request_count} reqs</div>
                <div className="text-xs font-medium text-green-600">
                  Save ~{rec.saving_pct}%
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
