"""Shapes of data going in and out of the Direct Market API (Pydantic v2).

Owner: Member A
"""
import re
from datetime import datetime
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

PHONE_PATTERN = r"^[6-9]\d{9}$"  # 10-digit Indian mobile number


def normalize_phone(value):
    """Accept '+91 98765-43210', '098765 43210' or '9876543210' and keep the 10 digits."""
    if not isinstance(value, str):
        return value
    digits = re.sub(r"\D", "", value)
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits


# A phone field that cleans the number first, then checks it.
Phone = Annotated[str, BeforeValidator(normalize_phone), Field(pattern=PHONE_PATTERN)]


class _In(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)


class ListingCreate(_In):
    owner_pin: str = Field(min_length=8, max_length=128, repr=False)
    # Needed only when the server has phone verification (OTP) switched on.
    phone_token: Optional[str] = Field(default=None, max_length=200, repr=False)
    farmer_name: str = Field(min_length=2, max_length=80)
    phone: Phone
    crop: str = Field(min_length=2, max_length=60)
    quantity_kg: float = Field(gt=0, le=1_000_000)
    price_per_kg: float = Field(gt=0, le=100_000)
    village: Optional[str] = Field(default=None, max_length=80)
    district: Optional[str] = Field(default=None, max_length=80)
    state: Optional[str] = Field(default=None, max_length=80)


class ListingPublic(BaseModel):
    """What any buyer can see. The farmer's phone number is NOT shown here."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    farmer_name: str
    crop: str
    quantity_kg: float
    price_per_kg: float
    village: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    status: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    interest_count: int = 0


class InterestCreate(_In):
    buyer_name: str = Field(min_length=2, max_length=80)
    phone: Phone
    offered_price_per_kg: Optional[float] = Field(default=None, gt=0, le=100_000)
    message: Optional[str] = Field(default=None, max_length=300)


class InterestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    buyer_name: str
    phone: str
    offered_price_per_kg: Optional[float] = None
    message: Optional[str] = None
    created_at: datetime


class MyListing(ListingPublic):
    """What the farmer sees about their own listing: buyers and their numbers."""
    phone: str
    interests: list[InterestOut] = []


class OwnerCredentials(_In):
    """Shared secret plus phone; the phone number alone is not authentication."""
    phone: Phone
    owner_pin: str = Field(min_length=8, max_length=128, repr=False)
    phone_token: Optional[str] = Field(default=None, max_length=200, repr=False)


class OtpRequest(_In):
    phone: Phone


class OtpVerify(_In):
    phone: Phone
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")
