import os
import requests
import json
import logging
import base64
from io import BytesIO
from PIL import Image
import numpy as np

logger = logging.getLogger(__name__)

class SemanticChecker:
    """
    Evaluates the semantic difference between two images using an external
    Hugging Face Inference API instead of a local heavy PyTorch model,
    preventing out-of-memory errors on Azure's free tier.
    """
    def __init__(self, model_name="sentence-transformers/clip-ViT-B-32"):
        self.model_name = model_name
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{model_name}"
            
        print(f"Loading SemanticChecker API Client for {model_name}...")
        
    def _image_to_base64(self, image: Image.Image) -> str:
        if image.mode != "RGB":
            image = image.convert("RGB")
        buffered = BytesIO()
        # Compress slightly to save bandwidth
        image.save(buffered, format="JPEG", quality=85)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    def get_embedding(self, image: Image.Image):
        """
        Calls the Hugging Face API to get a normalized semantic feature vector.
        Returns a numpy array representing the embedding, or None on failure.
        """
        if not self.api_key:
             logger.warning("HUGGINGFACE_API_KEY not set. Semantic checks will be skipped.")
             return None
             
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
             # In CLIP sentence-transformers, we just pass the image directly
             img_bytes = BytesIO()
             image.save(img_bytes, format="JPEG")
             img_bytes.seek(0)
             
             response = requests.post(self.api_url, headers=headers, data=img_bytes.read())
             
             if response.status_code == 200:
                 # Response usually a list of floats
                 embedding = np.array(response.json())
                 if embedding.ndim > 1:
                      embedding = embedding[0] # Flatten if batch dimension returned
                 
                 # Normalize
                 norm = np.linalg.norm(embedding)
                 if norm > 0:
                     return embedding / norm
                 return embedding
             else:
                 logger.error(f"Semantic API Error {response.status_code}: {response.text}")
                 return None
                 
        except Exception as e:
             logger.error(f"Failed to fetch embedding: {e}")
             return None
        
    def is_semantically_different(self, emb_a, emb_b, threshold: float = 0.95) -> bool:
        """
        Calculates numpy cosine similarity between two embeddings.
        """
        if emb_a is None or emb_b is None:
            return True # Always different if one is missing

        # Calculate cosine similarity 
        cosine_similarity = np.dot(emb_a, emb_b)
        return cosine_similarity < threshold
