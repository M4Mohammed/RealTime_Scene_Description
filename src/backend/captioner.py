import time
import os
import io
import base64
import requests
from PIL import Image
from typing import Dict, Any


class Captioner:
    """
    Sends images to the model-server for captioning via HTTP.

    The model-server URL is read from the MODEL_SERVER_URL environment
    variable (default: http://model-server:8080, the Docker Compose
    service name).
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
        Generates a caption for the given image by calling the model-server.

        Returns:
            {"caption": str, "latency_ms": float}
        """
        start_time = time.perf_counter()

        # Encode image to base64
        buffered = io.BytesIO()
        if image.mode != "RGB":
            image = image.convert("RGB")
        image.save(buffered, format="JPEG")
        img_b64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        try:
            response = requests.post(
                self.predict_endpoint,
                json={"image_base64": img_b64},
                timeout=30,
            )

            if response.status_code == 200:
                result = response.json()
                caption = result.get("caption", "Error: no caption in response")
            elif response.status_code == 503:
                caption = "Model is still loading. Please wait and try again."
            else:
                error_msg = response.text[:200]
                print(f"Model-server HTTP {response.status_code}: {error_msg}")
                caption = f"Error: model-server returned HTTP {response.status_code}"

        except requests.exceptions.ConnectionError:
            caption = "Error: Cannot reach model-server. Is it running?"
        except requests.exceptions.Timeout:
            caption = "Error: Model-server request timed out."
        except Exception as e:
            caption = f"Error generating caption: {e}"

        latency_ms = (time.perf_counter() - start_time) * 1000

        return {
            "caption": caption,
            "latency_ms": latency_ms,
        }


# Simple self-test
if __name__ == "__main__":
    dummy_image = Image.new("RGB", (224, 224), color="red")

    try:
        print("Testing Captioner (model-server must be running)...")
        captioner = Captioner()
        result = captioner.generate_caption(dummy_image)

        print(f"\nTest Result:")
        print(f"Caption: {result['caption']}")
        print(f"Latency: {result['latency_ms']:.2f} ms")
        print("Captioner test complete.")
    except Exception as e:
        print(f"Captioner test failed: {e}")
