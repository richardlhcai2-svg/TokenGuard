"use client";

import { useEffect, useState } from "react";

interface AlertRule {
  id: string;
  organization_id: string;
  rule_type: string;
  config: Record<string, unknown>;
  is_enabled: boolean | null;
  created_at: string;
}

export default function AlertsPage() {
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [showDialog, setShowDialog] = useState(false);
  const [newRuleType, setNewRuleType] = useState("budget_percentage");
  const [newConfig, setNewConfig] = useState<Record<string, string>>({
    threshold_pct: "90",
  });
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetch("/api/v1/alerts/")
      .then((r) => r.json())
      .then((data) => {
        setRules(Array.isArray(data) ? data : []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, []);

  const handleCreate = async () => {
    setCreating(true);
    try {
      const config: Record<string, unknown> = { ...newConfig };
      // Convert numeric fields
      if (config.threshold_pct) config.threshold_pct = parseFloat(config.threshold_pct as string);
      if (config.budget_usd) config.budget_usd = parseFloat(config.budget_usd as string);

      const res = await fetch("/api/v1/alerts/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rule_type: newRuleType, config }),
      });
      if (res.ok) {
        const created = await res.json();
        setRules((prev) => [created, ...prev]);
        setShowDialog(false);
        setNewConfig({ threshold_pct: "90" });
      }
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    await fetch(`/api/v1/alerts/${id}`, { method: "DELETE" });
    setRules((prev) => prev.filter((r) => r.id !== id));
  };

  const handleToggle = async (rule: AlertRule) => {
    const res = await fetch(`/api/v1/alerts/${rule.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_enabled: !rule.is_enabled }),
    });
    if (res.ok) {
      const updated = await res.json();
      setRules((prev) => prev.map((r) => (r.id === rule.id ? updated : r)));
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Alerts</h1>
        <div className="animate-pulse rounded-xl border bg-card p-8 text-sm text-muted-foreground">
          Loading...
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Alert Rules</h1>
        <button
          onClick={() => setShowDialog(true)}
          className="inline-flex items-center rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          New Rule
        </button>
      </div>

      {/* New Rule Dialog */}
      {showDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <div className="w-full max-w-md rounded-xl border bg-card p-6 shadow-xl">
            <h2 className="mb-4 text-lg font-semibold">Create Alert Rule</h2>
            <div className="space-y-3">
              <div>
                <label className="text-sm text-muted-foreground">Rule Type</label>
                <select
                  value={newRuleType}
                  onChange={(e) => setNewRuleType(e.target.value)}
                  className="mt-1 w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                >
                  <option value="budget_percentage">Budget Percentage</option>
                  <option value="budget_absolute">Budget Absolute ($)</option>
                  <option value="budget_growth">Growth Spike</option>
                  <option value="context_window">Context Window Warning</option>
                </select>
              </div>
              <div>
                <label className="text-sm text-muted-foreground">Threshold (%)</label>
                <input
                  type="number"
                  value={newConfig.threshold_pct || ""}
                  onChange={(e) => setNewConfig({ ...newConfig, threshold_pct: e.target.value })}
                  className="mt-1 w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                  placeholder="90"
                />
              </div>
              {(newRuleType === "budget_absolute" || newRuleType === "budget_percentage") && (
                <div>
                  <label className="text-sm text-muted-foreground">Budget Limit ($)</label>
                  <input
                    type="number"
                    value={newConfig.budget_usd || ""}
                    onChange={(e) => setNewConfig({ ...newConfig, budget_usd: e.target.value })}
                    className="mt-1 w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                    placeholder="1000"
                  />
                </div>
              )}
              <div>
                <label className="text-sm text-muted-foreground">Channels (comma separated)</label>
                <input
                  type="text"
                  value={newConfig.channels || "email"}
                  onChange={(e) => setNewConfig({ ...newConfig, channels: e.target.value })}
                  className="mt-1 w-full rounded-md border bg-background px-3 py-1.5 text-sm"
                  placeholder="email,slack"
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                onClick={() => setShowDialog(false)}
                className="rounded-md px-3 py-1.5 text-sm hover:bg-muted"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating}
                className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
              >
                {creating ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}

      {rules.length === 0 ? (
        <div className="rounded-xl border bg-card p-8 text-center text-sm text-muted-foreground">
          No alert rules configured. Click "New Rule" to create one.
        </div>
      ) : (
        <div className="space-y-2">
          {rules.map((rule) => (
            <div
              key={rule.id}
              className="flex items-center justify-between rounded-xl border bg-card p-4"
            >
              <div>
                <div className="font-medium capitalize">{rule.rule_type.replace(/_/g, " ")}</div>
                <div className="text-xs text-muted-foreground">
                  {rule.is_enabled ? "Enabled" : "Disabled"} · Created {new Date(rule.created_at).toLocaleDateString()}
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleToggle(rule)}
                  className={`rounded-md px-3 py-1 text-xs font-medium ${
                    rule.is_enabled
                      ? "bg-green-100 text-green-700 hover:bg-green-200"
                      : "bg-yellow-100 text-yellow-700 hover:bg-yellow-200"
                  }`}
                >
                  {rule.is_enabled ? "On" : "Off"}
                </button>
                <button
                  onClick={() => handleDelete(rule.id)}
                  className="rounded-md px-3 py-1 text-xs text-destructive hover:bg-destructive/10"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
