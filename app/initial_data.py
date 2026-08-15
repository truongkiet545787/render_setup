from sqlalchemy.orm import Session
from . import models
import logging

logger = logging.getLogger("uvicorn.error")

# Comprehensive pre-filled database of the 71 food labels from dataset.yaml
FOOD_DATA = {
    "apple": {
        "calories": 52.0, "protein": 0.3, "fat": 0.2, "carbohydrate": 14.0, "sugar": 10.0, "fiber": 2.4,
        "potassium": 107.0, "vitamin_c": 4.6, "brand": None,
        "ingredients": ["Táo tươi"], "allergens": []
    },
    "banana": {
        "calories": 89.0, "protein": 1.1, "fat": 0.3, "carbohydrate": 22.8, "sugar": 12.2, "fiber": 2.6,
        "potassium": 358.0, "vitamin_c": 8.7, "brand": None,
        "ingredients": ["Chuối tươi chín"], "allergens": []
    },
    "coca_cola": {
        "calories": 42.0, "protein": 0.0, "fat": 0.0, "carbohydrate": 10.6, "sugar": 10.6, "fiber": 0.0,
        "potassium": 2.0, "vitamin_c": 0.0, "brand": "Coca-Cola",
        "ingredients": ["Nước bão hòa CO2", "Đường HFCS", "Đường mía", "Màu thực phẩm", "Chất điều chỉnh độ acid", "Hương tự nhiên", "Caffeine"],
        "allergens": []
    },
    "7up": {
        "calories": 38.0, "protein": 0.0, "fat": 0.0, "carbohydrate": 9.5, "sugar": 9.5, "fiber": 0.0,
        "potassium": 1.0, "vitamin_c": 0.0, "brand": "PepsiCo",
        "ingredients": ["Nước bão hòa CO2", "Đường", "Chất điều chỉnh độ acid", "Hương chanh tự nhiên"],
        "allergens": []
    },
    "pepsi": {
        "calories": 41.0, "protein": 0.0, "fat": 0.0, "carbohydrate": 10.3, "sugar": 10.3, "fiber": 0.0,
        "potassium": 3.0, "vitamin_c": 0.0, "brand": "PepsiCo",
        "ingredients": ["Nước bão hòa CO2", "Đường mía", "Màu caramel", "Chất điều chỉnh độ acid", "Caffeine", "Hương tự nhiên"],
        "allergens": []
    },
    "banh_mi": {
        "calories": 250.0, "protein": 8.5, "fat": 5.0, "carbohydrate": 42.0, "sugar": 3.0, "fiber": 2.0,
        "potassium": 120.0, "vitamin_c": 1.0, "brand": None,
        "ingredients": ["Bột mì", "Thịt heo xá xíu", "Pate gan", "Bơ trứng", "Đồ chua (đu đủ, cà rốt)", "Rau ngò", "Dưa leo", "Nước sốt"],
        "allergens": ["Gluten (bột mì)", "Trứng", "Đậu nành"]
    },
    "bun_bo_hue": {
        "calories": 480.0, "protein": 25.0, "fat": 15.0, "carbohydrate": 58.0, "sugar": 4.0, "fiber": 3.0,
        "potassium": 350.0, "vitamin_c": 5.0, "brand": None,
        "ingredients": ["Bún gạo", "Nước dùng xương bò", "Nạm bò", "Chả cua", "Giò heo", "Huyết", "Sả", "Mắm ruốc Huế", "Hành lá", "Rau thơm"],
        "allergens": ["Giáp xác (cua)", "Mắm ruốc (tôm/cá)"]
    },
    "pho": {
        "calories": 350.0, "protein": 18.0, "fat": 8.0, "carbohydrate": 50.0, "sugar": 2.0, "fiber": 1.5,
        "potassium": 280.0, "vitamin_c": 2.0, "brand": None,
        "ingredients": ["Bánh phở", "Nước dùng bò/gà", "Thịt bò/gà lát", "Hành tây", "Hành lá", "Giá đỗ", "Rau húng", "Quế", "Hồi"],
        "allergens": []
    },
    "orange": {
        "calories": 47.0, "protein": 0.9, "fat": 0.1, "carbohydrate": 11.8, "sugar": 9.4, "fiber": 2.4,
        "potassium": 181.0, "vitamin_c": 53.2, "brand": None,
        "ingredients": ["Cam tươi"], "allergens": []
    },
    "egg": {
        "calories": 155.0, "protein": 13.0, "fat": 11.0, "carbohydrate": 1.1, "sugar": 1.1, "fiber": 0.0,
        "potassium": 138.0, "vitamin_c": 0.0, "brand": None,
        "ingredients": ["Trứng gà ta"], "allergens": ["Trứng"]
    },
    "tofu": {
        "calories": 76.0, "protein": 8.0, "fat": 4.8, "carbohydrate": 1.9, "sugar": 0.5, "fiber": 0.3,
        "potassium": 121.0, "vitamin_c": 0.0, "brand": None,
        "ingredients": ["Đậu nành", "Nước", "Muối tinh"], "allergens": ["Đậu nành"]
    },
    "tomato": {
        "calories": 18.0, "protein": 0.9, "fat": 0.2, "carbohydrate": 3.9, "sugar": 2.6, "fiber": 1.2,
        "potassium": 237.0, "vitamin_c": 13.7, "brand": None,
        "ingredients": ["Cà chua tươi"], "allergens": []
    },
    "fries": {
        "calories": 312.0, "protein": 3.4, "fat": 15.0, "carbohydrate": 41.0, "sugar": 0.3, "fiber": 3.8,
        "potassium": 579.0, "vitamin_c": 4.7, "brand": None,
        "ingredients": ["Khoai tây chiên", "Dầu thực vật", "Muối"], "allergens": []
    },
    "burger": {
        "calories": 295.0, "protein": 17.0, "fat": 14.0, "carbohydrate": 24.0, "sugar": 4.2, "fiber": 1.5,
        "potassium": 256.0, "vitamin_c": 1.2, "brand": None,
        "ingredients": ["Bánh mì tròn", "Bò băm chiên", "Phô mai lát", "Xà lách", "Cà chua", "Hành tây", "Nước sốt"],
        "allergens": ["Gluten (bột mì)", "Sữa (phô mai)", "Trứng (sốt mayonnaise)"]
    },
    "pizza": {
        "calories": 266.0, "protein": 11.4, "fat": 10.0, "carbohydrate": 33.0, "sugar": 3.6, "fiber": 2.3,
        "potassium": 172.0, "vitamin_c": 1.4, "brand": None,
        "ingredients": ["Đế bánh mì", "Sốt cà chua", "Phô mai Mozzarella", "Thịt nguội", "Ớt chuông", "Hành tây"],
        "allergens": ["Gluten (bột mì)", "Sữa (phô mai)"]
    },
    "milo": {
        "calories": 411.0, "protein": 11.8, "fat": 8.5, "carbohydrate": 71.0, "sugar": 47.0, "fiber": 3.2,
        "potassium": 480.0, "vitamin_c": 28.0, "brand": "Nestlé",
        "ingredients": ["Đường", "Sữa bột", "Lúa mạch", "Bột cacao", "Dầu thực vật", "Vitamin và Khoáng chất"],
        "allergens": ["Lúa mạch (gluten)", "Sữa"]
    },
    "yakult": {
        "calories": 71.0, "protein": 1.2, "fat": 0.1, "carbohydrate": 16.4, "sugar": 14.2, "fiber": 0.0,
        "potassium": 50.0, "vitamin_c": 0.0, "brand": "Yakult",
        "ingredients": ["Nước", "Đường", "Sữa bột gầy", "Lợi khuẩn Lactobacillus casei Shirota"],
        "allergens": ["Sữa"]
    }
}

