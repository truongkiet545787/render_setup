import sys
import os

# Add the parent directory to Python path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import logging
logging.basicConfig(level=logging.INFO)


from backend.app.search_agent import query_nutrition_for_food
from backend.app.vlm import identify_food_from_image

import sys
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

def main():

    print("=== Testing Search Agent Fallback ===")
    food_name = "bún chả"
    print(f"Querying nutrition details for '{food_name}'...")
    result = query_nutrition_for_food(food_name)
    print("Result JSON:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))

    print("\n=== Testing VLM Identification (if keys configured) ===")
    test_image_path = "vietnamese_food_test.jpg"
    if os.path.exists(test_image_path):
        print(f"Reading test image '{test_image_path}'...")
        with open(test_image_path, "rb") as f:
            image_bytes = f.read()
        try:
            food_id = identify_food_from_image(image_bytes)
            print(f"VLM identified food: '{food_id}'")
        except Exception as e:
            print(f"VLM failed (expected if keys are missing/invalid): {e}")
    else:
        print(f"Test image '{test_image_path}' not found at root directory.")

if __name__ == "__main__":
    main()
