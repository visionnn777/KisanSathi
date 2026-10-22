"""All settings in one place. Values come from backend/.env (see .env.example).

Owner: Member A
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent  # .../kisansaathi/backend
REPO_DIR = BACKEND_DIR.parent                          # .../kisansaathi

# Read backend/.env no matter which folder the command is run from.
# Values already set in the environment (for example by tests) win.
load_dotenv(BACKEND_DIR / ".env")

# Text you will see in .env.example. If a value still equals this, it was never filled in.
PLACEHOLDER_API_KEY = "YOUR_DATA_GOV_IN_API_KEY"

DEFAULT_SQLITE_PATH = REPO_DIR / "data" / "kisansaathi.db"
DATABASE_URL = os.getenv("DATABASE_URL", "").strip() or f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
DATA_GOV_API_KEY = os.getenv("DATA_GOV_API_KEY", "").strip()
# Keyless community provider used for hackathon demonstrations across five states.
MANDI_API_BASE_URL = os.getenv("MANDI_API_BASE_URL", "https://mandi-api.onrender.com/v1").strip().rstrip("/")

MODEL_ID = os.getenv("MODEL_ID", "wambugu71/crop_leaf_diseases_vit").strip()
# Pin the label mapping and weights together; upstream `main` has changed its labels before.
MODEL_REVISION = os.getenv("MODEL_REVISION", "2b77473a26a2974a9bfb7f0c7880ed84f9b302df").strip()
# Each model gets its own folder, e.g. ml/model/wambugu71__crop_leaf_diseases_vit
MODEL_DIR = Path(os.getenv("MODEL_DIR", str(REPO_DIR / "ml" / "model" / MODEL_ID.replace("/", "__"))))
CONFIDENCE_MIN = float(os.getenv("CONFIDENCE_MIN", "0.60"))
MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "10"))
PRELOAD_MODEL = os.getenv("PRELOAD_MODEL", "1").strip() not in ("0", "false", "False", "no")

FRONTEND_DIR = REPO_DIR / "frontend"
DATA_DIR = REPO_DIR / "data"
SNAPSHOT_CSV = DATA_DIR / "mandi_snapshot.csv"
SAMPLE_CSV = DATA_DIR / "sample_mandi_prices.csv"
CORS_ORIGINS = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").split(",") if v.strip()]
CROP_HISTORY_CSV = DATA_DIR / "crop_production.csv"
CROP_HISTORY_URL = os.getenv(
    "CROP_HISTORY_URL",
    "https://raw.githubusercontent.com/k0rn/India_Agri_Data/master/agridata.csv",
).strip()


# The lightweight in-process scheduler is designed for a single backend worker.
# Use a separate cron/job service for multi-worker or horizontally scaled deployments.
def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in ("0", "false", "no", "off", "")

def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


MANDI_AUTO_REFRESH_ENABLED = _env_bool("MANDI_AUTO_REFRESH_ENABLED", True)
MANDI_REFRESH_ON_STARTUP = _env_bool("MANDI_REFRESH_ON_STARTUP", True)
try:
    MANDI_REFRESH_INTERVAL_HOURS = max(1, int(os.getenv("MANDI_REFRESH_INTERVAL_HOURS", "24")))
except ValueError:
    MANDI_REFRESH_INTERVAL_HOURS = 24

# ---------------------------------------------------------------- Safety limits
# In-memory request limits per client address. They protect the PIN check, uploads and
# outside services from bots. Set RATE_LIMIT_ENABLED=0 only for local experiments.
RATE_LIMIT_ENABLED = _env_bool("RATE_LIMIT_ENABLED", True)
# Behind a reverse proxy (Hugging Face, Render, nginx) the real client address is in
# X-Forwarded-For. Only trust that header when the app really runs behind such a proxy.
TRUST_PROXY_HEADERS = _env_bool("TRUST_PROXY_HEADERS", False)
# Wrong farmer PINs allowed per phone number per hour before that number is locked for an hour.
PIN_FAILURES_PER_HOUR = _env_int("PIN_FAILURES_PER_HOUR", 5, minimum=1)
# Listings older than this are hidden from buyers automatically.
LISTING_EXPIRY_DAYS = _env_int("LISTING_EXPIRY_DAYS", 30, minimum=1)
# Stored mandi quotes older than this are removed after each successful refresh (0 = keep all).
PRICE_RETENTION_DAYS = _env_int("PRICE_RETENTION_DAYS", 730, minimum=0)
# A price report older than this many days is labelled "old" in the app.
PRICE_STALE_DAYS = _env_int("PRICE_STALE_DAYS", 3, minimum=1)
# The planner uses a current quote as market context only if it is at most this old.
PLANNER_PRICE_MAX_AGE_DAYS = _env_int("PLANNER_PRICE_MAX_AGE_DAYS", 30, minimum=1)
# Crop-history records older than this many years are flagged as old in the planner.
CROP_DATA_OLD_AFTER_YEARS = _env_int("CROP_DATA_OLD_AFTER_YEARS", 5, minimum=1)

# ---------------------------------------------------------------- Phone verification (OTP)
# off      = farmer PIN only (default; no SMS sent)
# console  = demo mode: the 6-digit code is written to the server log instead of an SMS.
#            Use it to demonstrate the verification flow; never in a public deployment.
# A real SMS gateway can be added in app/services/otp.py (see send_code) with its own key.
OTP_PROVIDER = os.getenv("OTP_PROVIDER", "off").strip().lower() or "off"
OTP_TTL_SECONDS = _env_int("OTP_TTL_SECONDS", 300, minimum=60)
# Secret used to sign short-lived "phone verified" tokens. If it is not set, a random one is
# made at start-up (tokens then stop working after a restart, which is safe).
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
