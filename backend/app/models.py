"""Database tables. Tables are created automatically when the server starts.

Owner: Member A (all three tables live here, so nobody else edits this file)
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint,
)

from .database import Base


def utc_now():
    return datetime.now(timezone.utc)


# Prices: rupees with 2 decimals, returned to Python as float.
Money = Numeric(12, 2, asdecimal=False)


class MandiPrice(Base):
    """One row = one commodity's price in one mandi on one day (Rs per quintal)."""
    __tablename__ = "mandi_prices"

    id = Column(Integer, primary_key=True)
    state = Column(String(80), nullable=False)
    district = Column(String(80), nullable=False, default="")
    market = Column(String(120), nullable=False)
    commodity = Column(String(120), nullable=False)
    variety = Column(String(120), nullable=False, default="")
    grade = Column(String(60), nullable=False, default="")
    arrival_date = Column(Date, nullable=False)
    min_price = Column(Money, nullable=False)
    max_price = Column(Money, nullable=False)
    modal_price = Column(Money, nullable=False)
    source = Column(String(20), nullable=False, default="data.gov.in")  # "data.gov.in" or "sample"

    __table_args__ = (
        UniqueConstraint("state", "district", "market", "commodity", "variety", "grade",
                         "arrival_date", name="uq_mandi_price_day"),
        Index("ix_mandi_state_commodity_date", "state", "commodity", "arrival_date"),
    )


