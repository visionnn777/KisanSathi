"""Live-weather irrigation planning using a seven-day forecast."""
from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from ..services import rate_limit
from ..services.irrigation import IrrigationDataError, calculate_irrigation

router = APIRouter(prefix="/api/irrigation", tags=["irrigation"])


class IrrigationRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    location: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=80)
    crop: Literal["maize", "wheat", "rice", "tomato", "potato", "soybean", "onion", "mustard", "chickpea", "groundnut", "cotton", "sugarcane", "pearl millet", "sorghum"]
    stage: Literal["initial", "development", "mid_season", "late_season"]
    area_ha: float = Field(gt=0, le=10_000)
    efficiency: float = Field(default=0.70, ge=0.30, le=1.0)
    soil_texture: Literal["unknown", "sandy", "loamy", "alluvial", "clayey", "black", "red"] = "unknown"
    field_moisture: Literal["unknown", "dry", "normal", "wet"] = "unknown"


@router.post("/estimate")
def estimate_irrigation(data: IrrigationRequest, request: Request):
    rate_limit.limit_client(request, "weather_calls", 60, 600)
    try:
        return calculate_irrigation(data.location, data.state, data.crop, data.stage,
                                    data.area_ha, data.efficiency, data.soil_texture, data.field_moisture)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except IrrigationDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
