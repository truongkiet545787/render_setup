from pydantic import BaseModel
from typing import Optional, List
import datetime

class NutritionResponse(BaseModel):
    calories: float
    protein: float
    fat: float
    carbohydrate: float
    sugar: float
    fiber: float
    potassium: float
    vitamin_c: float

    class Config:
        from_attributes = True

class IngredientResponse(BaseModel):
    name: str

    class Config:
        from_attributes = True

class AllergenResponse(BaseModel):
    name: str

    class Config:
        from_attributes = True

class ProductResponse(BaseModel):
    id: int
    barcode: Optional[str] = None
    name: str
    brand: Optional[str] = None
    nutrition: Optional[NutritionResponse] = None
    ingredients: List[IngredientResponse] = []
    allergens: List[AllergenResponse] = []

    class Config:
        from_attributes = True

class DetectRequest(BaseModel):
    name: str

class DetectResponse(BaseModel):
    name: str
    product_found: bool
    source: Optional[str] = "database" # "vector_cache", "vlm_matched", "vlm_new", "database"
    confidence: Optional[float] = 1.0
    image_vector: Optional[List[float]] = None
    details: Optional[ProductResponse] = None

class ConfirmDetectRequest(BaseModel):
    product_name: str
    is_correct: bool
    corrected_name: Optional[str] = None
    image_vector: Optional[List[float]] = None

class ChatRequest(BaseModel):
    session_id: str
    message: str
    product_name: Optional[str] = None

class ChatMessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    time_created: datetime.datetime

    class Config:
        from_attributes = True

class ChatResponse(BaseModel):
    reply: str
    history: List[ChatMessageResponse] = []

class MealHistoryCreate(BaseModel):
    product_name: str
    calories: float
    portion_size: float

class MealHistoryResponse(BaseModel):
    id: int
    product_name: str
    calories: float
    portion_size: float
    time_created: datetime.datetime

    class Config:
        from_attributes = True
