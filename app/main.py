from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import psycopg2
import time
import logging

from .database import Base, engine, SessionLocal
from .config import settings
from .routers import detect, chat
from .initial_data import init_db_data

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")

# 1. Database Connection and Auto-creation sequence
try:
    # If on local postgres with separate DB creation needed, attempt creation
    if settings.database_hostname and settings.database_password and not settings.database_url:
        try:
            conn = psycopg2.connect(
                host=settings.database_hostname, 
                database="postgres", 
                user=settings.database_username, 
                password=settings.database_password, 
                port=settings.database_port
            )
            conn.autocommit = True
            cursor = conn.cursor()
            cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{settings.database_name}';")
            exists = cursor.fetchone()
            if not exists:
                logger.info(f"Database '{settings.database_name}' not found. Creating database...")
                cursor.execute(f"CREATE DATABASE {settings.database_name};")
                logger.info(f"Database '{settings.database_name}' created successfully.")
            cursor.close()
            conn.close()
        except Exception as e:
            logger.info(f"Database pre-check notice (safe to continue): {e}")

    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")

    # Populate initial food data (71 labels)
    db = SessionLocal()
    try:
        init_db_data(db)
    finally:
        db.close()
except Exception as error:
    logger.error(f"Database setup error: {error}")

# 2. Initialize FastAPI App
app = FastAPI(
    title="AI Nutrition AR Agent Backend",
    description="FastAPI Backend for detecting food items and discussing nutrition details using LangChain.",
    version="1.0.0"
)

# 3. Setup CORS Middleware
origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 4. Include Routers
app.include_router(detect.router)
app.include_router(chat.router)

# 5. Root endpoint
@app.get("/")
def read_root():
    return {
        "status": "online",
        "project": "AI Nutrition AR Agent",
        "message": "Welcome! Use /detect to query food or /chat to chat with AI."
    }
