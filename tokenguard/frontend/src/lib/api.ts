const API_BASE = process.env.NEXT_PUBLIC_API_URL || "/api/v1";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("tg_token") ?? null;
}

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (init?.headers && typeof init.headers === "object") {
    for (const [k, v] of Object.entries(init.headers as Record<string, string>)) {
      headers[k] = v;
    }
  }
  const res = await fetch(`${API_BASE}${url}`, { ...init, headers });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status}: ${res.statusText}${body ? " - " + body : ""}`);
  }
  // Handle 204 No Content
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
}

// ── Auth ──────────────────────────────────────────────────────────────

export interface UserOut {
  id: string;
  email: string;
  name: string;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
}

export interface TokenOut {
  access_token: string;
  token_type: string;
  user: UserOut;
}

export async function login(email: string, password: string): Promise<TokenOut> {
  return fetchJson<TokenOut>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, name: string, password: string): Promise<TokenOut> {
  return fetchJson<TokenOut>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, name, password }),
  });
}

export function setToken(token: string): void {
  localStorage.setItem("tg_token", token);
}

export function clearToken(): void {
  localStorage.removeItem("tg_token");
}

// ── Dashboard (enhanced overview) ─────────────────────────────────────

export interface CostTrendPoint {
  date: string;
  cost: number | string;
  tokens: number;
}

export interface ToolBreakdown {
  tool: string;
  cost_usd: number | string;
  pct: number;
}

export interface MemberRanking {
  user_id: string;
  name: string;
  avatar_url: string | null;
  cost_usd: number | string;
  primary_tool: string;
}

export interface AnomalyEntry {
  user_name: string;
  tool: string;
  model: string;
  cost_usd: number | string;
  occurred_at: string;
  type: string;
}

export interface DashboardOverview {
  total_cost_usd: number | string;
  predicted_monthly_usd: number | string;
  mom_change_pct: number;
  active_tools_count: number;
  daily_trend: CostTrendPoint[];
  tool_breakdown: ToolBreakdown[];
  member_ranking: MemberRanking[];
  recent_anomalies: AnomalyEntry[];
}

export async function getDashboardOverview(days = 30): Promise<DashboardOverview> {
  return fetchJson<DashboardOverview>(`/dashboard/overview?days=${days}`);
}

// ── Legacy endpoints (still work via endpoints.py) ────────────────────

export interface DashboardSummary {
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

export async function getDashboardSummary(): Promise<DashboardSummary> {
  return fetchJson<DashboardSummary>("/dashboard/summary");
}

export async function getCostTrends(days = 30): Promise<CostTrendPoint[]> {
  return fetchJson<CostTrendPoint[]>(`/dashboard/trends?days=${days}`);
}

export interface TopModel {
  model_name: string;
  total_cost_usd: number | string;
  total_requests: number;
  avg_context_usage: number | string | null;
}

export interface TopUser {
  user_id: string;
  user_name: string;
  total_cost_usd: number | string;
  total_requests: number;
}

export async function getTopModels(limit = 10): Promise<TopModel[]> {
  return fetchJson<TopModel[]>(`/dashboard/top-models?limit=${limit}`);
}

export async function getTopUsers(limit = 10): Promise<TopUser[]> {
  return fetchJson<TopUser[]>(`/dashboard/top-users?limit=${limit}`);
}

// ── Savings Estimate ────────────────────────────────────────────────────

export interface PerModelSavings {
  model_name: string;
  provider: string | null;
  actual_cost_usd: number | string;
  alternative_cost_usd: number | string;
  savings_usd: number | string;
  savings_pct: number;
  request_count: number;
  recommended_model: string;
}

export interface SavingsData {
  total_actual_cost_usd: number | string;
  total_alternative_cost_usd: number | string;
  total_savings_usd: number | string;
  savings_pct: number;
  per_model: PerModelSavings[];
}

export async function getSavingsEstimate(days = 30): Promise<SavingsData> {
  return fetchJson<SavingsData>(`/dashboard/savings?days=${days}`);
}

// ── Dashboard Recommendations ───────────────────────────────────────────

export interface ModelRecommendation {
  current_model: string;
  recommended_model: string;
  provider: string | null;
  saving_pct: number;
  reason: string;
  request_count: number;
  total_cost_usd: number | string;
}

export async function getModelRecommendations(days = 30): Promise<ModelRecommendation[]> {
  return fetchJson<ModelRecommendation[]>(`/dashboard/recommendations?days=${days}`);
}

// ── Cost Optimization ───────────────────────────────────────────────────

export interface OptimizationAction {
  current_model: string;
  recommended_model: string;
  task_type: string;
  provider: string | null;
  actual_cost_usd: number | string;
  potential_cost_usd: number | string;
  savings_usd: number | string;
  savings_pct: number;
  request_count: number;
  action: string;
  priority: string;
}

export interface OptimizationReport {
  total_actual_cost_usd: number | string;
  total_potential_cost_usd: number | string;
  total_savings_usd: number | string;
  savings_pct: number;
  action_count: number;
  actions: OptimizationAction[];
}

export async function getOptimizations(days = 30, minSavings = 1): Promise<OptimizationReport> {
  return fetchJson<OptimizationReport>(`/dashboard/optimizations?days=${days}&min_savings=${minSavings}`);
}


// ── Budget ────────────────────────────────────────────────────────────

export interface BudgetStatus {
  monthly_limit_usd: number | string;
  current_spend_usd: number | string;
  usage_pct: number;
  predicted_end_usd: number | string;
  days_remaining: number;
  status: "normal" | "warning" | "critical" | "exceeded";
}

export async function getBudgetStatus(): Promise<BudgetStatus> {
  return fetchJson<BudgetStatus>("/budget/status");
}

// ── Alerts ────────────────────────────────────────────────────────────

export interface AlertRule {
  id: string;
  organization_id: string;
  rule_type: string;
  config: Record<string, unknown>;
  is_enabled: boolean | null;
  created_at: string;
}

export interface AlertHistoryEntry {
  id: string;
  organization_id: string;
  severity: string;
  message: string;
  triggered_at: string;
  resolved: boolean;
  resolved_at: string | null;
}

export async function getAlertRules(): Promise<AlertRule[]> {
  return fetchJson<AlertRule[]>("/alerts/");
}

export async function createAlertRule(rule_type: string, config: Record<string, unknown>): Promise<AlertRule> {
  return fetchJson<AlertRule>("/alerts/", {
    method: "POST",
    body: JSON.stringify({ rule_type, config }),
  });
}

export async function updateAlertRule(ruleId: string, patch: Partial<AlertRule>): Promise<AlertRule> {
  return fetchJson<AlertRule>(`/alerts/${ruleId}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteAlertRule(ruleId: string): Promise<void> {
  await fetchJson<void>(`/alerts/${ruleId}`, { method: "DELETE" });
}

