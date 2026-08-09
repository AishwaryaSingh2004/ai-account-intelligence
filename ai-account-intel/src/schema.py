from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


class Company(BaseModel):
    name: str
    domain: Optional[str] = None
    industry: str
    employee_count: Optional[int] = None
    headquarters: str
    founded_year: Optional[int] = None
    description: str


class TechStack(BaseModel):
    crm: Optional[str] = None
    marketing_automation: Optional[str] = None
    website_platform: Optional[str] = None
    analytics: Optional[str] = None


class Leader(BaseModel):
    name: str
    title: str


class Persona(BaseModel):
    likely_role: str
    confidence: float = Field(ge=0.0, le=1.0)


class Stage(str, Enum):
    AWARENESS = "Awareness"
    EVALUATION = "Evaluation"
    DECISION = "Decision"


class Intent(BaseModel):
    score: float = Field(ge=0.0, le=10.0)
    stage: Stage


class RecommendedAction(BaseModel):
    summary: str
    next_steps: List[str]


class RiskLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class Risk(BaseModel):
    level: RiskLevel
    explanation: str


class RiskAnalysis(BaseModel):
    employee_turnover: Risk
    funding_slowdown: Risk
    negative_news: Risk
    declining_hiring: Risk
    low_buying_intent: Risk


class NewsItem(BaseModel):
    headline: str
    summary: str
    date: Optional[str] = None


class Source(BaseModel):
    title: str
    url: str


class AccountIntel(BaseModel):
    company: Company
    tech_stack: TechStack
    business_signals: List[str]
    leadership: List[Leader]
    persona: Persona
    intent: Intent
    ai_summary: str
    recommended_action: RecommendedAction
    risks: RiskAnalysis
    recent_news: List[NewsItem] = []
    sources: List[Source] = []
    confidence_notes: str


class VisitorSignal(BaseModel):
    visitor_id: Optional[str] = None
    ip: Optional[str] = None
    pages_visited: List[str] = []
    time_on_site_seconds: Optional[float] = None
    visits_this_week: Optional[int] = None
    referral_source: Optional[str] = None
    device: Optional[str] = None
    location: Optional[str] = None


class CompanyInput(BaseModel):
    company_name: str
    partial_domain: Optional[str] = None