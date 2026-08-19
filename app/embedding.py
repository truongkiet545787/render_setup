import io
import re
import unicodedata
import logging
from PIL import Image
import numpy as np
from typing import Optional, Tuple, List
from sqlalchemy.orm import Session
from . import models

logger = logging.getLogger("uvicorn.error")

_embedding_model = None

def get_image_embedding_model():
    """
    Lazy load FastEmbed ImageEmbedding model (ONNX based, lightweight ~100MB RAM).
    Uses Qdrant/clip-ViT-B-32-vision (512-dimensional output).
    Configured with threads=1 for minimal memory footprint on free cloud instances.
    """
    global _embedding_model
    if _embedding_model is None:
        try:
            import gc
            from fastembed import ImageEmbedding
            logger.info("[Embedding] Loading FastEmbed ONNX Image model (Qdrant/clip-ViT-B-32-vision)...")
            _embedding_model = ImageEmbedding(model_name="Qdrant/clip-ViT-B-32-vision", threads=1)
            gc.collect()
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
        logger.warning(f"[Vector Search] Vector search failed: {e}")
        return None

def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd = unicodedata.normalize('NFKD', input_str)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).replace('đ', 'd').replace('Đ', 'D')

def normalize_food_text(text: str) -> str:
    clean = remove_accents(text.lower())
    clean = re.sub(r'[^a-z0-9\s_]', ' ', clean)
    return re.sub(r'\s+', '_', clean).strip('_')

# English to Vietnamese food synonyms mapping
FOOD_SYNONYMS = {
    "apple": ["tao", "qua_tao", "trai_tao"],
    "banana": ["chuoi", "qua_chuoi", "trai_chuoi"],
    "orange": ["cam", "qua_cam", "trai_cam"],
    "tomato": ["ca_chua", "qua_ca_chua"],
    "egg": ["trung", "trung_ga", "trung_vit", "trung_op_la"],
    "cucumber": ["dua_leo", "dua_chuot"],
    "potato": ["khoai_tay", "cu_khoai_tay"],
    "fries": ["khoai_tay_chien"],
    "burger": ["hamburger", "banh_burger"],
    "pizza": ["banh_pizza"],
    "pho": ["pho_bo", "pho_ga", "to_pho", "bat_pho"],
    "banh_mi": ["banh_my", "banh_mi_thit", "banh_mi_pate", "o_banh_mi"],
    "bun_bo_hue": ["bun_bo", "to_bun_bo", "to_bun_bo_hue"],
    "com_tam": ["com_tam_suon", "dia_com_tam", "com_suon"],
    "goi_cuon": ["nem_cuon", "cuon_diep"],
    "coca_cola": ["coca", "coke", "nuoc_ngot_coca"],
    "pepsi": ["nuoc_ngot_pepsi"],
    "7up": ["bay_up", "nuoc_ngot_7up"],
    "red_bull": ["bo_huc", "nuoc_tang_luc_bo_huc"],
    "yakult": ["sua_chua_yakult", "sua_uong_yakult"],
    "milo": ["sua_milo", "sua_cacao_milo"]
}

def match_vlm_name_to_existing_class(vlm_name: str, db: Session) -> Optional[Tuple[models.Product, float]]:
    """
    Semantically aligns VLM detected food name with existing database product classes
    to prevent duplicate class creation.
    Returns (Product, match_score) if matched, else None.
    """
    if not vlm_name:
        return None

    normalized_vlm = normalize_food_text(vlm_name)
    all_products = db.query(models.Product).all()

    best_match = None
    best_score = 0.0

    for prod in all_products:
        prod_norm = normalize_food_text(prod.name)
        
        # 1. Exact match
        if prod_norm == normalized_vlm:
            logger.info(f"[Semantic Alignment] Exact Match: '{vlm_name}' -> '{prod.name}'")
            return prod, 1.0

        # 2. Substring containment
        if prod_norm in normalized_vlm or normalized_vlm in prod_norm:
            score = 0.90
            if score > best_score:
                best_score = score
                best_match = prod

        # 3. Synonym matching
        synonyms = FOOD_SYNONYMS.get(prod_norm, [])
        for syn in synonyms:
            if syn in normalized_vlm or normalized_vlm in syn:
                score = 0.88
                if score > best_score:
                    best_score = score
                    best_match = prod

        # 4. Token overlap (Jaccard on words)
        tokens_vlm = set(normalized_vlm.split('_'))
        tokens_prod = set(prod_norm.split('_'))
        intersection = tokens_vlm.intersection(tokens_prod)
        if intersection:
            score = len(intersection) / float(len(tokens_vlm.union(tokens_prod)))
            if score >= 0.5 and score > best_score:
                best_score = score
                best_match = prod

    if best_match and best_score >= 0.5:
        logger.info(f"[Semantic Alignment] Matched '{vlm_name}' to existing class '{best_match.name}' (score: {best_score:.2f})")
        return best_match, best_score

    logger.info(f"[Semantic Alignment] No existing class matched for '{vlm_name}'. Treating as genuinely new dish.")
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
