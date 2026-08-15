from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from .config import settings

import logging

logger = logging.getLogger("uvicorn.error")

engine = None

if settings.database_url:
    db_url = settings.database_url
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    try:
        temp_engine = create_engine(db_url)
        with temp_engine.connect() as conn:
            pass
        engine = temp_engine
        logger.info("[Database] Connected to PostgreSQL via DATABASE_URL.")
    except Exception as e:
        logger.warning(f"[Database] Failed to connect to DATABASE_URL: {e}. Falling back to SQLite.")

if engine is None and settings.database_hostname and settings.database_password:
    try:
        SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.database_username or 'postgres'}:{settings.database_password}@{settings.database_hostname}:{settings.database_port or '5432'}/{settings.database_name or 'postgres'}"
        temp_engine = create_engine(SQLALCHEMY_DATABASE_URL)
        with temp_engine.connect() as conn:
            pass
        engine = temp_engine
        logger.info("[Database] Connected to local PostgreSQL.")
    except Exception as e:
        logger.warning(f"[Database] Failed to connect to PostgreSQL: {e}. Falling back to SQLite.")

if engine is None:
    logger.info("[Database] Initializing SQLite database (nutrition.db)...")
    engine = create_engine("sqlite:///./nutrition.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
