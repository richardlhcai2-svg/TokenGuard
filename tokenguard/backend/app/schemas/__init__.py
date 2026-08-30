from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Union
import uuid
from datetime import datetime, date
from decimal import Decimal


# ---------- Organization ----------

class OrgBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    plan: str = "free"
    monthly_budget: Optional[Decimal] = None


class OrgCreate(OrgBase):
    pass


class OrgUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    plan: Optional[str] = None
    monthly_budget: Optional[Decimal] = None


class OrgOut(OrgBase):
    id: Union[uuid.UUID, str]
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# ---------- User ----------

class UserBase(BaseModel):
    email: str
    name: str = Field(..., min_length=1, max_length=200)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    github_id: Optional[str] = None
    google_id: Optional[str] = None


class UserOut(UserBase):
    id: Union[uuid.UUID, str]
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class UserLogin(BaseModel):
    email: str
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- OrganizationMember ----------

class MemberCreate(BaseModel):
    user_id: str
    role: str = "member"


class MemberOut(BaseModel):
    id: Union[uuid.UUID, str]
    organization_id: Union[uuid.UUID, str]
    user_id: Union[uuid.UUID, str]
    role: str
    joined_at: datetime
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# ---------- ToolIntegration ----------

class IntegrationCreate(BaseModel):
    user_id: str
    tool_name: str
    api_key_hash: str


class IntegrationOut(BaseModel):
    id: Union[uuid.UUID, str]
    organization_id: Union[uuid.UUID, str]
    user_id: Union[uuid.UUID, str]
    tool_name: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# ---------- UsageRecord ----------

class UsageRecordCreate(BaseModel):
    organization_id: str
    user_id: str
    tool_name: str
    model_name: Optional[str] = None
    provider: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost_usd: Decimal
    session_id: Optional[str] = None
    project_name: Optional[str] = None
    task_type: Optional[str] = None
    context_window_size: Optional[int] = None
    context_usage_pct: Optional[Decimal] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


class UsageRecordIn(UsageRecordCreate):
    """Used by proxy — no `id` field."""
    pass


class UsageRecordOut(UsageRecordCreate):
    id: Union[uuid.UUID, str]
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


class UsageRecordsResponse(BaseModel):
    records: list[UsageRecordOut]
    total: int



# ---------- DailySummary ----------

class DailySummaryOut(BaseModel):
    id: Union[uuid.UUID, str]
    organization_id: Union[uuid.UUID, str]
    user_id: Optional[str] = None
    tool_name: Optional[str] = None
    date: date
    total_cost_usd: Decimal
    total_input_tokens: int
    total_output_tokens: int
    total_requests: int
    avg_context_usage: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# ---------- AlertRule ----------

class AlertRuleCreate(BaseModel):
    rule_type: str
    config: dict


class AlertRuleUpdate(BaseModel):
    rule_type: Optional[str] = None
    config: Optional[dict] = None
    is_enabled: Optional[bool] = None


class AlertRuleOut(BaseModel):
    id: Union[uuid.UUID, str]
    organization_id: Union[uuid.UUID, str]
    rule_type: str
    config: dict
    is_enabled: Optional[bool] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# ---------- AlertHistory ----------

class AlertHistoryOut(BaseModel):
    id: Union[uuid.UUID, str]
    organization_id: Union[uuid.UUID, str]
    severity: str
    message: str
    triggered_at: datetime
    resolved: bool
    resolved_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# ---------- ModelPricing ----------

class ModelPricingOut(BaseModel):
    id: Union[uuid.UUID, str]
    model_id: Union[uuid.UUID, str]
    display_name: str
    provider: str
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    cache_read_price_per_million: Optional[Decimal] = None
    cache_creation_price_per_million: Optional[Decimal] = None
    capability_level: int
    is_active: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)


# ---------- Dashboard ----------

