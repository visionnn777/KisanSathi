"""Live current conditions and seven-day forecast for an Indian town or district."""
from fastapi import APIRouter, HTTPException, Request, Query
from ..services import rate_limit
from ..services.irrigation import IrrigationDataError
from ..services.weather import get_live_forecast

router = APIRouter(prefix="/api/weather", tags=["live weather"])


@router.get("/forecast")
def live_weather_forecast(
    request: Request,
    location: str = Query(min_length=2, max_length=100),
    state: str | None = Query(default=None, min_length=2, max_length=80),
    days: int = Query(default=7, ge=1, le=7),
):
    rate_limit.limit_client(request, "weather_calls", 60, 600)
    try:
        return get_live_forecast(location, state, days)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IrrigationDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
