import time
import os
from PIL import Image
from typing import Dict, Any

class Captioner:
    """
    A wrapper class to load and run the Blip-Base Vision-Language Model for scene description.
    """
    def __init__(self):
        """
        Initializes the Blip-Base captioning model.
        It uses the Hugging Face API if HUGGINGFACE_API_KEY is present,
        otherwise it attempts to load the model locally.
        """
        self.model_name = "Salesforce/blip-image-captioning-large"
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.use_api = bool(self.api_key)
        
        print(f"Initializing {self.model_name}...")
        
        self.processor = None
        self.model = None
        self.client = None
        
        self._load_model()
        
    def _load_model(self):
        """Loads the Blip-Base model either via API client or local transformers."""
        if self.use_api:
            from huggingface_hub import InferenceClient
            print("Configuring Hugging Face API via huggingface_hub for Blip-Base...")
            self.client = InferenceClient(model=self.model_name, token=self.api_key)
            print("Hugging Face API configured successfully.")
        else:
            print("No HUGGINGFACE_API_KEY found. Attempting to load Blip-Base locally...")
            try:
                import torch
                from transformers import BlipProcessor, BlipForConditionalGeneration
                
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"Loading local model on {self.device}...")
                
                self.processor = BlipProcessor.from_pretrained(self.model_name)
                dtype = torch.float16 if self.device == "cuda" else torch.float32
                self.model = BlipForConditionalGeneration.from_pretrained(
                    self.model_name, 
                    torch_dtype=dtype
                ).to(self.device)
                print("Local BLIP model loaded successfully.")
            except ImportError as e:
                print(f"Error loading local model. Please install torch and transformers. {e}")
                raise

    def generate_caption(self, image: Image.Image) -> Dict[str, Any]:
        """
        Generates a caption for the given image using Blip-Base and measures latency.
        """
        start_time = time.perf_counter()
        
        if self.use_api:
            import io
            import requests
            import base64
            
            # Convert PIL Image to Base64 String for JSON Payload
            buffered = io.BytesIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffered, format="JPEG")
            img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
            
            try:
                # Use custom dedicated HF Space API
                api_url = "https://a7med-ame3-visionassist-api.hf.space/predict"
                headers = {"Content-Type": "application/json"}
                
                payload = {
                    "inputs": img_b64
                }
                
                response = requests.post(api_url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        if isinstance(result, list) and len(result) > 0 and "generated_text" in result[0]:
                            caption = result[0]["generated_text"]
                        else:
                            caption = f"Error: Unexpected response format: {result}"
                    except Exception as json_err:
                        caption = f"Error parsing JSON success response: {json_err}"
                else:
                    error_msg = response.text
                    if len(error_msg) > 200:
                        error_msg = error_msg[:200]
                    print(f"Custom HF Space API HTTP Error {response.status_code}: {error_msg}")
                    if response.status_code == 503 or "loading" in error_msg.lower():
                        caption = "Error: Custom API Model is currently loading (Cold Start). Please wait 30 seconds and try again."
                    else:
                        caption = f"Error generating caption via Custom API HTTP {response.status_code}. (Check logs)"
                        
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = str(e) if str(e) else repr(e)
                print(f"Custom HF Space API Request Exception: {error_msg}")
                caption = f"Error generating caption via Custom API: {error_msg}"
        else:
            import torch
            
            # Prepare inputs
            inputs = self.processor(image, return_tensors="pt").to(self.device, self.model.dtype)
            
            # Generate output
            with torch.no_grad():
                out = self.model.generate(**inputs, max_new_tokens=50)
                
            caption = self.processor.decode(out[0], skip_special_tokens=True)
            
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        return {
            "caption": caption,
            "latency_ms": latency_ms
        }

# Simple self-test
if __name__ == "__main__":
    dummy_image = Image.new('RGB', (224, 224), color = 'red')
    
    try:
        print("Testing Blip-Base Captioner pipeline...")
        captioner = Captioner()
        result = captioner.generate_caption(dummy_image)
        
        print(f"\\nTest Result:")
        print(f"Caption: {result['caption']}")
        print(f"Latency: {result['latency_ms']:.2f} ms")
        print("Captioner test successful!")
    except Exception as e:
        print(f"Captioner test failed: {e}")
