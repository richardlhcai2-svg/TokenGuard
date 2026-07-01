from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


# ---------- Organization ----------

class OrgBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100)
    plan: str = Field(default="free")
    monthly_budget: Optional[Decimal] = None


class OrgCreate(OrgBase):
    pass


class OrgUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    slug: Optional[str] = Field(None, min_length=1, max_length=100)
    plan: Optional[str] = None
    monthly_budget: Optional[Decimal] = None


class OrgOut(OrgBase):
    id: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- User ----------

class UserBase(BaseModel):
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=200)


class UserCreate(UserBase):
    github_id: Optional[str] = None
    google_id: Optional[str] = None


class UserOut(UserBase):
    id: str
    avatar_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- OrganizationMember ----------

class MemberOut(BaseModel):
    id: str
    organization_id: str
    user_id: str
    role: str
    joined_at: datetime
    user: UserOut
    model_config = ConfigDict(from_attributes=True)


# ---------- ToolIntegration ----------

class IntegrationOut(BaseModel):
    id: str
    organization_id: str
    user_id: str
    tool_name: str
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


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


class UsageRecordOut(BaseModel):
    id: str
    organization_id: str
    user_id: str
    tool_name: str
    model_name: Optional[str] = None
    provider: Optional[str] = None
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    cost_usd: Decimal
    session_id: Optional[str] = None
    project_name: Optional[str] = None
    task_type: Optional[str] = None
    context_window_size: Optional[int] = None
    context_usage_pct: Optional[Decimal] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


# ---------- DailySummary ----------

class DailySummaryOut(BaseModel):
    id: str
    organization_id: str
    user_id: Optional[str] = None
    tool_name: Optional[str] = None
    date: datetime
    total_cost_usd: Decimal
    total_input_tokens: int
    total_output_tokens: int
    total_requests: int
    avg_context_usage: Optional[Decimal] = None
    model_config = ConfigDict(from_attributes=True)


# ---------- AlertRule ----------

class AlertRuleCreate(BaseModel):
    rule_type: str
    config: dict


class AlertRuleUpdate(BaseModel):
    rule_type: Optional[str] = None
    config: Optional[dict] = None
    is_enabled: Optional[bool] = None


class AlertRuleOut(BaseModel):
    id: str
    organization_id: str
    rule_type: str
    config: dict
    is_enabled: Optional[bool] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ---------- ModelPricing ----------

class ModelPricingOut(BaseModel):
    id: str
    model_id: str
    display_name: str
    provider: str
    input_price_per_million: Decimal
    output_price_per_million: Decimal
    cache_read_price_per_million: Optional[Decimal] = None
    cache_creation_price_per_million: Optional[Decimal] = None
    capability_level: int
    is_active: Optional[bool] = None
    model_config = ConfigDict(from_attributes=True)


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
