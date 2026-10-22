"""Direct Market API.

Farmers prove ownership with a private PIN, never with their phone number alone. When the
server has phone verification switched on (OTP_PROVIDER), a fresh one-time-code token is
also required, so nobody can post or manage listings with somebody else's number.
Wrong PINs are counted per phone number and the number is locked for an hour after
PIN_FAILURES_PER_HOUR mistakes. Every write endpoint is rate limited per client address.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..models import BuyerInterest, Listing
from ..schemas import (
    InterestCreate, InterestOut, ListingCreate, ListingPublic, MyListing, OwnerCredentials,
)
from ..security import hash_owner_pin, pin_problem, verify_owner_pin
from ..services import otp, rate_limit
from ..services.query_utils import LIKE_ESCAPE, like_contains
from ..timeutil import now_utc

router = APIRouter(prefix="/api/listings", tags=["listings"])

WRONG_CREDENTIALS = "Phone number or farmer PIN is incorrect, or this listing predates PIN protection."
LOCKED = "Too many wrong PIN attempts for this mobile number. Please wait an hour and try again."
NEEDS_VERIFICATION = "Verify this mobile number with the one-time code first."
HOUR = 3600


def _get_or_404(db: Session, listing_id: int) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Listing not found")
    return listing


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _expires_at(listing: Listing) -> datetime:
    return _aware(listing.created_at) + timedelta(days=config.LISTING_EXPIRY_DAYS)


def _is_open(listing: Listing) -> bool:
    return listing.status == "available" and _expires_at(listing) > now_utc()


def _public_name(name: str) -> str:
    """Show buyers 'Ramesh K.' rather than the full name."""
    parts = (name or "").split()
    if len(parts) <= 1:
        return name
    return f"{parts[0]} {parts[-1][0].upper()}."


def _interest_counts(db: Session, ids: list[int]) -> dict[int, int]:
    if not ids:
        return {}
    rows = (
        db.query(BuyerInterest.listing_id, func.count(BuyerInterest.id))
        .filter(BuyerInterest.listing_id.in_(ids))
        .group_by(BuyerInterest.listing_id)
        .all()
    )
    return {listing_id: count for listing_id, count in rows}


def _status(listing: Listing) -> str:
    if listing.status == "available" and not _is_open(listing):
        return "expired"
    return listing.status


def _public(listing: Listing, count: int = 0) -> ListingPublic:
    out = ListingPublic.model_validate(listing)
    out.farmer_name = _public_name(listing.farmer_name)
    out.status = _status(listing)
    out.expires_at = _expires_at(listing)
    out.interest_count = count
    return out


def _require_phone_verification(phone: str, token: Optional[str]) -> None:
    if otp.otp_required() and not otp.token_valid(phone, token):
        raise HTTPException(status_code=401, detail=NEEDS_VERIFICATION)


def _guard_pin_attempts(request: Request, phone: str) -> None:
    rate_limit.limit_client(request, "pin_check_ip", 30, 10 * 60)
    if rate_limit.retry_after("pin_fail_phone", phone, config.PIN_FAILURES_PER_HOUR, HOUR):
        raise HTTPException(status_code=429, detail=LOCKED, headers={"Retry-After": str(HOUR)})


def _pin_failed(phone: str) -> None:
    rate_limit.record("pin_fail_phone", phone)


def _owned_by_credentials(request: Request, db: Session, phone: str, pin: str, token: Optional[str]) -> list[Listing]:
    """Return only PIN-matched listings. Legacy rows without hashes are never exposed here."""
    _require_phone_verification(phone, token)
    _guard_pin_attempts(request, phone)
    candidates = db.query(Listing).filter(Listing.phone == phone).order_by(
        Listing.created_at.desc(), Listing.id.desc()
    ).all()
    protected = [row for row in candidates if row.owner_pin_hash]
    # The create endpoint enforces one PIN per phone. Verify only one salted hash to avoid
    # multiplying the intentionally expensive PBKDF2 check by the number of listings.
    if not protected or not verify_owner_pin(pin, protected[0].owner_pin_hash):
        _pin_failed(phone)
        # Same response for unknown phone, wrong PIN, and legacy rows.
        raise HTTPException(status_code=403, detail=WRONG_CREDENTIALS)
    return protected


@router.post("", response_model=ListingPublic, status_code=201)
def create_listing(data: ListingCreate, request: Request, db: Session = Depends(get_db)):
    rate_limit.limit_client(request, "listing_create", 10, HOUR)
    _require_phone_verification(data.phone, data.phone_token)
    weak = pin_problem(data.owner_pin, data.phone)
    if weak:
        raise HTTPException(status_code=422, detail=weak)
    existing_hash = db.query(Listing.owner_pin_hash).filter(
        Listing.phone == data.phone, Listing.owner_pin_hash.is_not(None)
    ).first()
    if existing_hash:
        # Creating a listing on a known number is also a PIN check, so it shares the lockout.
        _guard_pin_attempts(request, data.phone)
        if not verify_owner_pin(data.owner_pin, existing_hash[0]):
            _pin_failed(data.phone)
            raise HTTPException(status_code=403, detail="This mobile number already has listings. Use the same farmer PIN.")

    values = data.model_dump(exclude={"owner_pin", "phone_token"})
    listing = Listing(**values, owner_pin_hash=hash_owner_pin(data.owner_pin), created_at=now_utc())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _public(listing)


@router.get("", response_model=list[ListingPublic])
def browse_listings(
    crop: Optional[str] = None,
    district: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Open listings, newest first. Expired listings and farmer phone/PIN details are never shown."""
    cutoff = now_utc() - timedelta(days=config.LISTING_EXPIRY_DAYS)
    q = db.query(Listing).filter(Listing.status == "available", Listing.created_at > cutoff)
    if crop and crop.strip():
        q = q.filter(Listing.crop.ilike(like_contains(crop.strip()), escape=LIKE_ESCAPE))
    if district and district.strip():
        q = q.filter(Listing.district.ilike(like_contains(district.strip()), escape=LIKE_ESCAPE))
    if state and state.strip():
        q = q.filter(Listing.state.ilike(like_contains(state.strip()), escape=LIKE_ESCAPE))
    listings = q.order_by(Listing.created_at.desc(), Listing.id.desc()).limit(limit).all()
    counts = _interest_counts(db, [l.id for l in listings])
    return [_public(l, counts.get(l.id, 0)) for l in listings]


