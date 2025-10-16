# FIPE API Documentation

## Summary

The FIPE website exposes a fully functional REST API that allows direct access to all vehicle pricing data **without requiring Selenium or browser automation**. This API enables scraping that is 50-100x faster than the current Selenium-based approach.

## API Base URL

```
http://veiculos.fipe.org.br/api/veiculos
```

## Required Headers

```python
{
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'http://veiculos.fipe.org.br',
    'Referer': 'http://veiculos.fipe.org.br/',
    'X-Requested-With': 'XMLHttpRequest',
}
```

## API Endpoints

### 1. Get Reference Months

**Endpoint:** `POST /ConsultarTabelaDeReferencia`

**Parameters:** None

**Response Example:**
```json
[
  {
    "Codigo": 326,
    "Mes": "outubro/2025 "
  },
  {
    "Codigo": 325,
    "Mes": "setembro/2025 "
  }
]
```

**Notes:**
- Returns 298+ months (from 2001 to present)
- `Codigo` is used in subsequent API calls
- Response is cached for 3 hours (Cache-Control header)

---

### 2. Get Brands

**Endpoint:** `POST /ConsultarMarcas`

**Parameters:**
```python
{
    'codigoTabelaReferencia': 326,  # From endpoint #1
    'codigoTipoVeiculo': 1          # 1=Cars, 2=Motorcycles, 3=Trucks
}
```

**Response Example:**
```json
[
  {
    "Label": "Acura",
    "Value": "1"
  },
  {
    "Label": "Agrale",
    "Value": "2"
  }
]
```

**Notes:**
- Returns 103 car brands
- `Value` is the brand code for subsequent calls

---

### 3. Get Models

**Endpoint:** `POST /ConsultarModelos`

**Parameters:**
```python
{
    'codigoTabelaReferencia': 326,
    'codigoTipoVeiculo': 1,
    'codigoMarca': '1'  # Brand code from endpoint #2
}
```

**Response Example:**
```json
{
  "Modelos": [
    {
      "Label": "Integra GS 1.8",
      "Value": 1
    },
    {
      "Label": "Legend 3.2/3.5",
      "Value": 2
    }
  ],
  "Anos": [
    {
      "Label": "1998 Gasolina",
      "Value": "1998-1"
    }
  ]
}
```

**Notes:**
- Returns nested object with `Modelos` (models) and `Anos` (years) arrays
- `Modelos[].Value` is the model code
- `Anos` array can be used to skip endpoint #4 (optimization!)

---

### 4. Get Years

**Endpoint:** `POST /ConsultarAnoModelo`

**Parameters:**
```python
{
    'codigoTabelaReferencia': 326,
    'codigoTipoVeiculo': 1,
    'codigoMarca': '1',
    'codigoModelo': 1  # Model code from endpoint #3
}
```

**Response Example:**
```json
[
  {
    "Label": "1992 Gasolina",
    "Value": "1992-1"
  },
  {
    "Label": "1991 Gasolina",
    "Value": "1991-1"
  }
]
```

**Notes:**
- `Value` format: `"YEAR-FUEL_CODE"` (e.g., "1992-1")
- Common fuel codes: 1=Gasoline, 2=Alcohol, 3=Diesel

---

### 5. Get Price Data

**Endpoint:** `POST /ConsultarValorComTodosParametros`

**Parameters:**
```python
{
    'codigoTabelaReferencia': 326,
    'codigoTipoVeiculo': 1,
    'codigoMarca': '1',
    'codigoModelo': 1,
    'anoModelo': '1992',              # Year part only (split from "1992-1")
    'codigoTipoCombustivel': '1',     # Fuel code part (split from "1992-1")
    'tipoConsulta': 'tradicional'
}
```

**Response Example:**
```json
{
  "Valor": "R$ 11.007,00",
  "Marca": "Acura",
  "Modelo": "Integra GS 1.8",
  "AnoModelo": 1992,
  "Combustivel": "Gasolina",
  "CodigoFipe": "038003-2",
  "MesReferencia": "outubro de 2025 ",
  "TipoVeiculo": 1,
  "SiglaCombustivel": "G",
  "DataConsulta": "terça-feira, 14 de outubro de 2025 07:10",
  "Autenticacao": "ghc40wlrn6"
}
```

**Notes:**
- This is the final endpoint that returns the actual price
- `Valor` needs parsing (remove "R$ " and convert comma to decimal)
- `CodigoFipe` is the official FIPE reference code

---

## Scraping Workflow

```
1. Get all reference months
   └─> For each month:
       2. Get all brands
          └─> For each brand:
              3. Get all models (includes years in response!)
                 └─> For each model:
                     └─> For each year (from step 3):
                         4. Get price data
                         5. Save to database
```

## Performance Comparison

| Approach | Speed | Memory | Complexity |
|----------|-------|--------|------------|
| **Selenium (current)** | 1x baseline | ~500MB per browser | High (browser automation) |
| **Direct API** | **50-100x faster** | ~50MB | Low (simple HTTP) |
| **API + Async** | **100-200x faster** | ~100MB | Medium (concurrent requests) |

## Key Advantages

1. **No Selenium Required** - Pure HTTP requests with `requests` library
2. **Extremely Fast** - No browser overhead, direct JSON responses
3. **Concurrent Requests** - Can make hundreds of parallel API calls
4. **Cacheable** - API responses are cached for 3 hours
5. **Low Memory** - No browser instances consuming hundreds of MB
6. **Reliable** - No JavaScript timing issues or DOM changes
7. **Simpler Code** - ~200 lines vs 777 lines

## Implementation Notes

- The API has CORS enabled (`Access-Control-Allow-Origin: *`)
- Responses are gzipped automatically
- CloudFlare is used for caching and CDN
- No authentication or API keys required
- Rate limiting not observed during testing
- Recommend 0.1-0.5 second delays between requests for politeness

## Next Steps

1. Create optimized API-based scraper
2. Implement async/await with `aiohttp` for maximum concurrency
3. Add progress tracking and resume capability
4. Run performance benchmarks vs Selenium approach
