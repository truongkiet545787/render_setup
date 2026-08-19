import os
import glob
import io
import yaml
import argparse
import psycopg2
from psycopg2.extras import execute_values
from pgvector.psycopg2 import register_vector
from PIL import Image
from tqdm import tqdm
from fastembed import ImageEmbedding
from dotenv import load_dotenv

# Load .env file
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("[Error] DATABASE_URL not found in .env. Please set DATABASE_URL first.")
    exit(1)

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def load_classes_from_yaml(yaml_path: str) -> dict:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    names = data.get("names", {})
    # If list
    if isinstance(names, list):
        return {i: name for i, name in enumerate(names)}
    # If dict
    return {int(k): v for k, v in names.items()}

def get_product_map(cur) -> dict:
    """Preload all product names to product_ids from database."""
    cur.execute("SELECT id, name FROM products;")
    rows = cur.fetchall()
    return {name.strip().lower(): p_id for p_id, name in rows}

def ensure_product(cur, product_name: str, product_map: dict) -> int:
    name_clean = product_name.strip().lower()
    if name_clean in product_map:
        return product_map[name_clean]
    
    cur.execute("INSERT INTO products (name) VALUES (%s) RETURNING id;", (name_clean,))
    p_id = cur.fetchone()[0]
    
    # Create empty nutrition row
    cur.execute(
        "INSERT INTO nutrition (product_id, calories, protein, fat, carbohydrate) VALUES (%s, 0, 0, 0, 0);",
        (p_id,)
    )
    product_map[name_clean] = p_id
    return p_id

def process_dataset(dataset_dir: str, yaml_path: str, batch_size: int = 64, max_images: int = 0):
    class_map = load_classes_from_yaml(yaml_path)
    print(f"[Info] Loaded {len(class_map)} classes from {yaml_path}")

    # Connect to Supabase
    print("[Info] Connecting to Supabase...")
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    cur = conn.cursor()

    product_map = get_product_map(cur)
    print(f"[Info] Found {len(product_map)} existing products in Supabase.")

    # Initialize FastEmbed Vision model
    print("[Info] Loading FastEmbed Vision model (Qdrant/clip-ViT-B-32-vision)...")
    model = ImageEmbedding(model_name="Qdrant/clip-ViT-B-32-vision")

    # Find image files
    print(f"[Info] Scanning image files in {dataset_dir}...")
    image_paths = []
    for ext in ["*.jpg", "*.jpeg", "*.png", "*.webp"]:
        image_paths.extend(glob.glob(os.path.join(dataset_dir, "**", ext), recursive=True))

    if max_images > 0:
        image_paths = image_paths[:max_images]

    print(f"[Info] Processing {len(image_paths)} images...")

    batch_crops = []
    batch_metadata = [] # (product_id, source)
    total_vectors_inserted = 0

    def flush_batch():
        nonlocal total_vectors_inserted
        if not batch_crops:
            return
        
        # FastEmbed onnx embed batch
        embeddings = list(model.embed(batch_crops))
        
        # Prepare records for execute_values
        records = []
        for vec, (p_id, src) in zip(embeddings, batch_metadata):
            records.append((p_id, vec.tolist(), src))
        
        insert_query = """
        INSERT INTO food_embeddings (product_id, embedding, source)
        VALUES %s;
        """
        execute_values(cur, insert_query, records, template="(%s, %s, %s)")
        conn.commit()
        total_vectors_inserted += len(records)
        
        # Clear batch
        batch_crops.clear()
        batch_metadata.clear()

    for img_path in tqdm(image_paths, desc="Cropping & Embedding"):
        try:
            # Corresponding label file
            txt_path = img_path.replace("/images/", "/labels/").replace("\\images\\", "\\labels\\")
            base, _ = os.path.splitext(txt_path)
            label_file = base + ".txt"

            img = Image.open(img_path).convert("RGB")
            width, height = img.size

            crops_in_image = 0
            if os.path.exists(label_file):
                with open(label_file, "r") as lf:
                    lines = lf.readlines()
                for line in lines:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        cls_idx = int(parts[0])
                        cls_name = class_map.get(cls_idx, f"class_{cls_idx}")
                        x_c, y_c, w, h = map(float, parts[1:5])
                        
                        xmin = max(0, int((x_c - w / 2) * width))
                        ymin = max(0, int((y_c - h / 2) * height))
                        xmax = min(width, int((x_c + w / 2) * width))
                        ymax = min(height, int((y_c + h / 2) * height))

                        if (xmax - xmin) >= 15 and (ymax - ymin) >= 15:
                            cropped = img.crop((xmin, ymin, xmax, ymax))
                            buf = io.BytesIO()
                            cropped.save(buf, format="JPEG")
                            buf.seek(0)
                            
                            p_id = ensure_product(cur, cls_name, product_map)
                            batch_crops.append(buf)
                            batch_metadata.append((p_id, "dataset_crop"))
                            crops_in_image += 1

            # If no bbox or empty label file, embed whole image
            if crops_in_image == 0:
                parent_dir = os.path.basename(os.path.dirname(img_path))
                buf = io.BytesIO()
                img.save(buf, format="JPEG")
                buf.seek(0)
                p_id = ensure_product(cur, parent_dir, product_map)
                batch_crops.append(buf)
                batch_metadata.append((p_id, "dataset_full"))

            if len(batch_crops) >= batch_size:
                flush_batch()

        except Exception as e:
            continue

    # Final flush
    flush_batch()

    cur.close()
    conn.close()
    print(f"\n🎉 HOÀN THÀNH: Đã trích xuất và lưu thành công {total_vectors_inserted} vector embeddings vào Supabase!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset_dir", type=str, default="c:/Users/nhung/planetAR/dataset/dataset/train/images")
    parser.add_argument("--yaml_path", type=str, default="c:/Users/nhung/planetAR/dataset/dataset/dataset.yaml")
    parser.add_argument("--batch_size", type=int, default=64)
    parser.add_argument("--max_images", type=int, default=0)
    args = parser.parse_args()

    process_dataset(args.dataset_dir, args.yaml_path, args.batch_size, args.max_images)
