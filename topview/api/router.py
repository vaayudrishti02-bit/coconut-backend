from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse, Response
import numpy as np
import cv2
import io
import base64

from topview.api.model_path import get_model_path
from topview.model import TopViewModel
from topview.utils import assign_numbers, draw_overlay

router = APIRouter(prefix="/topview", tags=["Top-View Detection"])

# Load YOLO model using model_path.py
model = TopViewModel(get_model_path())

# ---------------------------------------------------------
# 1️⃣ JSON Only
# ---------------------------------------------------------
@router.post("/detect")
async def detect_json(file: UploadFile = File(...)):
    img_bytes = await file.read()

    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(400, "Invalid image")

    boxes = model.detect_trees(img)
    numbered = assign_numbers(boxes, img.shape[0])

    return {"count": len(numbered), "trees": numbered}

# ---------------------------------------------------------
# 2️⃣ Annotated Image Output
# ---------------------------------------------------------
@router.post(
    "/detect/image",
    responses={
        200: {
            "description": "Annotated image (PNG)",
            "content": {
                "image/png": {
                    "schema": {"type": "string", "format": "binary"}
                }
            },
        }
    },
)
async def detect_image(file: UploadFile = File(...)):
    img_bytes = await file.read()

    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(400, "Invalid image")

    boxes = model.detect_trees(img)
    numbered = assign_numbers(boxes, img.shape[0])
    annotated = draw_overlay(img, numbered)

    ok, buf = cv2.imencode(".png", annotated)
    if not ok:
        raise HTTPException(500, "Image encoding failed")

    # Return direct PNG bytes with inline disposition for better Swagger/browser display
    return Response(
        content=buf.tobytes(),
        media_type="image/png",
        headers={"Content-Disposition": "inline; filename=annotated.png"},
    )

# ---------------------------------------------------------
# 3️⃣ JSON + Base64 Image (Full response)
# ---------------------------------------------------------
@router.post("/detect/full")
async def detect_full(file: UploadFile = File(...)):
    img_bytes = await file.read()

    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

    if img is None:
        raise HTTPException(400, "Invalid image")

    boxes = model.detect_trees(img)
    numbered = assign_numbers(boxes, img.shape[0])
    annotated = draw_overlay(img, numbered)

    ok, buf = cv2.imencode(".png", annotated)
    if not ok:
        raise HTTPException(500, "Image encoding failed")

    b64 = base64.b64encode(buf).decode("utf-8")

    return {
        "count": len(numbered),
        "trees": numbered,
        "image_base64": b64
    }
