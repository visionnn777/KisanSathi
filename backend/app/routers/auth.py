"""Optional phone verification (one-time code). See app/services/otp.py."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import config
from ..database import get_db
from ..schemas import OtpRequest, OtpVerify
from ..services import otp, rate_limit

router = APIRouter(prefix="/api/auth", tags=["phone verification"])


@router.get("/config")
def auth_config():
    return {"otp_required": otp.otp_required(), "provider": config.OTP_PROVIDER,
            "demo_mode": config.OTP_PROVIDER == "console"}


@router.post("/otp/request")
def request_code(data: OtpRequest, request: Request, db: Session = Depends(get_db)):
    if not otp.otp_required():
        raise HTTPException(status_code=409, detail="Phone verification is not enabled on this server.")
    rate_limit.limit_client(request, "otp_ip", 10, 3600)
    rate_limit.check("otp_phone", data.phone, 3, 15 * 60)
    return otp.send_code(db, data.phone)


@router.post("/otp/verify")
def verify_code(data: OtpVerify, request: Request, db: Session = Depends(get_db)):
    if not otp.otp_required():
        raise HTTPException(status_code=409, detail="Phone verification is not enabled on this server.")
    rate_limit.limit_client(request, "otp_verify_ip", 20, 3600)
    token = otp.verify_code(db, data.phone, data.code)
    if token is None:
        raise HTTPException(status_code=403, detail="The code is wrong or has expired. Request a new code.")
    return {"phone_token": token, "expires_in": otp.TOKEN_TTL_SECONDS}
