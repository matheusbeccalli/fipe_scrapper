"""
Database models for FIPE car price scraper

This file defines the database structure using SQLAlchemy ORM.
We use multiple tables to normalize the data and avoid redundancy.
"""

from sqlalchemy import create_engine, Column, Integer, String, Float, Date, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()


class ReferenceMonth(Base):
    """
    Stores the reference months available in FIPE table.
    Each month represents a data collection period.
    
    Example: "dezembro/2024" with code "312"
    """
    __tablename__ = 'reference_months'
    
    id = Column(Integer, primary_key=True)
    month_code = Column(String(50), unique=True, nullable=False)  # e.g., "312"
    month_name = Column(String(50), nullable=False)  # e.g., "dezembro/2024"
    created_at = Column(Date, default=datetime.now)
    
    # Relationship to prices
    prices = relationship("CarPrice", back_populates="reference_month")
    
    def __repr__(self):
        return f"<ReferenceMonth(month_name='{self.month_name}')>"


class Brand(Base):
    """
    Stores car brands (manufacturers).
    
    Example: "Volkswagen", "Fiat", "Chevrolet"
    """
    __tablename__ = 'brands'
    
    id = Column(Integer, primary_key=True)
    brand_code = Column(String(50), unique=True, nullable=False)  # FIPE's internal code
    brand_name = Column(String(100), nullable=False)  # Brand name
    created_at = Column(Date, default=datetime.now)
    
    # Relationship to models
    models = relationship("CarModel", back_populates="brand")
    
    def __repr__(self):
        return f"<Brand(brand_name='{self.brand_name}')>"


class CarModel(Base):
    """
    Stores car models within each brand.
    
    Example: "Gol 1.0", "Onix LT 1.0", "Civic EX 2.0"
    """
    __tablename__ = 'car_models'
    
    id = Column(Integer, primary_key=True)
    brand_id = Column(Integer, ForeignKey('brands.id'), nullable=False)
    model_code = Column(String(50), nullable=False)  # FIPE's internal code
    model_name = Column(String(200), nullable=False)  # Model name
    created_at = Column(Date, default=datetime.now)
    
    # Ensure unique combination of brand and model code
    __table_args__ = (UniqueConstraint('brand_id', 'model_code', name='_brand_model_uc'),)
    
    # Relationships
    brand = relationship("Brand", back_populates="models")
    years = relationship("ModelYear", back_populates="car_model")
    
    def __repr__(self):
        return f"<CarModel(model_name='{self.model_name}')>"


class ModelYear(Base):
    """
    Stores the different years available for each car model.
    
    Example: "2024 Gasolina", "2023 Flex", "2022 Diesel"
    Note: Brazilian cars often have fuel type in the year description
    """
    __tablename__ = 'model_years'
    
    id = Column(Integer, primary_key=True)
    car_model_id = Column(Integer, ForeignKey('car_models.id'), nullable=False)
    year_code = Column(String(50), nullable=False)  # FIPE's internal code
    year_description = Column(String(100), nullable=False)  # e.g., "2024 Gasolina"
    created_at = Column(Date, default=datetime.now)
    
    # Ensure unique combination of model and year code
    __table_args__ = (UniqueConstraint('car_model_id', 'year_code', name='_model_year_uc'),)
    
    # Relationships
    car_model = relationship("CarModel", back_populates="years")
    prices = relationship("CarPrice", back_populates="model_year")
    
    def __repr__(self):
        return f"<ModelYear(year_description='{self.year_description}')>"


class CarPrice(Base):
    """
    Stores the actual price data for each combination of:
    - Reference month
    - Model year (which links to model -> brand)
    
    This is the main table with the actual scraped price data.
    """
    __tablename__ = 'car_prices'
    
    id = Column(Integer, primary_key=True)
    reference_month_id = Column(Integer, ForeignKey('reference_months.id'), nullable=False)
    model_year_id = Column(Integer, ForeignKey('model_years.id'), nullable=False)
    
    # Price information
    price = Column(Float, nullable=False)  # Price in BRL (Brazilian Real)
    fipe_code = Column(String(50))  # FIPE code for this specific vehicle
    
    # Additional information that might be available
    vehicle_type = Column(String(50))  # e.g., "Carro", "Utilitário"
    fuel_type = Column(String(50))  # e.g., "Gasolina", "Flex", "Diesel"
    
    # Metadata
    scraped_at = Column(Date, default=datetime.now)
    
    # Ensure we don't duplicate price entries
    __table_args__ = (UniqueConstraint('reference_month_id', 'model_year_id', name='_month_year_uc'),)
    
    # Relationships
    reference_month = relationship("ReferenceMonth", back_populates="prices")
    model_year = relationship("ModelYear", back_populates="prices")
    
    def __repr__(self):
        return f"<CarPrice(price={self.price}, fipe_code='{self.fipe_code}')>"


def create_database(database_url='sqlite:///fipe_data.db'):
    """
    Creates the database and all tables.
    
    Args:
        database_url: SQLAlchemy database URL. Default is SQLite.
                     For PostgreSQL: 'postgresql://user:password@localhost/dbname'
                     For MySQL: 'mysql+pymysql://user:password@localhost/dbname'
    
    Returns:
        engine: SQLAlchemy engine object
        Session: SQLAlchemy Session class
    """
    engine = create_engine(database_url, echo=True)  # echo=True shows SQL queries
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


if __name__ == "__main__":
    # Create the database when this file is run directly
    print("Creating database...")
    engine, Session = create_database()
    print("Database created successfully!")
    print(f"Tables created: {Base.metadata.tables.keys()}")
