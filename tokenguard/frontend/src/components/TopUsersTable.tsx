"use client";

import { useEffect, useState } from "react";

interface UserRow {
  user_id: string;
  user_name: string;
  total_cost_usd: number | string;
  total_requests: number;
}

export function TopUsersTable() {
  const [data, setData] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/v1/dashboard/top-users?limit=10")
      .then((r) => r.json())
      .then((rows: UserRow[]) => {
        setData(rows);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="rounded-xl border bg-card p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-semibold">Top Users</h2>
        <div className="animate-pulse h-32 text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm">
      <h2 className="mb-4 text-lg font-semibold">Top Users by Cost</h2>
      {data.length === 0 ? (
        <div className="text-sm text-muted-foreground">
          No user data yet. Usage data will appear once the proxy starts reporting.
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-3 py-2 text-left font-medium text-muted-foreground">User</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground">Cost</th>
                <th className="px-3 py-2 text-right font-medium text-muted-foreground">Requests</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.user_id} className="border-t">
                  <td className="px-3 py-2">{row.user_name}</td>
                  <td className="px-3 py-2 text-right">
                    ${typeof row.total_cost_usd === "string" ? parseFloat(row.total_cost_usd).toFixed(4) : row.total_cost_usd.toFixed(4)}
                  </td>
                  <td className="px-3 py-2 text-right">{row.total_requests}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
