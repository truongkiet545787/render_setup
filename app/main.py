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

# 1. Database Table Creation and Initial Data Population
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully.")

    db = SessionLocal()
    try:
        init_db_data(db)
    finally:
        db.close()

    # Preload FastEmbed ONNX Image model
    try:
        from .embedding import get_image_embedding_model
        get_image_embedding_model()
    except Exception as em_err:
        logger.warning(f"FastEmbed initial load warning: {em_err}")
except Exception as error:
    logger.error(f"Database initialization error: {error}")

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
