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
        """Read model-server URL from environment and build predict endpoint."""
        base_url = os.getenv("MODEL_SERVER_URL", "http://model-server:8080")
        self.predict_endpoint = f"{base_url.rstrip('/')}/predict"
        print(f"Captioner → model-server at {self.predict_endpoint}")

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
