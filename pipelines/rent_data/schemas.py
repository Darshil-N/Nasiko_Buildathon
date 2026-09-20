"""Schemas for the optional rent and price CSV data (step 2.1.3)."""

from typing import Literal

from pydantic import BaseModel, Field


class RawListing(BaseModel):
    """A row from the user-provided listings CSV."""

    type: Literal["rent", "sale"]
    property_type: Literal["commercial", "residential"]
    price_inr: float = Field(..., gt=0)
    period: Literal["monthly", "yearly", "total"] = "monthly"
    area_sqft: float = Field(..., ge=50, le=20000)
    locality: str
    lat: float | None = None
    lon: float | None = None
    source_note: str | None = None
