"use client";

import { useEffect, useState } from "react";

interface OrgInfo {
  id: string;
  name: string;
  slug: string;
  plan: string;
  monthly_budget: string | null;
  is_active: boolean;
  created_at: string;
}

export default function SettingsPage() {
  const [org, setOrg] = useState<OrgInfo | null>(null);
  const [budgetInput, setBudgetInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"org" | "profile" | "notifications">("org");

  useEffect(() => {
    fetch("/api/v1/orgs/me")
      .then((r) => r.json())
      .then(setOrg)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (org?.monthly_budget) setBudgetInput(String(org.monthly_budget));
  }, [org]);

  const handleSaveBudget = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/v1/orgs/me", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monthly_budget: budgetInput ? parseFloat(budgetInput) : null }),
      });
      if (res.ok) setOrg(await res.json());
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <div className="animate-pulse rounded-xl border bg-card p-8 text-sm text-muted-foreground">Loading...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>

      <div className="flex gap-2 border-b">
        {(["org", "profile", "notifications"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`border-b-2 px-4 py-2 text-sm font-medium -mb-px ${
              tab === t
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === "org" && org && (
        <div className="space-y-4 rounded-xl border bg-card p-6">
          <h2 className="text-lg font-semibold">Organization</h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-muted-foreground">Name</label>
              <div className="font-medium">{org.name}</div>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Plan</label>
              <div className="font-medium capitalize">{org.plan || "free"}</div>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Monthly Budget ($)</label>
              <div className="flex gap-2">
                <input
                  type="number"
                  value={budgetInput}
                  onChange={(e) => setBudgetInput(e.target.value)}
                  className="w-40 rounded-md border bg-background px-3 py-1.5 text-sm"
                  placeholder="No budget"
                />
                <button
                  onClick={handleSaveBudget}
                  disabled={saving}
                  className="rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
                >
                  {saving ? "Saving..." : "Save"}
                </button>
              </div>
            </div>
            <div>
              <label className="text-sm text-muted-foreground">Status</label>
              <div className={`font-medium ${org.is_active ? "text-green-600" : "text-destructive"}`}>
                {org.is_active ? "Active" : "Inactive"}
              </div>
            </div>
          </div>
        </div>
      )}

      {tab === "profile" && (
        <div className="rounded-xl border bg-card p-6 text-sm text-muted-foreground">
          Profile settings coming soon. This is where users will manage their name, password, and avatar.
        </div>
      )}

      {tab === "notifications" && (
        <div className="space-y-4 rounded-xl border bg-card p-6">
          <h2 className="text-lg font-semibold">Notification Channels</h2>
          <p className="text-sm text-muted-foreground">
            Configure where alert notifications are sent. Set up email via SendGrid or Slack webhooks in your alert rules.
          </p>
          <div className="space-y-2">
            <div className="flex items-center justify-between rounded-lg border p-3">
              <span className="text-sm">Email (SendGrid)</span>
              <span className="text-xs text-muted-foreground">Configured per alert rule</span>
            </div>
            <div className="flex items-center justify-between rounded-lg border p-3">
              <span className="text-sm">Slack Webhook</span>
              <span className="text-xs text-muted-foreground">Configured per alert rule</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
