"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import date

# HVAC-focused schemas

class CampaignMetric(BaseModel):
    """
    HVAC AI campaign performance metrics
    Collection name: "campaignmetric"
    """
    channel: Literal["inbound", "outbound"] = Field(..., description="Channel type")
    date: date = Field(..., description="Metric date (UTC)")

    # Core funnel metrics
    leads_generated: int = Field(0, ge=0)
    calls_handled: int = Field(0, ge=0)
    conversations: int = Field(0, ge=0)
    booked_jobs: int = Field(0, ge=0)
    completed_jobs: int = Field(0, ge=0)

    # Performance
    response_time_sec: float = Field(0, ge=0, description="Average first-response time in seconds")
    conversion_rate: float = Field(0, ge=0, le=1, description="Lead → booked conversion rate (0-1)")
    appt_set_rate: float = Field(0, ge=0, le=1, description="Conversations → appointments set (0-1)")
    no_show_rate: float = Field(0, ge=0, le=1)

    # Financials
    aov: float = Field(0, ge=0, description="Average order value")
    revenue: float = Field(0, ge=0)
    cost: float = Field(0, ge=0)
    roi: float = Field(0, description="Return on investment multiplier, e.g. 3.2 = 320%")

    # Quality
    csat: float = Field(0, ge=0, le=5, description="Customer satisfaction (1-5)")

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")
