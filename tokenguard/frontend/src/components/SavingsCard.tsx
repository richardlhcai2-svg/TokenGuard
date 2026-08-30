"use client";

import { useEffect, useState } from "react";
import { getSavingsEstimate, type PerModelSavings, type SavingsData } from "@/lib/api";

function fmt(n: number | string): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  return `$${v.toFixed(2)}`;
}

function fmtSmall(n: number | string): string {
  const v = typeof n === "string" ? parseFloat(n) : n;
  return `$${v.toFixed(4)}`;
}

export function SavingsCard() {
  const [data, setData] = useState<SavingsData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSavingsEstimate(30)
      .then(setData)
      .catch(() => setLoading(false))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Estimated Savings</h2>
        <div className="h-40 animate-pulse text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }
  if (!data) return null;

  const hasSavings = data.total_actual_cost_usd && parseFloat(String(data.total_actual_cost_usd)) > 0;
  const savingsPct = data.savings_pct;

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Estimated Savings</h2>
      {!hasSavings ? (
        <div className="text-sm text-muted-foreground">
          No usage data yet. Savings estimates will appear once the proxy starts reporting.
        </div>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <dt className="text-sm text-muted-foreground">Actual Spend</dt>
              <dd className="mt-1 text-2xl font-bold">{fmt(data.total_actual_cost_usd)}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">Potential Spend</dt>
              <dd className="mt-1 text-2xl font-bold">{fmt(data.total_alternative_cost_usd)}</dd>
            </div>
            <div>
              <dt className="text-sm text-muted-foreground">You Could Save</dt>
              <dd className={`mt-1 text-2xl font-bold ${savingsPct > 0 ? "text-green-600" : ""}`}>
                {fmt(data.total_savings_usd)} ({savingsPct.toFixed(1)}%)
              </dd>
            </div>
          </div>

          {/* Per-model breakdown */}
          {data.per_model.length > 0 && (
            <div className="mt-4 overflow-hidden rounded-lg border">
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-muted-foreground">Model</th>
                    <th className="px-3 py-2 text-right font-medium text-muted-foreground">Actual</th>
                    <th className="px-3 py-2 text-right font-medium text-muted-foreground">Alternative</th>
                    <th className="px-3 py-2 text-right font-medium text-muted-foreground">Save</th>
                    <th className="px-3 py-2 text-right font-medium text-muted-foreground">Try</th>
                  </tr>
                </thead>
                <tbody>
                  {data.per_model.map((row) => (
                    <ModelSavingsRow key={row.model_name} row={row} />
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function ModelSavingsRow({ row }: { row: PerModelSavings }) {
  return (
    <tr className="border-t">
      <td className="px-3 py-2 font-mono text-xs">
        {row.model_name}
        {row.request_count > 1 && (
          <span className="ml-1 text-muted-foreground">({row.request_count} reqs)</span>
        )}
      </td>
      <td className="px-3 py-2 text-right">{fmtSmall(row.actual_cost_usd)}</td>
      <td className="px-3 py-2 text-right">{fmtSmall(row.alternative_cost_usd)}</td>
      <td className={`px-3 py-2 text-right ${row.savings_pct > 0 ? "text-green-600" : "text-muted-foreground"}`}>
        {row.savings_pct > 0 ? `-${fmt(row.savings_usd)}` : "—"}
      </td>
      <td className="px-3 py-2 text-right">
        <span className="rounded bg-blue-50 px-1.5 py-0.5 text-xs text-blue-700">
          {row.recommended_model}
        </span>
      </td>
    </tr>
  );
}
