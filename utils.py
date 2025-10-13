"""
Utility functions for FIPE scraper

This file contains helpful functions for:
- Exporting data to different formats
- Querying the database
- Data analysis
"""

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Optional, List
import config
from database_models import (
    CarPrice, ModelYear, CarModel, Brand, ReferenceMonth
)


class FIPEDataExporter:
    """
    Helper class to export and analyze FIPE data.
    
    This makes it easy to get data out of the database
    and into formats you can work with.
    """
    
    def __init__(self, database_url: str = None):
        """
        Initialize the exporter.
        
        Args:
            database_url: SQLAlchemy database URL. If None, uses config.
        """
        db_url = database_url or config.DATABASE_URL
        self.engine = create_engine(db_url)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    def export_all_to_csv(self, filename: str = "fipe_data_export.csv"):
        """
        Export all data to a CSV file.

        This creates a denormalized CSV with all information in one table.
        Perfect for opening in Excel or doing analysis in pandas.

        Args:
            filename: Name of the output CSV file
        """
        query = """
        SELECT
            rm.month_date,
            rm.month_code,
            b.brand_name,
            b.brand_code,
            cm.model_name,
            cm.model_code,
            my.year_description,
            my.year_code,
            cp.price,
            cp.fipe_code,
            cp.scraped_at
        FROM car_prices cp
        JOIN reference_months rm ON cp.reference_month_id = rm.id
        JOIN model_years my ON cp.model_year_id = my.id
        JOIN car_models cm ON my.car_model_id = cm.id
        JOIN brands b ON cm.brand_id = b.id
        ORDER BY rm.month_date DESC, b.brand_name, cm.model_name, my.year_description
        """

        df = pd.read_sql(query, self.engine)
        df.to_csv(filename, index=False, encoding='utf-8-sig')  # utf-8-sig for Excel compatibility
        print(f"✓ Exported {len(df)} records to {filename}")
        return df
    
    def export_by_brand(self, brand_name: str, filename: Optional[str] = None):
        """
        Export data for a specific brand to CSV.

        Args:
            brand_name: Name of the brand (e.g., "Volkswagen")
            filename: Output filename. If None, uses brand_name.csv
        """
        if filename is None:
            filename = f"{brand_name.replace(' ', '_')}_data.csv"

        query = f"""
        SELECT
            rm.month_date,
            b.brand_name,
            cm.model_name,
            my.year_description,
            cp.price,
            cp.fipe_code
        FROM car_prices cp
        JOIN reference_months rm ON cp.reference_month_id = rm.id
        JOIN model_years my ON cp.model_year_id = my.id
        JOIN car_models cm ON my.car_model_id = cm.id
        JOIN brands b ON cm.brand_id = b.id
        WHERE b.brand_name LIKE '%{brand_name}%'
        ORDER BY rm.month_date DESC, cm.model_name, my.year_description
        """

        df = pd.read_sql(query, self.engine)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✓ Exported {len(df)} records to {filename}")
        return df
    
    def get_price_history(self, brand_name: str, model_name: str, year_description: str) -> pd.DataFrame:
        """
        Get price history for a specific car over time.

        Args:
            brand_name: Brand name (e.g., "Volkswagen")
            model_name: Model name (e.g., "Gol")
            year_description: Year description (e.g., "2020 Gasolina")

        Returns:
            DataFrame with month_date and price columns
        """
        query = f"""
        SELECT
            rm.month_date,
            cp.price
        FROM car_prices cp
        JOIN reference_months rm ON cp.reference_month_id = rm.id
        JOIN model_years my ON cp.model_year_id = my.id
        JOIN car_models cm ON my.car_model_id = cm.id
        JOIN brands b ON cm.brand_id = b.id
        WHERE b.brand_name LIKE '%{brand_name}%'
        AND cm.model_name LIKE '%{model_name}%'
        AND my.year_description LIKE '%{year_description}%'
        ORDER BY rm.month_date
        """

        df = pd.read_sql(query, self.engine)
        return df
    
    def get_average_price_by_brand(self) -> pd.DataFrame:
        """
        Get average price for each brand across all time periods.
        
        Returns:
            DataFrame with brand names and average prices
        """
        query = """
        SELECT 
            b.brand_name,
            AVG(cp.price) as average_price,
            COUNT(cp.id) as num_records
        FROM car_prices cp
        JOIN model_years my ON cp.model_year_id = my.id
        JOIN car_models cm ON my.car_model_id = cm.id
        JOIN brands b ON cm.brand_id = b.id
        GROUP BY b.brand_name
        ORDER BY average_price DESC
        """
        
        df = pd.read_sql(query, self.engine)
        return df
    
    def get_most_expensive_cars(self, limit: int = 10) -> pd.DataFrame:
        """
        Get the most expensive cars in the most recent month.

        Args:
            limit: Number of results to return

        Returns:
            DataFrame with the most expensive cars
        """
        query = f"""
        SELECT
            b.brand_name,
            cm.model_name,
            my.year_description,
            cp.price,
            rm.month_date
        FROM car_prices cp
        JOIN reference_months rm ON cp.reference_month_id = rm.id
        JOIN model_years my ON cp.model_year_id = my.id
        JOIN car_models cm ON my.car_model_id = cm.id
        JOIN brands b ON cm.brand_id = b.id
        WHERE rm.month_date = (SELECT MAX(month_date) FROM reference_months)
        ORDER BY cp.price DESC
        LIMIT {limit}
        """

        df = pd.read_sql(query, self.engine)
        return df
    
    def get_database_stats(self):
        """
        Print statistics about the database.

        Shows how much data has been collected.
        """
        # Count records in each table
        stats = {
            'Reference Months': self.session.query(ReferenceMonth).count(),
            'Brands': self.session.query(Brand).count(),
            'Car Models': self.session.query(CarModel).count(),
            'Model Years': self.session.query(ModelYear).count(),
            'Price Records': self.session.query(CarPrice).count(),
        }

        print("\n📊 Database Statistics:")
        print("-" * 40)
        for key, value in stats.items():
            print(f"{key:.<25} {value:>10,}")
        print("-" * 40)

        # Get date range using month_date field for proper chronological ordering
        oldest_month = self.session.query(ReferenceMonth).order_by(ReferenceMonth.month_date).first()
        newest_month = self.session.query(ReferenceMonth).order_by(ReferenceMonth.month_date.desc()).first()

        if oldest_month and newest_month:
            print(f"\nDate Range: {oldest_month.month_date} to {newest_month.month_date}")

        return stats
    
    def close(self):
        """Close the database session."""
        self.session.close()


# Standalone utility functions

def quick_export():
    """
    Quick function to export all data to CSV.
    Run this from command line: python -c "from utils import quick_export; quick_export()"
    """
    exporter = FIPEDataExporter()
    df = exporter.export_all_to_csv()
    exporter.get_database_stats()
    exporter.close()
    return df


def show_stats():
    """
    Quick function to show database statistics.
    Run: python -c "from utils import show_stats; show_stats()"
    """
    exporter = FIPEDataExporter()
    exporter.get_database_stats()
    exporter.close()


if __name__ == "__main__":
    # If this file is run directly, show database stats
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "export":
        print("Exporting all data to CSV...")
        quick_export()
    else:
        print("Showing database statistics...")
        show_stats()
        print("\nTip: Run 'python utils.py export' to export data to CSV")
