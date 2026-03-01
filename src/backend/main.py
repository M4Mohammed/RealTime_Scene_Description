from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from io import BytesIO
import base64
from PIL import Image
import json
import logging

# Set up simple logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Real-Time Scene Description & Danger Detection API",
    description="API for assistive scene description and context-aware danger classification.",
    version="1.0.0"
)

# Enable CORS for the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to the frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize modules (Lazy loading for actual models)
from .classifier import DangerClassifier
# Note: For production, we'd initialize the model once globally.
# For this skeleton, we will mock the captioner just to test the API structure,
# and initialize the real one inside the actual benchmark/evaluation scripts later.
# 
from .captioner import Captioner
# Global initialized model - using huggingface-api for free inference without GPU
caption_model = Captioner(model_name="huggingface-api")
danger_classifier = DangerClassifier()

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {"status": "ok", "message": "VisionAssist API is running."}

@app.post("/api/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    """
    Analyzes a single uploaded static image.
    Extracts the image, generates a caption, and classifies it.
    """
    try:
        image_bytes = await file.read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        
        # MOCK PIPELINE FOR NOW
        caption_result = {
            "caption": "MOCK: A mock caption of the uploaded image containing a hole in the ground.",
            "latency_ms": 150.0
        }
        
        # Real pipeline would be:
        caption_result = caption_model.generate_caption(image)
        
        caption = caption_result["caption"]
        classification, reason = danger_classifier.classify(caption)
        
        result_payload = {
            "caption": caption,
            "classification": classification,
            "danger_reason": reason,
            "latency_ms": caption_result["latency_ms"],
            "total_latency_ms": caption_result["latency_ms"] + 5.0 # Mock total
        }
        
        return result_payload

    except Exception as e:
        logger.error(f"Error processing image: {str(e)}")
        return {"error": str(e)}, 500


@app.websocket("/ws/livestream")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time video/camera analysis.
    Accepts base64 encoded image frames from the frontend.
    """
    await websocket.accept()
    logger.info("WebSocket client connected.")
    
    try:
        while True:
            # Receive frame data (expecting JSON with base64 encoded image)
            data = await websocket.receive_text()
            payload = json.loads(data)
            
            if 'frame' not in payload:
                await websocket.send_json({"error": "No frame data received."})
                continue
                
            # Decode the base64 string
            frame_data = payload['frame']
            
            # The string might look like "data:image/jpeg;base64,/9j/4AAQSk..."
            if ',' in frame_data:
                frame_data = frame_data.split(',')[1]
                
            image_bytes = base64.b64decode(frame_data)
            image = Image.open(BytesIO(image_bytes)).convert("RGB")
            
            # MOCK PIPELINE FOR REAL-TIME
            caption_result = {
                "caption": "MOCK: Real-time caption of an open manhole on the street.",
                "latency_ms": 140.0
            }
            
            # Real pipeline would be:
            # caption_result = caption_model.generate_caption(image)
            
            caption = caption_result["caption"]
            classification, reason = danger_classifier.classify(caption)
            
            response_payload = {
                "caption": caption,
                "classification": classification,
                "danger_reason": reason,
                "latency_ms": caption_result["latency_ms"]
            }
            
            # Send result back to the frontend
            await websocket.send_json(response_payload)
            
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        try:
             await websocket.send_json({"error": str(e)})
        except:
             pass
