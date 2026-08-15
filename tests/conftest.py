from fastapi.testclient import TestClient
from app.main import app
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import get_db, Base
from app.config import settings
import pytest
import psycopg2

# Disable Redis caching for all pytest tests to ensure isolation
from app import redis as app_redis
app_redis.redis_enabled = False

# Dynamically construct test database name based on settings
TEST_DB_NAME = f"{settings.database_name}_test"
SQLALCHEMY_DATABASE_URL = f"postgresql://{settings.database_username}:{settings.database_password}@{settings.database_hostname}:{settings.database_port}/{TEST_DB_NAME}"

# Setup test database creation helper
@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    try:
        # Connect to default postgres to create test db if it doesn't exist
        conn = psycopg2.connect(
            host=settings.database_hostname,
            database="postgres",
            user=settings.database_username,
            password=settings.database_password,
            port=settings.database_port
        )
        conn.autocommit = True
        cursor = conn.cursor()
        cursor.execute(f"SELECT 1 FROM pg_catalog.pg_database WHERE datname = '{TEST_DB_NAME}';")
        exists = cursor.fetchone()
        if not exists:
            cursor.execute(f"CREATE DATABASE {TEST_DB_NAME};")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Warning: Could not create test database automatically: {e}")
    yield

engine = create_engine(SQLALCHEMY_DATABASE_URL)
Testing_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def session():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = Testing_SessionLocal()
    
    # Pre-populate test database with 71 items for routing tests
    from app.initial_data import init_db_data
    init_db_data(db)
    
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(session):
    def override_get_db():
        try:
            yield session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()
