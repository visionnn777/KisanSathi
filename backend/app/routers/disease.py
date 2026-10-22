"""Crop Doctor: upload a leaf photo, get the disease and advice in English and Hindi.

Owner: Member B
"""
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from .. import config
from ..services import disease_model, rate_limit
from ..services.remedies import EXPERT, UNSURE, describe, match_label

router = APIRouter(prefix="/api/disease", tags=["disease"])
# If the best and second-best answers are this close, the photo is a close call: say "not sure".
MIN_MARGIN = 0.15
MIN_ALTERNATIVE = 0.10


def _alternative(r):
    info = describe(r["label"])
    return {"label": r["label"], "confidence": round(float(r["score"]) * 100, 1),
            "crop": info["crop"], "name": info["name"]}


@router.post("/predict")
def predict_disease(request: Request, file: UploadFile = File(...)):
    # A normal "def" (not async): FastAPI runs it in a worker thread,
    # so a slow prediction does not freeze the rest of the server.
    rate_limit.limit_client(request, "disease_predict", 30, 600)
    ctype = (file.content_type or "").lower()
    if ctype and not (ctype.startswith("image/") or ctype == "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Please upload a photo (JPG or PNG) of a leaf")

    max_bytes = int(config.MAX_UPLOAD_MB * 1024 * 1024)
    data = file.file.read(max_bytes + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The photo is empty")
    if len(data) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Photo is larger than {config.MAX_UPLOAD_MB:g} MB")

    try:
        results, plant_share = disease_model.analyse(data, top_k=3)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except disease_model.ModelNotReady as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    if not results:
        raise HTTPException(status_code=500, detail="The model returned no result")

    top = results[0]
    top_id = match_label(top["label"])
    second = float(results[1]["score"]) if len(results) > 1 else 0.0
    reason = None
    if plant_share < disease_model.MIN_PLANT_SHARE:
        reason = "not_leaf_like"
    elif top_id is None or top_id == "invalid":
        reason = "invalid_or_unknown"
    elif float(top["score"]) < config.CONFIDENCE_MIN:
        reason = "low_confidence"
    elif float(top["score"]) - second < MIN_MARGIN:
        reason = "close_call"
    confident = reason is None
    return {
        "label": top["label"],
        "confidence": round(float(top["score"]) * 100, 1),
        "confident": confident,
        "uncertain_reason": reason,
        "plant_pixel_share": round(plant_share, 2),
        "result": describe(top["label"]) if confident else UNSURE,
        "alternatives": [_alternative(r) for r in results[1:] if float(r["score"]) >= MIN_ALTERNATIVE],
        "expert": EXPERT,
        "model": config.MODEL_ID,
    }
