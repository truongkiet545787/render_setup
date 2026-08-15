from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    barcode = Column(String, unique=True, index=True, nullable=True)
    name = Column(String, unique=True, index=True, nullable=False)
    brand = Column(String, nullable=True)

    nutrition = relationship("Nutrition", back_populates="product", uselist=False, cascade="all, delete-orphan")
    ingredients = relationship("Ingredient", back_populates="product", cascade="all, delete-orphan")
    allergens = relationship("Allergen", back_populates="product", cascade="all, delete-orphan")

class Nutrition(Base):
    __tablename__ = 'nutrition'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    calories = Column(Float, nullable=False, default=0.0)
    protein = Column(Float, nullable=False, default=0.0)
    fat = Column(Float, nullable=False, default=0.0)
    carbohydrate = Column(Float, nullable=False, default=0.0)
    sugar = Column(Float, nullable=False, default=0.0)
    fiber = Column(Float, nullable=False, default=0.0)
    potassium = Column(Float, nullable=False, default=0.0)
    vitamin_c = Column(Float, nullable=False, default=0.0)

    product = relationship("Product", back_populates="nutrition")

class Ingredient(Base):
    __tablename__ = 'ingredients'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)

    product = relationship("Product", back_populates="ingredients")

class Allergen(Base):
    __tablename__ = 'allergens'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)

    product = relationship("Product", back_populates="allergens")

class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    role = Column(String, nullable=False) # 'user' or 'assistant'
    content = Column(Text, nullable=False)
    time_created = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

class MealHistory(Base):
    __tablename__ = 'meal_history'
    id = Column(Integer, primary_key=True, nullable=False, autoincrement=True)
    product_name = Column(String, nullable=False)
    calories = Column(Float, nullable=False, default=0.0)
    portion_size = Column(Float, nullable=False, default=100.0) # in grams
    time_created = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
