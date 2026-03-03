"""
VisionAssist Model Server — Standalone GPU Inference API

Loads a Vision-Language Model (BLIP) onto GPU at startup and exposes
a simple REST endpoint for image captioning. Designed to run as a
dedicated Docker container with GPU access.
"""

import os
import io
import time
import base64
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
MODEL_NAME = os.getenv("MODEL_NAME", "Salesforce/blip-image-captioning-base")
MAX_NEW_TOKENS = int(os.getenv("MAX_NEW_TOKENS", "50"))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("model-server")

# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="VisionAssist Model Server",
    description="GPU-accelerated image captioning inference endpoint.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# Model loading (runs once at startup)
# ---------------------------------------------------------------------------
processor = None
model = None
device = None


@app.on_event("startup")
def load_model():
    """Load the BLIP model onto the best available device."""
    global processor, model, device

    import torch
    from transformers import BlipProcessor, BlipForConditionalGeneration

    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32

    logger.info(f"Loading model '{MODEL_NAME}' on {device} ({dtype}) ...")
    processor = BlipProcessor.from_pretrained(MODEL_NAME)
    model = BlipForConditionalGeneration.from_pretrained(
        MODEL_NAME, torch_dtype=dtype
    ).to(device)
    logger.info("Model loaded successfully ✓")


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class PredictRequest(BaseModel):
    image_base64: str  # raw base64 (no data-uri prefix)


class PredictResponse(BaseModel):
    caption: str
    latency_ms: float


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
def health():
    """Readiness probe — returns 200 only after the model is loaded."""
    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")
    return {"status": "ok", "model": MODEL_NAME, "device": str(device)}


@app.post("/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    """Generate a caption for a base64‑encoded image."""
    import torch

    if model is None or processor is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    try:
        image_bytes = base64.b64decode(req.image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image data: {e}")

    start = time.perf_counter()

    inputs = processor(image, return_tensors="pt").to(device, model.dtype)
    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS)
    caption = processor.decode(output_ids[0], skip_special_tokens=True)

    latency_ms = (time.perf_counter() - start) * 1000

    return PredictResponse(caption=caption, latency_ms=latency_ms)
