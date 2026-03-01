import torch
import time
from PIL import Image
from typing import Dict, Any

class Captioner:
    """
    A wrapper class to load and run Vision-Language Models for scene description.
    Designed to easily swap models for benchmarking latency and accuracy.
    """
    def __init__(self, model_name: str = "Salesforce/blip-image-captioning-base", device: str = None):
        """
        Initializes the captioning model.
        
        Args:
            model_name (str): Hugging Face model identifier
            device (str): "cuda", "cpu", etc. If None, auto-detects.
        """
        self.model_name = model_name
        self.device = device if device else ("cuda" if torch.cuda.is_available() else "cpu")
        print(f"Initializing {model_name} on {self.device}...")
        
        self.processor = None
        self.model = None
        
        self._load_model()
        
    def _load_model(self):
        """Loads the processor and model based on the model_name."""
        # Note: In a production environment with multiple model types (Qwen, Moondream, etc.),
        # this method would use a factory pattern. For this benchmark foundation, we start with BLIP.
        
        if "blip" in self.model_name.lower():
            from transformers import BlipProcessor, BlipForConditionalGeneration
            self.processor = BlipProcessor.from_pretrained(self.model_name)
            
            # Use float16 on GPU for faster inference
            dtype = torch.float16 if self.device == "cuda" else torch.float32
            self.model = BlipForConditionalGeneration.from_pretrained(
                self.model_name, 
                torch_dtype=dtype
            ).to(self.device)
            print("BLIP model loaded successfully.")
            
        elif self.model_name.lower() == "huggingface-api":
            import os
            import requests
            
            print("Configuring Hugging Face API...")
            self.api_key = os.getenv("HUGGINGFACE_API_KEY")
            if not self.api_key:
                print("WARNING: HUGGINGFACE_API_KEY environment variable not set.")
                
            self.api_url = os.getenv(
                "HUGGINGFACE_MODEL_URL", 
                "https://api-inference.huggingface.co/models/microsoft/git-base-coco"
            )
            print(f"Hugging Face API configured successfully. Target endpoint: {self.api_url}")
            
        else:
            raise NotImplementedError(f"Model loader for {self.model_name} is not implemented yet.")

    def generate_caption(self, image: Image.Image) -> Dict[str, Any]:
        """
        Generates a caption for the given image and measures latency.
        
        Args:
            image (PIL.Image): The input image.
            
        Returns:
            Dict containing the caption string and the latency in milliseconds.
        """
        if "blip" in self.model_name.lower():
            start_time = time.perf_counter()
            
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
            
        elif self.model_name.lower() == "huggingface-api":
            import io
            import requests
            
            start_time = time.perf_counter()
            
            # Convert PIL Image to Bytes for HTTP Request
            buffered = io.BytesIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffered, format="JPEG")
            img_bytes = buffered.getvalue()
            
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            
            try:
                # By default, image captioning models on HF take raw binary image data
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=img_bytes,
                    timeout=60
                )
                
                # If it's a 503 Service Unavailable, model is likely loading.
                if response.status_code == 503:
                    try:
                        result = response.json()
                        wait_time = result.get("estimated_time", 20.0)
                        print(f"Model is loading (503), waiting {wait_time} seconds...")
                    except ValueError:
                        wait_time = 20.0
                        print(f"Model is loading (503), waiting default {wait_time} seconds...")
                        
                    time.sleep(wait_time)
                    response = requests.post(
                        self.api_url,
                        headers=headers,
                        data=img_bytes,
                        timeout=60
                    )
                
                # Check for other HTTP errors (Unauthorized, Bad Request, etc.)
                response.raise_for_status()

                try:
                    result = response.json()
                except ValueError:
                     # sometimes HF returns HTML for 500 errors
                     print(f"Failed to parse JSON. Raw API response: {response.text}")
                     caption = f"HF API Error (Non-JSON): {response.status_code}"
                     result = None

                if result:
                    if isinstance(result, list) and len(result) > 0 and "generated_text" in result[0]:
                        caption = result[0]["generated_text"].strip()
                    elif isinstance(result, dict) and "error" in result:
                        caption = f"Hugging Face API Error: {result['error']}"
                    else:
                        caption = f"HF API unexpected format: {result}"
                    
            except requests.exceptions.HTTPError as http_err:
                print(f"Hugging Face HTTP Error: {http_err} - Body: {response.text}")
                caption = f"HTTP {response.status_code}: Error generating caption with Hugging Face API."
            except Exception as e:
                print(f"Hugging Face API Request Error: {e}")
                caption = "Error generating caption with Hugging Face API."
                
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            return {
                "caption": caption,
                "latency_ms": latency_ms
            }
            
        else:
             raise NotImplementedError(f"Generation for {self.model_name} is not implemented yet.")

# Simple self-test
if __name__ == "__main__":
    # Create a dummy image for testing initialization and inference pipeline
    dummy_image = Image.new('RGB', (224, 224), color = 'red')
    
    try:
        # We test with the huggingface-api to ensure code runs without long downloads
        print("Testing Captioner pipeline...")
        captioner = Captioner(model_name="huggingface-api")
        # Ensure HUGGINGFACE_API_KEY is set or the test will print a warning and return an unauthorized error
        result = captioner.generate_caption(dummy_image)
        
        print(f"\nTest Result:")
        print(f"Caption: {result['caption']}")
        print(f"Latency: {result['latency_ms']:.2f} ms")
        print("Captioner test successful!")
    except Exception as e:
        print(f"Captioner test failed: {e}")