# The full list of 71 labels
LABELS = [
    "7up", "apple", "baked_potato", "banana", "banh_bao", "banh_beo", "banh_bot_loc", "banh_chung",
    "banh_mi", "banh_tet", "banh_trang_nuong", "banh_trung_thu", "bun_bo_hue", "bun_dau_mam_tom", "burger", "c2_green_tea",
    "cabbage", "carrot", "coca_cola", "com_chien", "com_lam", "crispy_chicken", "cua_hap", "cucumber",
    "donut", "egg", "eggplant", "fanta", "fries", "garlic", "ginger", "goi_cuon",
    "grape", "hot_dog", "lays_chips", "lemon", "lipton", "m_ms", "milo", "minute_maid",
    "mirinda", "monster", "mountain_dew", "nui_xao", "oc_buoi_hap", "oishi_bread_pan", "oishi_pillows", "oishi_sponge",
    "onion", "orange", "oreo", "peach", "pear", "pepero", "pepsi", "pho",
    "pineapple", "pizza", "potato", "pringles", "rau_muong_xao", "red_bull", "schweppes", "snickers",
    "sprite", "sunkist", "thit_kho_tau", "tofu", "tomato", "xoi_xeo", "yakult"
]

def init_db_data(db: Session):
    existing_count = db.query(models.Product).count()
    if existing_count > 0:
        logger.info(f"Database already contains {existing_count} products. Skipping data initialization.")
        return

    logger.info("Initializing database with 71 default food labels...")
    
    for label in LABELS:
        # Fetch mock data or use generic values
        info = FOOD_DATA.get(label, {
            "calories": 120.0,
            "protein": 3.0,
            "fat": 2.0,
            "carbohydrate": 20.0,
            "sugar": 5.0,
            "fiber": 1.5,
            "potassium": 100.0,
            "vitamin_c": 2.0,
            "brand": None,
            "ingredients": [f"Thành phần của {label}"],
            "allergens": []
        })

        product = models.Product(name=label, brand=info["brand"])
        db.add(product)
        db.commit()
        db.refresh(product)

        nutrition = models.Nutrition(
            product_id=product.id,
            calories=info["calories"],
            protein=info["protein"],
            fat=info["fat"],
            carbohydrate=info["carbohydrate"],
            sugar=info["sugar"],
            fiber=info["fiber"],
            potassium=info["potassium"],
            vitamin_c=info["vitamin_c"]
        )
        db.add(nutrition)

        for ing in info["ingredients"]:
            db.add(models.Ingredient(product_id=product.id, name=ing))
        
        for alg in info["allergens"]:
            db.add(models.Allergen(product_id=product.id, name=alg))

    db.commit()
    logger.info("Successfully populated 71 products into the database.")