export async function getAlertHistory(limit = 50): Promise<AlertHistoryEntry[]> {
  return fetchJson<AlertHistoryEntry[]>(`/alerts/history?limit=${limit}`);
}

// ── Usage Records ─────────────────────────────────────────────────────

export interface UsageRecord {
  id: string;
  organization_id: string;
  user_id: string;
  tool_name: string;
  model_name: string | null;
  provider: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_creation_tokens: number;
  cache_read_tokens: number;
  cost_usd: number | string;
  session_id: string | null;
  project_name: string | null;
  task_type: string | null;
  context_window_size: number | null;
  context_usage_pct: number | string | null;
  started_at: string;
  ended_at: string | null;
}

export async function getUsageRecords(params?: {
  start_date?: string;
  end_date?: string;
  user_id?: string;
  tool?: string;
  model?: string;
  page?: number;
  per_page?: number;
}): Promise<{ records: UsageRecord[]; total: number }> {
  const qs = new URLSearchParams();
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined) qs.set(k, String(v));
    }
  }
  const query = qs.toString() ? `?${qs}` : "";
  const result = await fetchJson<UsageRecord[]>(`/usage/records${query}`);
  // The endpoint returns [records, total] tuple from Flask-style
  // Actually it returns a list in our implementation, so wrap it
  return { records: result, total: result.length };
}

// ── Org & Members ─────────────────────────────────────────────────────

export interface OrgOut {
  id: string;
  name: string;
  slug: string;
  plan: string;
  monthly_budget: number | string | null;
  is_active: boolean;
  created_at: string;
}

export interface MemberOut {
  id: string;
  organization_id: string;
  user_id: string;
  role: string;
  joined_at: string;
}

export async function getMyOrg(): Promise<OrgOut> {
  return fetchJson<OrgOut>("/orgs/me");
}

export async function updateMyOrg(patch: Partial<OrgOut>): Promise<OrgOut> {
  return fetchJson<OrgOut>("/orgs/me", {
    method: "PUT",
    body: JSON.stringify(patch),
  });
}

export async function getMembers(): Promise<MemberOut[]> {
  return fetchJson<MemberOut[]>("/orgs/members");
}

export async function addMember(userId: string, role = "member"): Promise<MemberOut> {
  return fetchJson<MemberOut>("/orgs/members", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, role }),
  });
}

export async function removeMember(userId: string): Promise<void> {
  await fetchJson<void>(`/orgs/members/${userId}`, { method: "DELETE" });
}

export async function getOrgStats(): Promise<{
  member_count: number;
  total_cost_usd: number;
  plan: string;
  monthly_budget: number | null;
}> {
  return fetchJson<{ member_count: number; total_cost_usd: number; plan: string; monthly_budget: number | null }>("/orgs/stats");
}

// ── Recommendations ───────────────────────────────────────────────────

export interface RecommendationResponse {
  recommended_model: string;
  current_model: string;
  task_type: string;
  estimated_saving_pct: number;
  confidence: number;
  reason: string;
  current_cost_estimate: number | string;
  recommended_cost_estimate: number | string;
}

export async function recommendModel(prompt: string, currentModel?: string): Promise<RecommendationResponse> {
  return fetchJson<RecommendationResponse>("/recommendations/model", {
    method: "POST",
    body: JSON.stringify({ prompt, current_model: currentModel }),
  });
}

// ── ROI Reports ───────────────────────────────────────────────────────

export interface ROIReport {
  month: string;
  ai_cost_usd: number | string;
  pr_count: number;
  avg_pr_time_hours: number;
  baseline_pr_time_hours: number;
  time_saved_hours: number | string;
  time_value_usd: number | string;
  roi_multiple: number;
  cost_breakdown: Record<string, number>;
  optimization_suggestions: Record<string, unknown>[];
}

export async function getROIReport(month?: string): Promise<ROIReport> {
  const qs = month ? `?month=${month}` : "";
  return fetchJson<ROIReport>(`/reports/roi${qs}`);
}

// ── Subscription ──────────────────────────────────────────────────────

export async function getCurrentPlan(): Promise<{
  plan: string;
  is_active: boolean;
  limits: Record<string, number>;
  member_count: number;
  can_add_member: boolean;
  features: Record<string, boolean>;
}> {
  return fetchJson<{ plan: string; is_active: boolean; limits: Record<string, number>; member_count: number; can_add_member: boolean; features: Record<string, boolean> }>("/subscriptions/current");
}

export async function listPlans(): Promise<unknown[]> {
  return fetchJson<unknown[]>("/subscriptions/plans");
}
