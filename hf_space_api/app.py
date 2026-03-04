import io
import base64
import torch
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image
from transformers import BlipProcessor, BlipForConditionalGeneration

app = FastAPI(title="VisionAssist BLIP-Large API")

# Global variables for model and processor
model_name = "Salesforce/blip-image-captioning-large"
device = "cuda" if torch.cuda.is_available() else "cpu"
processor = None
model = None

@app.on_event("startup")
async def load_model():
    global processor, model
    print(f"Loading {model_name} on {device}...")
    try:
        processor = BlipProcessor.from_pretrained(model_name)
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = BlipForConditionalGeneration.from_pretrained(
            model_name, 
            torch_dtype=dtype
        ).to(device)
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Error loading model: {e}")

class ImageRequest(BaseModel):
    inputs: str

@app.post("/predict")
async def predict(request: ImageRequest):
    """
    Accepts a base64 encoded image string and returns the generated caption.
    """
    start_time = time.perf_counter()
    if not processor or not model:
        raise HTTPException(status_code=503, detail="Model is currently loading or failed to load. Please try again later.")
        
    try:
        # Decode base64 image
        image_data = base64.b64decode(request.inputs)
        image = Image.open(io.BytesIO(image_data))
        
        if image.mode != "RGB":
            image = image.convert("RGB")
            
        # Process image
        inputs = processor(image, return_tensors="pt").to(device, model.dtype)
        
        # Generate caption
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=50)
            
        caption = processor.decode(out[0], skip_special_tokens=True)
        
        latency = (time.perf_counter() - start_time) * 1000
        
        # Format response identical to HF Inference API format
        return [{"generated_text": caption, "latency_ms": round(latency, 2)}]
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error processing image: {str(e)}")

@app.get("/")
def health_check():
    return {"status": "healthy", "model": model_name, "device": device}