class Listing(Base):
    """Produce a farmer offers for sale."""
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True)
    farmer_name = Column(String(80), nullable=False)
    phone = Column(String(10), nullable=False, index=True)
    crop = Column(String(60), nullable=False, index=True)
    quantity_kg = Column(Money, nullable=False)
    price_per_kg = Column(Money, nullable=False)
    village = Column(String(80))
    district = Column(String(80), index=True)
    state = Column(String(80))
    status = Column(String(20), nullable=False, default="available", index=True)  # available | sold
    # Nullable only for safe migration of old pre-PIN rows; such rows cannot be managed via API.
    owner_pin_hash = Column(String(220), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class BuyerInterest(Base):
    """A buyer saying 'I want to buy this', with their contact number."""
    __tablename__ = "buyer_interests"

    id = Column(Integer, primary_key=True)
    listing_id = Column(Integer, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_name = Column(String(80), nullable=False)
    phone = Column(String(10), nullable=False)
    offered_price_per_kg = Column(Money)
    message = Column(String(300))
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class CropProduction(Base):
    """Historical district-level crop area and output from an openly licensed CSV."""
    __tablename__ = "crop_production_history"

    id = Column(Integer, primary_key=True)
    state = Column(String(100), nullable=False)
    district = Column(String(120), nullable=False)
    crop = Column(String(120), nullable=False)
    year_label = Column(String(20), nullable=False)  # e.g. 1998-99
    year_start = Column(Integer, nullable=False, index=True)
    season = Column(String(60), nullable=False, default="Unknown")
    area_ha = Column(Numeric(16, 3, asdecimal=False), nullable=False)
    production_tonnes = Column(Numeric(18, 3, asdecimal=False), nullable=False)
    # "tonnes" after conversion at import, "nuts" for coconut (no tonne value), or empty for
    # rows imported by older versions (converted when read; re-import to store tonnes).
    production_unit = Column(String(20), nullable=True)
    source = Column(String(160), nullable=False, default="k0rn/India_Agri_Data (CC0-1.0)")

    __table_args__ = (
        UniqueConstraint("state", "district", "crop", "year_label", "season",
                         name="uq_crop_history_observation"),
        Index("ix_crop_history_state_district", "state", "district"),
        Index("ix_crop_history_lookup", "state", "district", "season", "year_start"),
    )


class MandiSyncStatus(Base):
    """Persist the last automatic/manual mandi refresh result for the status UI."""
    __tablename__ = "mandi_sync_status"

    id = Column(Integer, primary_key=True)
    provider = Column(String(40), nullable=False, unique=True, default="mandi-api")
    status = Column(String(20), nullable=False, default="idle")  # idle | success | partial | no_data | error
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    rows_received = Column(Integer, nullable=False, default=0)
    rows_saved = Column(Integer, nullable=False, default=0)
    states_succeeded = Column(Text, nullable=False, default="[]")
    states_failed = Column(Text, nullable=False, default="[]")
    message = Column(Text, nullable=False, default="No refresh has run yet.")


class MandiPriceHistory(Base):
    """State-level historical price observations from the provider history endpoint.

    This is kept separate from individual mandi quotes because the provider history
    endpoint can aggregate across mandis; it must never be displayed as a specific
    market's quoted price.
    """
    __tablename__ = "mandi_price_history"

    id = Column(Integer, primary_key=True)
    state = Column(String(80), nullable=False, index=True)
    commodity = Column(String(120), nullable=False, index=True)
    observation_date = Column(Date, nullable=False, index=True)
    average_modal_price = Column(Money, nullable=False)
    min_modal_price = Column(Money, nullable=True)
    max_modal_price = Column(Money, nullable=True)
    markets_count = Column(Integer, nullable=True)
    source = Column(String(40), nullable=False, default="mandi-api-history")
    fetched_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        UniqueConstraint("state", "commodity", "observation_date", "source",
                         name="uq_mandi_price_history_observation"),
        Index("ix_mandi_history_state_crop_date", "state", "commodity", "observation_date"),
    )


class FarmSeasonRecord(Base):
    """Farmer-entered seasonal outcome for later yield/productivity comparisons.

    This prototype stores no name or phone number. A deployed multi-user service must
    add authenticated ownership and access-control fields before retaining farm data.
    """
    __tablename__ = "farm_season_records"

    id = Column(Integer, primary_key=True)
    farm_ref = Column(String(80), nullable=False, index=True)  # random local-browser reference; not account authentication
    state = Column(String(100), nullable=False, index=True)
    district = Column(String(120), nullable=False, index=True)
    crop = Column(String(120), nullable=False, index=True)
    season = Column(String(60), nullable=False, index=True)
    year_start = Column(Integer, nullable=False, index=True)
    area_ha = Column(Numeric(12, 3, asdecimal=False), nullable=False)
    harvested_tonnes = Column(Numeric(12, 3, asdecimal=False), nullable=True)
    yield_t_per_ha = Column(Numeric(12, 3, asdecimal=False), nullable=True)
    sale_price_rs_per_qtl = Column(Numeric(12, 2, asdecimal=False), nullable=True)
    cultivation_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    seed_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    fertiliser_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    crop_protection_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    labour_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    irrigation_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    machinery_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    harvest_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    transport_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    other_cost_rs_per_ha = Column(Numeric(14, 2, asdecimal=False), nullable=True)
    primary_issue = Column(String(40), nullable=False, default="unknown")
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("ix_farm_season_region_crop", "state", "district", "crop", "season"),
    )


class OtpChallenge(Base):
    """One pending phone-verification code. Only a salted hash of the code is stored."""
    __tablename__ = "otp_challenges"

    id = Column(Integer, primary_key=True)
    phone = Column(String(10), nullable=False, unique=True, index=True)
    salt = Column(String(32), nullable=False)
    code_hash = Column(String(64), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class FarmReference(Base):
    """A private farm-record key issued by the server. Only its SHA-256 hash is stored,
    so a database leak does not reveal the key that unlocks the farmer's records."""
    __tablename__ = "farm_references"

    id = Column(Integer, primary_key=True)
    ref_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)


class SchedulerLease(Base):
    """Makes sure only one server process runs a scheduled job at a time."""
    __tablename__ = "scheduler_leases"

    name = Column(String(60), primary_key=True)
    owner = Column(String(80), nullable=False)
    lease_until = Column(DateTime(timezone=True), nullable=False)