# POST keeps the PIN out of URLs, browser history, and standard access logs.
@router.post("/mine", response_model=list[MyListing])
def my_listings(data: OwnerCredentials, request: Request, db: Session = Depends(get_db)):
    """Return only listings for which the caller supplies the correct PIN."""
    listings = _owned_by_credentials(request, db, data.phone, data.owner_pin, data.phone_token)
    ids = [l.id for l in listings]
    interests = (
        db.query(BuyerInterest).filter(BuyerInterest.listing_id.in_(ids))
        .order_by(BuyerInterest.created_at.desc(), BuyerInterest.id.desc()).all()
        if ids else []
    )
    by_listing: dict[int, list[InterestOut]] = {}
    for interest in interests:
        by_listing.setdefault(interest.listing_id, []).append(InterestOut.model_validate(interest))
    result = []
    for listing in listings:
        item = MyListing.model_validate(listing)
        item.status = _status(listing)
        item.expires_at = _expires_at(listing)
        item.interests = by_listing.get(listing.id, [])
        item.interest_count = len(item.interests)
        result.append(item)
    return result


@router.get("/{listing_id}", response_model=ListingPublic)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = _get_or_404(db, listing_id)
    return _public(listing, _interest_counts(db, [listing.id]).get(listing.id, 0))


@router.post("/{listing_id}/interest", response_model=InterestOut, status_code=201)
def send_interest(listing_id: int, data: InterestCreate, request: Request, db: Session = Depends(get_db)):
    rate_limit.limit_client(request, "interest", 20, HOUR)
    listing = _get_or_404(db, listing_id)
    if listing.status != "available":
        detail = "This listing is already sold" if listing.status == "sold" else "This listing is no longer available"
        raise HTTPException(status_code=409, detail=detail)
    if not _is_open(listing):
        raise HTTPException(status_code=409, detail="This listing has expired")
    already = db.query(BuyerInterest.id).filter(
        BuyerInterest.listing_id == listing_id, BuyerInterest.phone == data.phone
    ).first()
    if already:
        raise HTTPException(status_code=409, detail="You have already sent your number for this listing")
    interest = BuyerInterest(listing_id=listing_id, **data.model_dump(), created_at=now_utc())
    db.add(interest)
    db.commit()
    db.refresh(interest)
    return interest


def _owner_action(listing_id: int, data: OwnerCredentials, request: Request, db: Session) -> Listing:
    listing = _get_or_404(db, listing_id)
    _require_phone_verification(data.phone, data.phone_token)
    _guard_pin_attempts(request, data.phone)
    if listing.phone != data.phone or not verify_owner_pin(data.owner_pin, listing.owner_pin_hash):
        _pin_failed(data.phone)
        raise HTTPException(status_code=403, detail="Phone number or farmer PIN is incorrect.")
    return listing


@router.patch("/{listing_id}/sold", response_model=ListingPublic)
def mark_sold(listing_id: int, data: OwnerCredentials, request: Request, db: Session = Depends(get_db)):
    listing = _owner_action(listing_id, data, request, db)
    listing.status = "sold"
    db.commit()
    db.refresh(listing)
    return _public(listing, _interest_counts(db, [listing.id]).get(listing.id, 0))


@router.post("/{listing_id}/withdraw", response_model=ListingPublic)
def withdraw_listing(listing_id: int, data: OwnerCredentials, request: Request, db: Session = Depends(get_db)):
    """The farmer removes a listing from the market (for example, a mistake or no longer for sale)."""
    listing = _owner_action(listing_id, data, request, db)
    listing.status = "withdrawn"
    db.commit()
    db.refresh(listing)
    return _public(listing, _interest_counts(db, [listing.id]).get(listing.id, 0))
