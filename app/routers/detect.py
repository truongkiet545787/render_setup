from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from typing import Optional
import json
import logging

from ..database import get_db
from .. import models, schemas
from ..redis import get_cache, set_cache
from ..config import settings
from ..embedding import extract_image_vector, find_similar_food_by_vector, save_food_vector

logger = logging.getLogger("uvicorn.error")
router = APIRouter(
    prefix="/detect",
    tags=["Detection"]
)

# Helper function to save product details to DB and cache
def save_new_food_to_db_and_cache(name: str, details: dict, db: Session) -> models.Product:
    # Check if already exists in DB
    existing = db.query(models.Product).filter(models.Product.name == name.strip().lower()).first()
    if existing:
        return existing

    # 1. Create Product
    product = models.Product(
        name=name.strip().lower(),
        brand=details.get("brand")
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    
    # 2. Create Nutrition
    nutrition = models.Nutrition(
        product_id=product.id,
        calories=float(details.get("calories", 0.0)),
        protein=float(details.get("protein", 0.0)),
        fat=float(details.get("fat", 0.0)),
        carbohydrate=float(details.get("carbohydrate", 0.0)),
        sugar=float(details.get("sugar", 0.0)),
        fiber=float(details.get("fiber", 0.0)),
        potassium=float(details.get("potassium", 0.0)),
        vitamin_c=float(details.get("vitamin_c", 0.0))
    )
    db.add(nutrition)
    
    # 3. Create Ingredients
    for ing_name in details.get("ingredients", []):
        db.add(models.Ingredient(product_id=product.id, name=ing_name))
        
    # 4. Create Allergens
    for alg_name in details.get("allergens", []):
        db.add(models.Allergen(product_id=product.id, name=alg_name))
        
    db.commit()
    db.refresh(product)
    
    # 5. Save to cache
    product_schema = schemas.ProductResponse.model_validate(product)
    cache_key = f"nutrition:{name.strip().lower()}"
    set_cache(cache_key, product_schema.model_dump())
    
    return product

@router.get("", response_model=schemas.DetectResponse)
def detect_food(name: str, db: Session = Depends(get_db)):
    normalized_name = name.strip().lower()
    
    # 1. Check Redis Cache
    cache_key = f"nutrition:{normalized_name}"
    cached_data = get_cache(cache_key)
    if cached_data:
        logger.info(f"Cache HIT for food: {normalized_name}")
        return schemas.DetectResponse(
            name=name,
            product_found=True,
            details=schemas.ProductResponse(**cached_data)
        )
    
    logger.info(f"Cache MISS for food: {normalized_name}. Checking PostgreSQL...")

    # 2. Check Database
    product = db.query(models.Product).filter(models.Product.name == normalized_name).first()
    
    if product:
        logger.info(f"Database HIT for food: {normalized_name}")
        product_schema = schemas.ProductResponse.model_validate(product)
        set_cache(cache_key, product_schema.model_dump())
        return schemas.DetectResponse(
            name=name,
            product_found=True,
            details=product_schema
        )
    
    # 3. Database MISS: Trigger Search Agent Fallback
    logger.info(f"Database MISS for food: {normalized_name}. Triggering search agent fallback...")
    try:
        from ..search_agent import query_nutrition_for_food
        details = query_nutrition_for_food(name)
        product = save_new_food_to_db_and_cache(normalized_name, details, db)
        product_schema = schemas.ProductResponse.model_validate(product)
        return schemas.DetectResponse(
            name=name,
            product_found=True,
            details=product_schema
        )
    except Exception as e:
        logger.error(f"Failed to query nutrition via search agent: {e}")
        return schemas.DetectResponse(
            name=name,
            product_found=False,
            details=None
        )

@router.post("/image", response_model=schemas.DetectResponse)
def detect_food_from_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        # 1. Read file bytes
        image_bytes = file.file.read()
        
        # 2. Extract image embedding vector
        image_vector = None
        try:
            image_vector = extract_image_vector(image_bytes)
        except Exception as embed_err:
            logger.warning(f"[Embedding] Failed to extract image vector: {embed_err}")

        # 3. Check Vector DB Cache (Visual Similarity Search)
        if image_vector is not None:
            vector_match = find_similar_food_by_vector(image_vector, db, similarity_threshold=0.85)
            if vector_match:
                product, sim = vector_match
                logger.info(f"🎯 [Vector Cache HIT] Matched '{product.name}' with similarity {sim:.4f} - Skipping VLM!")
                product_schema = schemas.ProductResponse.model_validate(product)
                return schemas.DetectResponse(
                    name=product.name,
                    product_found=True,
                    details=product_schema
                )

        logger.info("[Vector Cache MISS] Image not found in vector database. Calling VLM...")
        
        # 4. Fallback to VLM to identify food name
        from ..vlm import identify_food_from_image
        identified_name = identify_food_from_image(image_bytes)
        normalized_name = identified_name.strip().lower()
        
        # 5. Check if food details exist in DB/Redis
        product = db.query(models.Product).filter(models.Product.name == normalized_name).first()
        
        if not product:
            logger.info(f"Database MISS for VLM-identified food: {normalized_name}. Triggering search agent...")
            from ..search_agent import query_nutrition_for_food
            details = query_nutrition_for_food(identified_name)
            product = save_new_food_to_db_and_cache(normalized_name, details, db)
        else:
            logger.info(f"Database HIT for VLM-identified food: {normalized_name}")

        # 6. Save this new image vector to Vector DB so future scans HIT the cache!
        if image_vector is not None and product:
            save_food_vector(product_id=product.id, vector=image_vector, source="vlm_cache", db=db)

        product_schema = schemas.ProductResponse.model_validate(product)
        return schemas.DetectResponse(
            name=identified_name,
            product_found=True,
            details=product_schema
        )

    except Exception as e:
        logger.error(f"Error in detect_food_from_image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process image: {str(e)}"
        )
