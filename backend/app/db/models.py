"""SQLAlchemy models. The SQL in ``migrations/sql/0001_initial_upgrade.sql`` is the source of truth;
``tests/backend/test_schema_sync.py`` fails if these models and that SQL drift apart."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.db.base import Base

_NOW = func.now()


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text, server_default="IN")
    bbox: Mapped[Any | None] = mapped_column(Geometry("POLYGON", srid=4326))
    status: Mapped[str] = mapped_column(Text, server_default="draft")
    last_full_refresh: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Cell(Base):
    __tablename__ = "cells"

    h3_index: Mapped[str] = mapped_column(Text, primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    centroid: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326))
    boundary: Mapped[Any | None] = mapped_column(Geometry("POLYGON", srid=4326))
    locality_name: Mapped[str | None] = mapped_column(Text)
    land_use: Mapped[str | None] = mapped_column(Text)


class CellAttributes(Base):
    __tablename__ = "cell_attributes"

    h3_index: Mapped[str] = mapped_column(
        ForeignKey("cells.h3_index", ondelete="CASCADE"), primary_key=True
    )
    landuse_residential_share: Mapped[Decimal] = mapped_column(Numeric(5, 4), server_default="0")
    landuse_commercial_share: Mapped[Decimal] = mapped_column(Numeric(5, 4), server_default="0")
    landuse_retail_share: Mapped[Decimal] = mapped_column(Numeric(5, 4), server_default="0")
    main_road_dist_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 1))
    main_road_class: Mapped[str | None] = mapped_column(Text)
    population_est: Mapped[Decimal | None] = mapped_column(Numeric)
    source_version: Mapped[str | None] = mapped_column(Text)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int | None] = mapped_column(ForeignKey("cities.id", ondelete="SET NULL"))
    source: Mapped[str] = mapped_column(Text)
    purpose: Mapped[str | None] = mapped_column(Text)
    target: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    raw_path: Mapped[str | None] = mapped_column(Text)
    stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Poi(Base):
    __tablename__ = "pois"
    __table_args__ = (UniqueConstraint("osm_type", "osm_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    osm_type: Mapped[str | None] = mapped_column(Text)
    osm_id: Mapped[int | None] = mapped_column(BigInteger)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"))
    category: Mapped[str] = mapped_column(Text)
    name: Mapped[str | None] = mapped_column(Text)
    brand: Mapped[str | None] = mapped_column(Text)
    tier_guess: Mapped[str] = mapped_column(Text, server_default="unknown")
    location: Mapped[Any] = mapped_column(Geometry("POINT", srid=4326))
    h3_index: Mapped[str | None] = mapped_column(ForeignKey("cells.h3_index", ondelete="SET NULL"))
    tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(Text, server_default="osm")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ingest_job_id: Mapped[int | None] = mapped_column(
        ForeignKey("ingest_jobs.id", ondelete="SET NULL")
    )
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    source: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    listing_type: Mapped[str | None] = mapped_column(Text)
    property_type: Mapped[str | None] = mapped_column(Text)
    price_inr: Mapped[Decimal | None] = mapped_column(Numeric)
    price_period: Mapped[str | None] = mapped_column(Text)
    area_sqft: Mapped[Decimal | None] = mapped_column(Numeric)
    price_per_sqft: Mapped[Decimal | None] = mapped_column(Numeric)
    locality: Mapped[str | None] = mapped_column(Text)
    address_text: Mapped[str | None] = mapped_column(Text)
    location: Mapped[Any | None] = mapped_column(Geometry("POINT", srid=4326))
    geo_precision: Mapped[str | None] = mapped_column(Text)
    h3_index: Mapped[str | None] = mapped_column(
        ForeignKey("cells.h3_index", ondelete="SET NULL"), index=True
    )
    posted_date: Mapped[date | None] = mapped_column(Date)
    source_note: Mapped[str | None] = mapped_column(Text)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class MarketIntel(Base):
    __tablename__ = "market_intel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    category: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, str]] | None] = mapped_column(JSONB)
    locality_mentions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class CellFeaturesRow(Base):
    __tablename__ = "cell_features"

    h3_index: Mapped[str] = mapped_column(
        ForeignKey("cells.h3_index", ondelete="CASCADE"), primary_key=True
    )
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    feature_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB)
    affluence: Mapped[Decimal | None] = mapped_column(Numeric)
    rent_per_sqft_est: Mapped[Decimal | None] = mapped_column(Numeric)
    rent_is_estimated: Mapped[bool | None] = mapped_column(Boolean)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(Text, unique=True)
    email: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="owner")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    category: Mapped[str] = mapped_column(Text)
    tier: Mapped[str] = mapped_column(Text)
    answers: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    constraints: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    config_version: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="queued")
    summary_narrative: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str] = mapped_column(ForeignKey("analyses.id", ondelete="CASCADE"))
    rank: Mapped[int | None] = mapped_column(Integer)
    h3_index: Mapped[str | None] = mapped_column(ForeignKey("cells.h3_index"))
    zone_name: Mapped[str | None] = mapped_column(Text)
    score: Mapped[Decimal | None] = mapped_column(Numeric)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric)
    contributions: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    top_drivers: Mapped[list[str] | None] = mapped_column(JSONB)
    top_risks: Mapped[list[str] | None] = mapped_column(JSONB)
    nearby_listing_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    narrative: Mapped[str | None] = mapped_column(Text)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    analysis_id: Mapped[str | None] = mapped_column(Text)
    agent_name: Mapped[str | None] = mapped_column(String)
    status: Mapped[str | None] = mapped_column(Text)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    tokens_in: Mapped[int | None] = mapped_column(Integer)
    tokens_out: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric, server_default="0")
    trace_id: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=_NOW)


class CategoryConfig(Base):
    __tablename__ = "category_configs"

    category: Mapped[str] = mapped_column(Text, primary_key=True)
    version: Mapped[str] = mapped_column(Text, primary_key=True)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
