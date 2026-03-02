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
# Global initialized model - enforcing Blip-Base
caption_model = Captioner()
danger_classifier = DangerClassifier()

# We will mount the frontend directory to serve static files at the end of the file.
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")


@app.post("/api/analyze/image")
async def analyze_image(file: UploadFile = File(...)):
    """
    Analyzes a single uploaded static image.
    Extracts the image, generates a caption, and classifies it.
    """
    try:
        image_bytes = await file.read()
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        
        # Use real pipeline
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

        # Prepare VideoWriter for the output synthesized video
        out_fd, out_temp_video_path = tempfile.mkstemp(suffix=".mp4")
        
        # Determine output dimensions (standardize to 640x480 for consistency)
        out_width = 800
        out_height = 600
        
        # Use simple mp4v codec for standard web compatibility
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_video = cv2.VideoWriter(out_temp_video_path, fourcc, fps, (out_width, out_height))

        prev_frame_gray = None
        current_caption = "Analyzing initial scene..."
        current_status = "UNKNOWN"
        
        # Extract at most 1 frame per second to avoid HF API overload
        frame_interval = int(fps) 
        if frame_interval <= 0: frame_interval = 1
        
        current_frame = 0
        total_processed_unique_frames = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            # Resize internal processing frames for perf
            process_frame = cv2.resize(frame, (640, 480))
            gray = cv2.cvtColor(process_frame, cv2.COLOR_BGR2GRAY)
            
            # Check for unique keyframes every 1 second
            if current_frame % frame_interval == 0 and total_processed_unique_frames < 20:
                is_unique = True
                
                if prev_frame_gray is not None:
                    error = mse(gray, prev_frame_gray)
                    logger.info(f"Frame {current_frame} MSE: {error}")
                    if error < 1000.0:  # Threshold
                        is_unique = False
                
                if is_unique:
                    logger.info(f"Generating caption for unique frame {current_frame}...")
                    color_frame = cv2.cvtColor(process_frame, cv2.COLOR_BGR2RGB)
                    pil_img = Image.fromarray(color_frame)
                    
                    try:
                        caption_result = caption_model.generate_caption(pil_img)
                        current_caption = caption_result["caption"]
                    except Exception as e:
                        logger.warning(f"Caption engine failed: {e}")
                        current_caption = "Error generating caption."
                        
                    classification, reason = danger_classifier.classify(current_caption)
                    current_status = classification.upper()
                    
                    total_processed_unique_frames += 1
                    prev_frame_gray = gray
            
            # ---------------------------------------------------------
            # DRAW OVERLAY ON THE CURRENT FRAME
            # ---------------------------------------------------------
            # We resize the display frame to our target 800x600 size
            display_frame = cv2.resize(frame, (out_width, out_height))
            
            # Create a black semi-transparent background bar at the bottom
            overlay = display_frame.copy()
            overlay_height = 120
            cv2.rectangle(overlay, (0, out_height - overlay_height), (out_width, out_height), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, display_frame, 0.3, 0, display_frame)
            
            # Determine Color for Status Box
            status_color = (0, 255, 0) if current_status == "SAFE" else (0, 0, 255)
            if current_status == "UNKNOWN":
                status_color = (200, 200, 200)
                
            # Draw Status Box (Top Right padding)
            cv2.rectangle(display_frame, (10, out_height - overlay_height + 10), (130, out_height - overlay_height + 40), status_color, -1)
            cv2.putText(display_frame, current_status, (25, out_height - overlay_height + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Handle Long Captions (Split into 2 lines if needed)
            max_chars = 60
            if len(current_caption) > max_chars:
                words = current_caption.split(' ')
                line1, line2 = "", ""
                for word in words:
                    if len(line1) + len(word) < max_chars:
                        line1 += word + " "
                    else:
                        line2 += word + " "
                cv2.putText(display_frame, line1.strip(), (150, out_height - overlay_height + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
                cv2.putText(display_frame, line2.strip(), (150, out_height - overlay_height + 62), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
            else:
                cv2.putText(display_frame, current_caption, (150, out_height - overlay_height + 32), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)

            # Write the modified frame to the output video
            out_video.write(display_frame)
            current_frame += 1
            
            # Stop if we hit 600 total frames to prevent huge memory buffers/timeouts in free Azure App
            if current_frame > 600:
                logger.info("Reached maximum allowed video duration (600 frames).")
                break

        cap.release()
        out_video.release()
        
        logger.info(f"Video synthesis complete. Processed {total_processed_unique_frames} unique keyframes.")
        
        # Read the generated MP4 file and encode to base64
        with open(out_temp_video_path, "rb") as video_file:
            video_bytes = video_file.read()
            video_b64 = base64.b64encode(video_bytes).decode('ascii')
            
        return {
             "video_base64": video_b64,
             "total_frames": current_frame,
             "unique_keyframes": total_processed_unique_frames
        }

    except Exception as e:
        logger.error(f"Error processing video: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}, 500
    finally:
        # Clean up temporary files
        if temp_video_path and os.path.exists(temp_video_path):
            os.remove(temp_video_path)
        try:
             if 'out_temp_video_path' in locals() and os.path.exists(out_temp_video_path):
                 os.remove(out_temp_video_path)
        except Exception:
             pass


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
            
            try:
                # Use real pipeline for Live Camera
                caption_result = caption_model.generate_caption(image)
            except Exception as e:
                logger.error(f"WebSocket Captioner Error: {e}")
                caption_result = {
                    "caption": f"Error communicating with AI Space API: {str(e)}",
                    "latency_ms": 0.0
                }
            
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

# Mount the frontend directory to serve static files AT THE VERY END
# so it doesn't intercept /api/... requests (FastAPI evaluates routes in order)
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
