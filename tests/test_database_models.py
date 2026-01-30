"""Tests for database_models.py - model relationships and constraints."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from database_models import (
    Base, ReferenceMonth, Brand, CarModel, ModelYear, CarPrice, create_database
)
from datetime import date


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCreateDatabase:
    """Tests for create_database function."""

    def test_creates_engine_and_session(self):
        """Should return engine and Session factory."""
        engine, Session = create_database("sqlite:///:memory:")

        assert engine is not None
        assert Session is not None

        # Session should be callable
        session = Session()
        assert session is not None
        session.close()

    def test_creates_all_tables(self):
        """Should create all 5 tables."""
        engine, Session = create_database("sqlite:///:memory:")

        table_names = set(Base.metadata.tables.keys())
        expected_tables = {
            'reference_months', 'brands', 'car_models', 'model_years', 'car_prices'
        }

        assert expected_tables == table_names


class TestReferenceMonth:
    """Tests for ReferenceMonth model."""

    def test_create_reference_month(self, db_session):
        """Should create a reference month record."""
        month = ReferenceMonth(
            month_code="312",
            month_date=date(2024, 12, 1)
        )
        db_session.add(month)
        db_session.commit()

        assert month.id is not None
        assert month.month_code == "312"
        assert month.month_date == date(2024, 12, 1)

    def test_month_code_unique_constraint(self, db_session):
        """Should enforce unique month_code."""
        month1 = ReferenceMonth(month_code="312", month_date=date(2024, 12, 1))
        month2 = ReferenceMonth(month_code="312", month_date=date(2024, 11, 1))

        db_session.add(month1)
        db_session.commit()

        db_session.add(month2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_repr(self, db_session):
        """__repr__ should include month_code and month_date."""
        month = ReferenceMonth(month_code="312", month_date=date(2024, 12, 1))
        db_session.add(month)
        db_session.commit()

        repr_str = repr(month)
        assert "312" in repr_str
        assert "2024-12-01" in repr_str


class TestBrand:
    """Tests for Brand model."""

    def test_create_brand(self, db_session):
        """Should create a brand record."""
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add(brand)
        db_session.commit()

        assert brand.id is not None
        assert brand.brand_code == "59"
        assert brand.brand_name == "Volkswagen"

    def test_brand_code_unique_constraint(self, db_session):
        """Should enforce unique brand_code."""
        brand1 = Brand(brand_code="59", brand_name="Volkswagen")
        brand2 = Brand(brand_code="59", brand_name="VW")

        db_session.add(brand1)
        db_session.commit()

        db_session.add(brand2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_brand_has_models_relationship(self, db_session):
        """Brand should have models relationship."""
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add(brand)
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        assert len(brand.models) == 1
        assert brand.models[0].model_name == "Gol"


class TestCarModel:
    """Tests for CarModel model."""

    def test_create_car_model(self, db_session):
        """Should create a car model linked to brand."""
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add(brand)
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol 1.0")
        db_session.add(model)
        db_session.commit()

        assert model.id is not None
        assert model.brand_id == brand.id
        assert model.model_name == "Gol 1.0"

    def test_brand_model_unique_constraint(self, db_session):
        """Should enforce unique (brand_id, model_code) combination."""
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add(brand)
        db_session.commit()

        model1 = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        model2 = CarModel(brand_id=brand.id, model_code="123", model_name="Gol 1.0")

        db_session.add(model1)
        db_session.commit()

        db_session.add(model2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_model_brand_relationship(self, db_session):
        """CarModel should access brand via relationship."""
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add(brand)
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        assert model.brand.brand_name == "Volkswagen"


class TestModelYear:
    """Tests for ModelYear model."""

    def test_create_model_year(self, db_session):
        """Should create a model year linked to car model."""
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add(brand)
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        year = ModelYear(
            car_model_id=model.id,
            year_code="2024-1",
            year_description="2024 Gasolina"
        )
        db_session.add(year)
        db_session.commit()

        assert year.id is not None
        assert year.year_description == "2024 Gasolina"

    def test_model_year_unique_constraint(self, db_session):
        """Should enforce unique (car_model_id, year_code) combination."""
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add(brand)
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        year1 = ModelYear(car_model_id=model.id, year_code="2024-1", year_description="2024 Gas")
        year2 = ModelYear(car_model_id=model.id, year_code="2024-1", year_description="2024 Gasolina")

        db_session.add(year1)
        db_session.commit()

        db_session.add(year2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestCarPrice:
    """Tests for CarPrice model."""

    def test_create_car_price(self, db_session):
        """Should create a price record linking month and model year."""
        # Create all required parent records
        month = ReferenceMonth(month_code="312", month_date=date(2024, 12, 1))
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add_all([month, brand])
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        year = ModelYear(car_model_id=model.id, year_code="2024-1", year_description="2024 Gas")
        db_session.add(year)
        db_session.commit()

        price = CarPrice(
            reference_month_id=month.id,
            model_year_id=year.id,
            price=45000.00,
            fipe_code="001234-5",
            fuel_type="Gasolina"
        )
        db_session.add(price)
        db_session.commit()

        assert price.id is not None
        assert price.price == 45000.00
        assert price.fipe_code == "001234-5"

    def test_price_unique_constraint(self, db_session):
        """Should enforce unique (reference_month_id, model_year_id) combination."""
        month = ReferenceMonth(month_code="312", month_date=date(2024, 12, 1))
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add_all([month, brand])
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        year = ModelYear(car_model_id=model.id, year_code="2024-1", year_description="2024 Gas")
        db_session.add(year)
        db_session.commit()

        price1 = CarPrice(reference_month_id=month.id, model_year_id=year.id, price=45000.00)
        price2 = CarPrice(reference_month_id=month.id, model_year_id=year.id, price=46000.00)

        db_session.add(price1)
        db_session.commit()

        db_session.add(price2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_price_relationships(self, db_session):
        """Price should access month and model_year via relationships."""
        month = ReferenceMonth(month_code="312", month_date=date(2024, 12, 1))
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add_all([month, brand])
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        year = ModelYear(car_model_id=model.id, year_code="2024-1", year_description="2024 Gas")
        db_session.add(year)
        db_session.commit()

        price = CarPrice(reference_month_id=month.id, model_year_id=year.id, price=45000.00)
        db_session.add(price)
        db_session.commit()

        # Navigate relationships
        assert price.reference_month.month_code == "312"
        assert price.model_year.year_description == "2024 Gas"
        assert price.model_year.car_model.model_name == "Gol"
        assert price.model_year.car_model.brand.brand_name == "Volkswagen"


class TestModelRelationshipChain:
    """Tests for the full relationship chain: Brand -> Model -> Year -> Price."""

    def test_full_relationship_chain(self, db_session):
        """Should be able to traverse from Brand down to Prices."""
        # Create full hierarchy
        month = ReferenceMonth(month_code="312", month_date=date(2024, 12, 1))
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add_all([month, brand])
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        year = ModelYear(car_model_id=model.id, year_code="2024-1", year_description="2024 Gas")
        db_session.add(year)
        db_session.commit()

        price = CarPrice(reference_month_id=month.id, model_year_id=year.id, price=45000.00)
        db_session.add(price)
        db_session.commit()

        # Traverse from brand to price
        brand_model = brand.models[0]
        model_year = brand_model.years[0]
        year_price = model_year.prices[0]

        assert year_price.price == 45000.00

    def test_reference_month_has_prices(self, db_session):
        """ReferenceMonth should access prices via relationship."""
        month = ReferenceMonth(month_code="312", month_date=date(2024, 12, 1))
        brand = Brand(brand_code="59", brand_name="Volkswagen")
        db_session.add_all([month, brand])
        db_session.commit()

        model = CarModel(brand_id=brand.id, model_code="123", model_name="Gol")
        db_session.add(model)
        db_session.commit()

        year = ModelYear(car_model_id=model.id, year_code="2024-1", year_description="2024 Gas")
        db_session.add(year)
        db_session.commit()

        price = CarPrice(reference_month_id=month.id, model_year_id=year.id, price=45000.00)
        db_session.add(price)
        db_session.commit()

        assert len(month.prices) == 1
        assert month.prices[0].price == 45000.00
