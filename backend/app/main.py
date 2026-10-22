"""KisanSaathi API - starts the server, creates tables and serves the website.

Owner: Member A

Run (from the backend folder):
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
Then open http://localhost:8000 (app) or http://localhost:8000/docs (API tester).
"""
import asyncio
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

from . import config
from .database import Base, engine
from .models import FarmSeasonRecord
from .routers import auth, crops, disease, irrigation, listings, planning, prices, weather
from .services import disease_model
from .services.mandi_scheduler import daily_mandi_refresh_loop

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("kisansaathi")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        Base.metadata.create_all(bind=engine)
        # create_all does not modify existing tables. Add this nullable column for upgrades.
        inspector = inspect(engine)
        table_names = set(inspector.get_table_names())
        if "listings" in table_names:
            columns = {column["name"] for column in inspector.get_columns("listings")}
            if "owner_pin_hash" not in columns:
                with engine.begin() as connection:
                    connection.execute(text("ALTER TABLE listings ADD COLUMN owner_pin_hash VARCHAR(220)"))
                log.warning("Added owner PIN column. Legacy listings without a PIN hash cannot be managed via API; reset demo DB/listings if needed.")
        if "crop_production_history" in table_names:
            crop_columns = {column["name"] for column in inspector.get_columns("crop_production_history")}
            if "production_unit" not in crop_columns:
                with engine.begin() as connection:
                    connection.execute(text("ALTER TABLE crop_production_history ADD COLUMN production_unit VARCHAR(20)"))
                log.warning("Added production_unit column. Re-run python -m scripts.setup_crop_data to store converted units.")
        # Additive migration for installations created before the farm cost breakdown
        # was introduced. Existing data remains untouched; all new columns are nullable.
        if "farm_season_records" in table_names:
            existing = {column["name"] for column in inspector.get_columns("farm_season_records")}
            for column_name in (
                "seed_cost_rs_per_ha", "fertiliser_cost_rs_per_ha", "crop_protection_cost_rs_per_ha",
                "labour_cost_rs_per_ha", "irrigation_cost_rs_per_ha", "machinery_cost_rs_per_ha",
                "harvest_cost_rs_per_ha", "transport_cost_rs_per_ha", "other_cost_rs_per_ha",
            ):
                if column_name not in existing:
                    with engine.begin() as connection:
                        connection.execute(text(f"ALTER TABLE farm_season_records ADD COLUMN {column_name} NUMERIC(14,2)"))
                    log.info("Added farm season cost field %s", column_name)
    except OperationalError:
        log.exception("Could not initialize the database. Check DATABASE_URL and database availability.")
        raise
    if config.PRELOAD_MODEL:
        threading.Thread(target=disease_model.warm_up, daemon=True).start()

    # Automatic daily price refresh. This runs asynchronously so an upstream timeout
    # cannot delay the web server from becoming ready. Set MANDI_AUTO_REFRESH_ENABLED=0
    # in tests or when a separate scheduled job is responsible for refreshing prices.
    refresh_stop = asyncio.Event()
    refresh_task = None
    if config.MANDI_AUTO_REFRESH_ENABLED:
        refresh_task = asyncio.create_task(daily_mandi_refresh_loop(refresh_stop))
        log.info(
            "Automatic mandi refresh enabled (interval=%s hour(s), on_startup=%s).",
            config.MANDI_REFRESH_INTERVAL_HOURS, config.MANDI_REFRESH_ON_STARTUP,
        )
    else:
        log.info("Automatic mandi refresh disabled by configuration.")

    try:
        yield
    finally:
        if refresh_task is not None:
            refresh_stop.set()
            refresh_task.cancel()
            try:
                await refresh_task
            except asyncio.CancelledError:
                pass


app = FastAPI(
    title="KisanSaathi API",
    description="KisanSaathi: crop disease, weather-aware irrigation estimates, mandi prices, historical crop insights, live weather, crop productivity planning and direct market for farmers.",
    version="2.0.0",
    lifespan=lifespan,
)

# Lets the pages work even when they are opened from a different port (e.g. port 5500).
# Compress pages, scripts and JSON (helps on slow rural mobile data).
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(CORSMiddleware, allow_origins=config.CORS_ORIGINS, allow_methods=["GET", "POST", "PATCH", "OPTIONS"], allow_headers=["Content-Type", "Authorization"], allow_credentials=False)

app.include_router(disease.router)
app.include_router(prices.router)
app.include_router(crops.router)
app.include_router(irrigation.router)
app.include_router(weather.router)
app.include_router(planning.router)
app.include_router(listings.router)
app.include_router(auth.router)


@app.get("/health", tags=["health"])
def health():
    """Real readiness check: the database must answer a query; model and price-refresh state are reported."""
    from .services.mandi_scheduler import scheduler_state

    database_ok = True
    database_error = None
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:  # report, never crash the health endpoint
        database_ok = False
        database_error = exc.__class__.__name__
    body = {
        "status": "ok" if database_ok else "degraded",
        "database": "connected" if database_ok else "unavailable",
        "database_engine": engine.dialect.name,
        "model": disease_model.status(),
        "model_id": config.MODEL_ID,
        "model_revision": config.MODEL_REVISION,
        "price_refresh": scheduler_state(),
        "phone_verification": config.OTP_PROVIDER,
    }
    if database_error:
        body["database_error"] = database_error
    return JSONResponse(body, status_code=200 if database_ok else 503)


# The website (frontend folder) is served at http://localhost:8000/
# This line must stay LAST so it does not hide the /api routes.
if config.FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIR, html=True), name="frontend")
