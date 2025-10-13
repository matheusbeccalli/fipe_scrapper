"""
Example Usage Script for FIPE Data

This script shows different ways to use the scraped FIPE data.
Run this AFTER you've scraped some data with fipe_scraper.py

To run:
    python example_usage.py
"""

from utils import FIPEDataExporter
import pandas as pd

# Set pandas display options for better readability
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)
pd.set_option('display.max_colwidth', 50)


def main():
    """Main function demonstrating various data queries."""
    
    # Create an exporter instance
    print("=" * 60)
    print("FIPE Data Analysis Examples")
    print("=" * 60)
    
    exporter = FIPEDataExporter()
    
    # Example 1: Show database statistics
    print("\n1. DATABASE STATISTICS")
    print("-" * 60)
    exporter.get_database_stats()
    
    # Example 2: Get average price by brand
    print("\n\n2. AVERAGE PRICE BY BRAND (Top 10)")
    print("-" * 60)
    avg_by_brand = exporter.get_average_price_by_brand()
    print(avg_by_brand.head(10).to_string(index=False))
    
    # Example 3: Get most expensive cars
    print("\n\n3. MOST EXPENSIVE CARS (Current Month)")
    print("-" * 60)
    expensive_cars = exporter.get_most_expensive_cars(limit=10)
    if not expensive_cars.empty:
        print(expensive_cars.to_string(index=False))
    else:
        print("No data available yet. Run the scraper first!")
    
    # Example 4: Get price history for a specific car
    # Note: Modify these values based on what's in your database
    print("\n\n4. PRICE HISTORY FOR A SPECIFIC CAR")
    print("-" * 60)
    print("Example: Searching for Volkswagen Gol...")
    
    try:
        price_history = exporter.get_price_history(
            brand_name="Volkswagen",
            model_name="Gol",
            year_description="2020"
        )
        
        if not price_history.empty:
            print(f"\nFound {len(price_history)} price records:")
            print(price_history.tail(12).to_string(index=False))  # Last 12 months
            
            # Calculate price change
            if len(price_history) > 1:
                first_price = price_history.iloc[0]['price']
                last_price = price_history.iloc[-1]['price']
                change = ((last_price - first_price) / first_price) * 100
                print(f"\nPrice Change: {change:+.2f}%")
        else:
            print("No data found. Try different brand/model/year combinations.")
            print("\nTip: First check what brands are available in your database:")
            print("SELECT DISTINCT brand_name FROM brands;")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you have data in the database first!")
    
    # Example 5: Export data to CSV
    print("\n\n5. EXPORTING DATA")
    print("-" * 60)
    user_input = input("Export all data to CSV? (y/n): ").lower()
    
    if user_input == 'y':
        print("Exporting data...")
        exporter.export_all_to_csv("fipe_complete_data.csv")
        print("✓ Data exported successfully!")
    
    # Example 6: Custom pandas analysis
    print("\n\n6. CUSTOM ANALYSIS WITH PANDAS")
    print("-" * 60)
    
    # Load data into pandas for custom analysis
    query = """
    SELECT 
        rm.month_name,
        b.brand_name,
        cm.model_name,
        my.year_description,
        cp.price
    FROM car_prices cp
    JOIN reference_months rm ON cp.reference_month_id = rm.id
    JOIN model_years my ON cp.model_year_id = my.id
    JOIN car_models cm ON my.car_model_id = cm.id
    JOIN brands b ON cm.brand_id = b.id
    """
    
    df = pd.read_sql(query, exporter.engine)
    
    if not df.empty:
        print(f"Loaded {len(df)} records into pandas DataFrame")
        print(f"\nDataFrame shape: {df.shape}")
        print(f"\nFirst few records:")
        print(df.head())
        
        print(f"\nPrice statistics:")
        print(df['price'].describe())
        
        # Find brands with most models
        print(f"\nBrands with most models:")
        models_per_brand = df.groupby('brand_name')['model_name'].nunique().sort_values(ascending=False)
        print(models_per_brand.head(10))
    else:
        print("No data in database yet. Run the scraper first!")
    
    # Clean up
    exporter.close()
    
    print("\n\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\nNext steps:")
    print("- Modify this script to analyze specific brands or models")
    print("- Create visualizations with matplotlib or plotly")
    print("- Export data for use in Excel or other tools")
    print("- Build a web dashboard with the data")


if __name__ == "__main__":
    main()
