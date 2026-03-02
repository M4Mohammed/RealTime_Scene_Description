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
        self.model_name = "Salesforce/blip-image-captioning-base"
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
            
            # Convert PIL Image to Bytes for HTTP Request
            buffered = io.BytesIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffered, format="JPEG")
            img_bytes = buffered.getvalue()
            
            try:
                caption = self.client.image_to_text(img_bytes)
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = str(e) if str(e) else repr(e)
                print(f"Hugging Face API Request Error: {error_msg}")
                if "401" in error_msg or "Unauthorized" in error_msg:
                    caption = "Error: Invalid or missing Hugging Face API Key."
                elif "503" in error_msg or "loading" in error_msg.lower():
                    caption = "Error: Model is currently loading (Cold Start). Please wait 20 seconds and try again."
                else:
                    caption = f"Error generating caption via API: {error_msg}"
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
