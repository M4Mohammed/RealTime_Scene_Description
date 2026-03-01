from fastapi import FastAPI, File, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from io import BytesIO
import base64
from PIL import Image
import json
import logging
import os
import cv2
import tempfile
import numpy as np

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

# Mount the frontend directory to serve static files
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")

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

def mse(imageA, imageB):
    # the 'Mean Squared Error' between the two images is the
    # sum of the squared difference between the two images;
    err = np.sum((imageA.astype("float") - imageB.astype("float")) ** 2)
    err /= float(imageA.shape[0] * imageA.shape[1])
    return err

@app.post("/api/analyze/video")
async def analyze_video(file: UploadFile = File(...)):
    """
    Analyzes an uploaded video file.
    Extracts frames, removes redundant frames, and captions the unique ones.
    """
    temp_video_path = None
    try:
        logger.info(f"Received video: {file.filename}")
        
        # Save uploaded video to a temporary file
        fd, temp_video_path = tempfile.mkstemp(suffix=".mp4")
        with os.fdopen(fd, 'wb') as f:
            f.write(await file.read())

        cap = cv2.VideoCapture(temp_video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        if fps == 0 or total_frames == 0:
            raise Exception("Could not read video properties.")

        frames_data = []
        prev_frame_gray = None
        
        # Extract at most 1 frame per second to avoid overload
        frame_interval = int(fps) 
        if frame_interval <= 0: frame_interval = 1
        
        current_frame = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if current_frame % frame_interval == 0:
                # Resize for faster processing and lower bandwidth
                frame_resized = cv2.resize(frame, (640, 480))
                gray = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2GRAY)
                
                is_unique = True
                
                if prev_frame_gray is not None:
                    # Calculate Mean Squared Error
                    error = mse(gray, prev_frame_gray)
                    logger.info(f"Frame {current_frame} MSE: {error}")
                    # If MSE is low, the frames are very similar (redundant)
                    if error < 1000.0:  # Threshold can be tuned
                        is_unique = False
                
                if is_unique:
                    # Convert to PIL Image for Captioner
                    color_frame = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(color_frame)
                    
                    # Generate Caption
                    # Try using real pipeline, fallback to mock if it fails 
                    try:
                        caption_result = caption_model.generate_caption(pil_img)
                    except Exception as e:
                        logger.warning(f"Caption engine failed, using mock: {e}")
                        caption_result = {
                            "caption": f"MOCK: Video frame {current_frame} extracted.",
                            "latency_ms": 100.0
                        }
                        
                    caption = caption_result["caption"]
                    classification, reason = danger_classifier.classify(caption)
                    
                    # Convert PIL back to base64 for frontend
                    buffered = BytesIO()
                    pil_img.save(buffered, format="JPEG", quality=75)
                    img_str = base64.b64encode(buffered.getvalue()).decode()
                    
                    frames_data.append({
                        "frame_index": current_frame,
                        "time_sec": current_frame / fps,
                        "caption": caption,
                        "classification": classification,
                        "danger_reason": reason,
                        "latency_ms": caption_result.get("latency_ms", 0),
                        "image_base64": img_str
                    })
                    
                    prev_frame_gray = gray
                    
                    # Limit max frames to prevent huge payloads/timeouts
                    if len(frames_data) >= 20: 
                        logger.info("Reached maximum of 20 unique frames.")
                        break
            
            current_frame += 1

        cap.release()
        
        if not frames_data:
             raise Exception("No valid frames could be extracted.")

        logger.info(f"Processed video. Extracted {len(frames_data)} unique frames.")
        return {"frames": frames_data}

    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500
    finally:
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)


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
