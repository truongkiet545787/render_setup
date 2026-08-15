import sys
import os
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logging.basicConfig(level=logging.INFO)
sys.stdout.reconfigure(encoding='utf-8')

from backend.app.vlm import identify_food_from_image

def main():
    print("=== Testing VLM ONLY ===")
    test_image_path = "vietnamese_food_test.jpg"
    if os.path.exists(test_image_path):
        print(f"Reading test image '{test_image_path}'...")
        with open(test_image_path, "rb") as f:
            image_bytes = f.read()
        try:
            food_id = identify_food_from_image(image_bytes)
            print(f"VLM identified food: '{food_id}'")
        except Exception as e:
            print(f"VLM failed: {e}")
    else:
        print(f"Test image '{test_image_path}' not found.")

if __name__ == "__main__":
    main()