class DashboardSummary(BaseModel):
    total_cost_usd: Decimal
    total_requests: int
    total_input_tokens: int
    total_output_tokens: int
    avg_context_usage: Optional[Decimal] = None
    cost_today: Decimal
    cost_yesterday: Decimal
    cost_last_7_days: Decimal
    cost_last_30_days: Decimal


class CostTrendPoint(BaseModel):
    date: str
    cost: Decimal
    tokens: int


class TopModel(BaseModel):
    model_name: str
    total_cost_usd: Decimal
    total_requests: int
    avg_context_usage: Optional[Decimal] = None


class TopUser(BaseModel):
    user_id: str
    user_name: str
    total_cost_usd: Decimal
    total_requests: int


# ---------- Dashboard Overview (enhanced) ----------

class ToolBreakdown(BaseModel):
    tool: str
    cost_usd: Decimal
    pct: float


class MemberRanking(BaseModel):
    user_id: str
    name: str
    avatar_url: Optional[str] = None
    cost_usd: Decimal
    primary_tool: str


class AnomalyEntry(BaseModel):
    user_name: str
    tool: str
    model: str
    cost_usd: Decimal
    occurred_at: datetime
    type: str


class DashboardOverview(BaseModel):
    total_cost_usd: Decimal
    predicted_monthly_usd: Decimal
    mom_change_pct: float
    active_tools_count: int
    daily_trend: list[CostTrendPoint]
    tool_breakdown: list[ToolBreakdown]
    member_ranking: list[MemberRanking]
    recent_anomalies: list[AnomalyEntry]


# ---------- Budget Status ----------

class BudgetStatus(BaseModel):
    monthly_limit_usd: Decimal
    current_spend_usd: Decimal
    usage_pct: float
    predicted_end_usd: Decimal
    days_remaining: int
    status: str  # normal|warning|critical|exceeded


# ---------- ROI Report ----------

class ROIReport(BaseModel):
    month: str
    ai_cost_usd: Decimal
    pr_count: int
    avg_pr_time_hours: float
    baseline_pr_time_hours: float
    time_saved_hours: Decimal
    time_value_usd: Decimal
    roi_multiple: float
    cost_breakdown: dict
    optimization_suggestions: list[dict]


# ---------- Recommendation ----------

class RecommendationRequest(BaseModel):
    prompt: str
    current_model: str
    context: Optional[dict] = None


class RecommendationResponse(BaseModel):
    recommended_model: str
    current_model: str
    task_type: str
    estimated_saving_pct: float
    confidence: float
    reason: str
    current_cost_estimate: Decimal
    recommended_cost_estimate: Decimal


# ---------- Cost Optimization ----------

class OptimizationAction(BaseModel):
    current_model: str
    recommended_model: str
    task_type: str
    provider: Optional[str] = None
    actual_cost_usd: Decimal
    potential_cost_usd: Decimal
    savings_usd: Decimal
    savings_pct: float
    request_count: int
    action: str = "downgrade"  # downgrade | switch_provider | optimize
    priority: str = "medium"  # high | medium | low


class OptimizationReport(BaseModel):
    total_actual_cost_usd: Decimal
    total_potential_cost_usd: Decimal
    total_savings_usd: Decimal
    savings_pct: float
    action_count: int
    actions: list[OptimizationAction]


# ---------- Savings Estimate ----------

class PerModelSavings(BaseModel):
    model_name: str
    provider: Optional[str] = None
    actual_cost_usd: Decimal
    alternative_cost_usd: Decimal
    savings_usd: Decimal
    savings_pct: float
    request_count: int
    recommended_model: str


class SavingsEstimate(BaseModel):
    total_actual_cost_usd: Decimal
    total_alternative_cost_usd: Decimal
    total_savings_usd: Decimal
    savings_pct: float
    per_model: list[PerModelSavings]


# ---------- SubscriptionPlan ----------

class SubscriptionPlanOut(BaseModel):
    id: Union[uuid.UUID, str]
    name: str
    monthly_budget_usd: Optional[Decimal] = None
    max_members: int
    retention_days: int
    include_alerts: bool
    include_predictions: bool
    include_team_features: bool
    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
