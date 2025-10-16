# FIPE Brand Codes Reference

This file contains all brand codes available in the FIPE API for use with the brand filtering feature.

**Important Notes:**
- These codes are valid as of **October 15, 2025** (Reference month: outubro/2025)
- Brand codes may change if the FIPE API is updated
- To get the latest brand codes, re-run the scraper or query your database: `SELECT brand_code, brand_name FROM brands ORDER BY brand_name;`
- Total brands listed: **103**

## How to Use Brand Codes

When configuring brand filtering in your `.env` file, use these codes:

```bash
# Example: Filter for Audi and Volkswagen
BRAND_FILTER_ENABLED=true
BRAND_FILTER_CODES=6,59

# Example: Filter for premium German brands
BRAND_FILTER_ENABLED=true
BRAND_FILTER_CODES=6,7,39,47  # Audi, BMW, Mercedes-Benz, Porsche
```

## Complete Brand Code List

| Code | Brand Name           | Code | Brand Name           |
|------|---------------------|------|---------------------|
| 1    | Acura               | 168  | LIFAN               |
| 2    | Agrale              | 170  | Fyber               |
| 3    | Alfa Romeo          | 171  | LAMBORGHINI         |
| 4    | AM Gen              | 177  | JAC                 |
| 5    | Asia Motors         | 182  | CHANGAN             |
| 6    | Audi                | 183  | SHINERAY            |
| 7    | BMW                 | 185  | RAM                 |
| 8    | BRM                 | 186  | RELY                |
| 10   | Cadillac            | 189  | ASTON MARTIN        |
| 11   | CBT Jipe            | 190  | FOTON               |
| 12   | Chrysler            | 195  | Rolls-Royce         |
| 14   | Cross Lander        | 199  | GEELY               |
| 15   | Daewoo              | 207  | Baby                |
| 16   | Daihatsu            | 208  | IVECO               |
| 17   | Dodge               | 211  | Mclaren             |
| 18   | Engesa              | 214  | HITECH ELECTRIC     |
| 19   | Envemo              | 236  | CAB Motors          |
| 20   | Ferrari             | 238  | BYD                 |
| 21   | Fiat                | 240  | GWM                 |
| 22   | Ford                | 241  | D2D Motors          |
| 23   | GM - Chevrolet      | 245  | Caoa Chery          |
| 24   | Gurgel              | 246  | DFSK                |
| 25   | Honda               | 247  | SERES               |
| 26   | Hyundai             | 249  | FEVER               |
| 27   | Isuzu               | 250  | NETA                |
| 28   | Jaguar              | 251  | Jaecoo              |
| 29   | Jeep                | 252  | Omoda               |
| 30   | JPX                 | 253  | ZEEKR               |
| 31   | Kia Motors          | 254  | GAC                 |
| 32   | Lada                | 120  | Walk                |
| 33   | Land Rover          | 123  | Bugre               |
| 34   | Lexus               | 125  | SSANGYONG           |
| 35   | Lotus               | 127  | LOBINI              |
| 36   | Maserati            | 136  | CHANA               |
| 37   | Matra               | 140  | Mahindra            |
| 38   | Mazda               | 147  | EFFA                |
| 39   | Mercedes-Benz       | 149  | Fibravan            |
| 40   | Mercury             | 152  | HAFEI               |
| 41   | Mitsubishi          | 153  | GREAT WALL          |
| 42   | Miura               | 154  | JINBEI              |
| 43   | Nissan              | 156  | MINI                |
| 44   | Peugeot             | 157  | smart               |
| 45   | Plymouth            | 161  | Caoa Chery/Chery    |
| 46   | Pontiac             | 163  | Wake                |
| 47   | Porsche             | 165  | TAC                 |
| 48   | Renault             | 167  | MG                  |
| 49   | Rover               |      |                     |
| 50   | Saab                |      |                     |
| 51   | Saturn              |      |                     |
| 52   | Seat                |      |                     |
| 54   | Subaru              |      |                     |
| 55   | Suzuki              |      |                     |
| 56   | Toyota              |      |                     |
| 57   | Troller             |      |                     |
| 58   | Volvo               |      |                     |
| 59   | VW - VolksWagen     |      |                     |

**New Brands Added (since last update):**
- 250: NETA (Chinese EV brand)
- 251: Jaecoo (Chinese brand from Chery Group)
- 252: Omoda (Chinese brand from Chery Group)
- 253: ZEEKR (Chinese EV brand from Geely)
- 254: GAC (Guangzhou Automobile Group - Chinese)

## Popular Brand Combinations

### Brazilian Market Leaders
```bash
BRAND_FILTER_CODES=21,22,23,59  # Fiat, Ford, Chevrolet, Volkswagen
```

### Premium Brands
```bash
BRAND_FILTER_CODES=6,7,20,28,33,34,39,47  # Audi, BMW, Ferrari, Jaguar, Land Rover, Lexus, Mercedes-Benz, Porsche
```

### Japanese Brands
```bash
BRAND_FILTER_CODES=25,26,38,41,43,54,55,56  # Honda, Hyundai, Mazda, Mitsubishi, Nissan, Subaru, Suzuki, Toyota
```

### Chinese Brands (Updated)
```bash
BRAND_FILTER_CODES=136,153,154,161,168,177,182,183,199,238,240,245,250,251,252,253,254  # Various Chinese manufacturers including new EV brands
```

### New Electric Vehicle (EV) Brands
```bash
BRAND_FILTER_CODES=238,250,253  # BYD, NETA, ZEEKR
```

## Updating This List

To regenerate this list with current data from the FIPE API:

```bash
python -c "
import asyncio
import aiohttp
import sys
from datetime import datetime
from fipe_api_scraper import FIPEAPIScraper

async def get_brands():
    scraper = FIPEAPIScraper(max_concurrent_requests=1)
    async with aiohttp.ClientSession() as session:
        months = await scraper.get_reference_months(session)
        # Use most recent month
        brands = await scraper.get_brands(session, months[0]['Codigo'])
        brands_sorted = sorted(brands, key=lambda x: x['Label'])
        for brand in brands_sorted:
            print(f\"{brand['Value']:5} | {brand['Label']}\")

asyncio.run(get_brands())
"
```

Or query your database:

```bash
python -c "
from database_models import create_database, Brand
import config

engine, SessionMaker = create_database(config.DATABASE_URL)
session = SessionMaker()
brands = session.query(Brand).order_by(Brand.brand_name).all()

for brand in brands:
    print(f'{brand.brand_code:5} | {brand.brand_name}')

session.close()
"
```
