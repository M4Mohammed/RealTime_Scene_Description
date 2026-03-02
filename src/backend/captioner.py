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
        
        if device:
            self.device = device
        else:
            try:
                import torch
                self.device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                self.device = "cpu"
                
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
            from huggingface_hub import InferenceClient
            
            print("Configuring Hugging Face API via huggingface_hub...")
            self.api_key = os.getenv("HUGGINGFACE_API_KEY")
            if not self.api_key:
                print("WARNING: HUGGINGFACE_API_KEY environment variable not set.")
                
            model_id = os.getenv(
                "HUGGINGFACE_MODEL_URL", 
                "Salesforce/blip-image-captioning-base"
            )
            # Support if full API URL was provided by mistake
            if model_id.startswith("http"):
                model_id = model_id.split("models/")[-1]

            print(f"Hugging Face API configured successfully. Target model: {model_id}")
            self.client = InferenceClient(model=model_id, token=self.api_key)
            
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
            import torch
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
            
            start_time = time.perf_counter()
            
            # Convert PIL Image to Bytes for HTTP Request
            buffered = io.BytesIO()
            if image.mode != "RGB":
                image = image.convert("RGB")
            image.save(buffered, format="JPEG")
            img_bytes = buffered.getvalue()
            
            try:
                # InferenceClient automatically handles timeouts, retries, and formatting.
                caption = self.client.image_to_text(img_bytes)
            except Exception as e:
                error_msg = str(e)
                print(f"Hugging Face API Request Error: {error_msg}")
                # Provide a more descriptive error depending on common Hugging Face issues
                if "401" in error_msg or "Unauthorized" in error_msg:
                    caption = "Error: Invalid or missing Hugging Face API Key."
                elif "503" in error_msg or "loading" in error_msg.lower():
                    caption = "Error: Model is currently loading (Cold Start). Please wait 20 seconds and try again."
                else:
                    caption = f"Error generating caption: {error_msg}"
                
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
