-- =======================================================
-- SUPABASE / POSTGRESQL INITIALIZATION SCRIPT FOR PLANETAR
-- Copy and paste this script into Supabase -> SQL Editor -> Run
-- =======================================================

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Create products table
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    barcode VARCHAR(255) UNIQUE,
    name VARCHAR(255) UNIQUE NOT NULL,
    brand VARCHAR(255)
);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);

-- 3. Create nutrition table
CREATE TABLE IF NOT EXISTS nutrition (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    calories FLOAT NOT NULL DEFAULT 0.0,
    protein FLOAT NOT NULL DEFAULT 0.0,
    fat FLOAT NOT NULL DEFAULT 0.0,
    carbohydrate FLOAT NOT NULL DEFAULT 0.0,
    sugar FLOAT NOT NULL DEFAULT 0.0,
    fiber FLOAT NOT NULL DEFAULT 0.0,
    potassium FLOAT NOT NULL DEFAULT 0.0,
    vitamin_c FLOAT NOT NULL DEFAULT 0.0
);

-- 4. Create ingredients table
CREATE TABLE IF NOT EXISTS ingredients (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL
);

-- 5. Create allergens table
CREATE TABLE IF NOT EXISTS allergens (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL
);

-- 6. Create food_embeddings table for Visual Vector Cache (512 dimensions for CLIP ViT-B/32)
CREATE TABLE IF NOT EXISTS food_embeddings (
    id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    embedding vector(512) NOT NULL,
    source VARCHAR(50) DEFAULT 'vlm_cache',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);

-- 7. Create HNSW or IVFFlat Index for sub-millisecond vector similarity search
CREATE INDEX IF NOT EXISTS idx_food_embeddings_vector 
ON food_embeddings USING hnsw (embedding vector_cosine_ops);

-- 8. Create chat messages and meal history tables
CREATE TABLE IF NOT EXISTS chat_messages (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL,
    content TEXT NOT NULL,
    time_created TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);

CREATE TABLE IF NOT EXISTS meal_history (
    id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    calories FLOAT NOT NULL DEFAULT 0.0,
    portion_size FLOAT NOT NULL DEFAULT 100.0,
    time_created TIMESTAMP WITH TIME ZONE DEFAULT timezone('utc'::text, now())
);
