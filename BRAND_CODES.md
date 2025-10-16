# FIPE Brand Codes Reference

This file contains all brand codes available in the FIPE API for use with the brand filtering feature.

**Important Notes:**
- These codes are valid as of **October 15, 2025**
- Brand codes may change if the FIPE API is updated
- To get the latest brand codes from your database, run: `SELECT brand_code, brand_name FROM brands ORDER BY brand_name;`
- Total brands listed: **98**

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
| 1    | Acura               | 127  | LOBINI              |
| 2    | Agrale              | 136  | CHANA               |
| 3    | Alfa Romeo          | 140  | Mahindra            |
| 4    | AM Gen              | 147  | EFFA                |
| 5    | Asia Motors         | 149  | Fibravan            |
| 6    | Audi                | 152  | HAFEI               |
| 7    | BMW                 | 153  | GREAT WALL          |
| 8    | BRM                 | 154  | JINBEI              |
| 10   | Cadillac            | 156  | MINI                |
| 11   | CBT Jipe            | 157  | smart               |
| 12   | Chrysler            | 161  | Caoa Chery/Chery    |
| 13   | Citroën             | 163  | Wake                |
| 14   | Cross Lander        | 165  | TAC                 |
| 15   | Daewoo              | 167  | MG                  |
| 16   | Daihatsu            | 168  | LIFAN               |
| 17   | Dodge               | 170  | Fyber               |
| 18   | Engesa              | 171  | LAMBORGHINI         |
| 19   | Envemo              | 177  | JAC                 |
| 20   | Ferrari             | 182  | CHANGAN             |
| 21   | Fiat                | 183  | SHINERAY            |
| 22   | Ford                | 185  | RAM                 |
| 23   | GM - Chevrolet      | 186  | RELY                |
| 24   | Gurgel              | 189  | ASTON MARTIN        |
| 25   | Honda               | 190  | FOTON               |
| 26   | Hyundai             | 195  | Rolls-Royce         |
| 27   | Isuzu               | 199  | GEELY               |
| 28   | Jaguar              | 207  | Baby                |
| 29   | Jeep                | 208  | IVECO               |
| 30   | JPX                 | 211  | Mclaren             |
| 31   | Kia Motors          | 214  | HITECH ELECTRIC     |
| 32   | Lada                | 236  | CAB Motors          |
| 33   | Land Rover          | 238  | BYD                 |
| 34   | Lexus               | 240  | GWM                 |
| 35   | Lotus               | 241  | D2D Motors          |
| 36   | Maserati            | 245  | Caoa Chery          |
| 37   | Matra               | 246  | DFSK                |
| 38   | Mazda               | 247  | SERES               |
| 39   | Mercedes-Benz       | 249  | FEVER               |
| 40   | Mercury             | 120  | Walk                |
| 41   | Mitsubishi          | 123  | Bugre               |
| 42   | Miura               | 125  | SSANGYONG           |
| 43   | Nissan              |      |                     |
| 44   | Peugeot             |      |                     |
| 45   | Plymouth            |      |                     |
| 46   | Pontiac             |      |                     |
| 47   | Porsche             |      |                     |
| 48   | Renault             |      |                     |
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

### Chinese Brands
```bash
BRAND_FILTER_CODES=136,153,154,161,168,177,182,183,199,238,240,245  # Various Chinese manufacturers
```

## Updating This List

To regenerate this list with current data from your database:

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
