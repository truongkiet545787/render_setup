import io
import logging
from PIL import Image
import numpy as np
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from . import models

logger = logging.getLogger("uvicorn.error")

_embedding_model = None

def get_image_embedding_model():
    """
    Lazy load FastEmbed ImageEmbedding model (ONNX based, lightweight ~100MB RAM).
    Uses Qdrant/clip-ViT-B-32-vision (512-dimensional output).
    """
    global _embedding_model
    if _embedding_model is None:
        try:
            from fastembed import ImageEmbedding
            logger.info("[Embedding] Loading FastEmbed ONNX Image model (Qdrant/clip-ViT-B-32-vision)...")
            _embedding_model = ImageEmbedding(model_name="Qdrant/clip-ViT-B-32-vision")
            logger.info("[Embedding] Model loaded successfully.")
        except Exception as e:
            logger.error(f"[Embedding] Failed to load FastEmbed: {e}")
            raise e
    return _embedding_model

def extract_image_vector(image_bytes: bytes) -> list[float]:
    """
    Extracts a 512-dimensional normalized embedding vector from image bytes.
    """
    try:
        model = get_image_embedding_model()
        bio = io.BytesIO(image_bytes)
        embeddings = list(model.embed([bio]))
        vector = embeddings[0].tolist()
        return vector
    except Exception as e:
        logger.error(f"[Embedding] Failed to extract image vector: {e}")
        raise e

def find_similar_food_by_vector(
    vector: list[float], 
    db: Session, 
    similarity_threshold: float = 0.85
) -> Optional[Tuple[models.Product, float]]:
    """
    Searches for the most similar food item in PostgreSQL using Cosine Distance.
    Returns (Product, similarity_score) if similarity >= threshold, else None.
    """
    try:
        db_url_str = str(db.bind.url)
        if "postgres" not in db_url_str:
            logger.info("[Vector Search] Current DB is SQLite; skipping pgvector search.")
            return None

        # Cosine distance in pgvector: embedding.cosine_distance(v)
        # Cosine similarity = 1 - cosine_distance
        result = (
            db.query(
                models.FoodEmbedding,
                (1.0 - models.FoodEmbedding.embedding.cosine_distance(vector)).label("similarity")
            )
            .order_by(models.FoodEmbedding.embedding.cosine_distance(vector))
            .first()
        )

        if result:
            food_embed, similarity = result
            sim_val = float(similarity)
            product = food_embed.product
            logger.info(f"[Vector Search] Closest match: '{product.name}' (Product ID: {product.id}) with similarity {sim_val:.4f}")
            
            if sim_val >= similarity_threshold:
                logger.info(f"[Vector Search] Match ACCEPTED (similarity {sim_val:.4f} >= {similarity_threshold})")
                return product, sim_val
            else:
                logger.info(f"[Vector Search] Match REJECTED (similarity {sim_val:.4f} < {similarity_threshold})")
        
        return None
    except Exception as e:
        logger.warning(f"[Vector Search] Vector search failed or table empty: {e}")
        return None

def save_food_vector(product_id: int, vector: list[float], source: str, db: Session):
    """
    Saves a newly generated embedding vector for a product into pgvector.
    """
    try:
        db_url_str = str(db.bind.url)
        if "postgres" not in db_url_str:
            return

        embedding_entry = models.FoodEmbedding(
            product_id=product_id,
            embedding=vector,
            source=source
        )
        db.add(embedding_entry)
        db.commit()
        logger.info(f"[Vector Cache] Saved new vector embedding for Product ID {product_id} (source: {source})")
    except Exception as e:
        logger.warning(f"[Vector Cache] Failed to save embedding vector: {e}")
        db.rollback()
