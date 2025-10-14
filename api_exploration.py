"""
FIPE API Exploration Script

This script investigates the FIPE backend API endpoints to determine
if we can bypass Selenium and scrape data directly via HTTP requests.

Based on initial analysis, the API base URL is:
http://veiculos.fipe.org.br/api/veiculos/
"""

import requests
import json
from pprint import pprint
from typing import Dict, List

# API Configuration
API_BASE_URL = "http://veiculos.fipe.org.br/api/veiculos"

# Common headers to mimic browser requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'Accept-Language': 'en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
    'Origin': 'http://veiculos.fipe.org.br',
    'Referer': 'http://veiculos.fipe.org.br/',
    'X-Requested-With': 'XMLHttpRequest',
}


def test_endpoint(endpoint: str, method: str = 'POST', data: Dict = None) -> Dict:
    """
    Test an API endpoint and return the response.

    Args:
        endpoint: API endpoint path (e.g., '/ConsultarTabelaDeReferencia')
        method: HTTP method (GET or POST)
        data: Request payload for POST requests

    Returns:
        JSON response or error dict
    """
    url = f"{API_BASE_URL}{endpoint}"
    print(f"\n{'='*80}")
    print(f"Testing: {method} {url}")
    if data:
        print(f"Payload: {data}")
    print('='*80)

    try:
        if method.upper() == 'POST':
            response = requests.post(url, data=data, headers=HEADERS, timeout=10)
        else:
            response = requests.get(url, params=data, headers=HEADERS, timeout=10)

        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")

        # Try to parse JSON response
        try:
            json_data = response.json()
            print(f"\nJSON Response ({len(json_data)} items):" if isinstance(json_data, list) else "\nJSON Response:")

            # Show first few items if it's a list
            if isinstance(json_data, list):
                pprint(json_data[:3] if len(json_data) > 3 else json_data)
                if len(json_data) > 3:
                    print(f"... and {len(json_data) - 3} more items")
            else:
                pprint(json_data)

            return json_data
        except json.JSONDecodeError:
            print(f"\nText Response:\n{response.text[:500]}")
            return {'error': 'Not JSON', 'text': response.text}

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return {'error': str(e)}


def explore_api():
    """
    Systematically explore the FIPE API endpoints.

    Based on common API patterns and the website structure, we'll test:
    1. Reference months endpoint
    2. Brands endpoint
    3. Models endpoint
    4. Years endpoint
    5. Price data endpoint
    """

    print("FIPE API EXPLORATION")
    print("=" * 80)

    # Test 1: Get reference months (time periods available)
    print("\n\n### TEST 1: Get Reference Months ###")
    months = test_endpoint('/ConsultarTabelaDeReferencia', method='POST')

    # Select first month if available
    selected_month = None
    if isinstance(months, list) and len(months) > 0:
        selected_month = months[0]['Codigo']
        print(f"\nSelected month for testing: {months[0]}")

    # Test 2: Get brands for cars (tipo=1 usually means cars)
    print("\n\n### TEST 2: Get Car Brands ###")
    # Common vehicle type codes: 1=cars, 2=motorcycles, 3=trucks
    brands = test_endpoint('/ConsultarMarcas', method='POST', data={
        'codigoTabelaReferencia': selected_month or 1,
        'codigoTipoVeiculo': 1  # Cars
    })

    # Select first brand if available
    selected_brand = None
    if isinstance(brands, list) and len(brands) > 0:
        selected_brand = brands[0]['Value']
        print(f"\nSelected brand for testing: {brands[0]}")

    # Test 3: Get models for a brand
    if selected_month and selected_brand:
        print("\n\n### TEST 3: Get Models for Brand ###")
        models = test_endpoint('/ConsultarModelos', method='POST', data={
            'codigoTabelaReferencia': selected_month,
            'codigoTipoVeiculo': 1,
            'codigoMarca': selected_brand
        })

        # Extract models list (response might be nested)
        selected_model = None
        if isinstance(models, dict) and 'Modelos' in models:
            models_list = models['Modelos']
            if len(models_list) > 0:
                selected_model = models_list[0]['Value']
                print(f"\nSelected model for testing: {models_list[0]}")

        # Test 4: Get years for a model
        if selected_model:
            print("\n\n### TEST 4: Get Years for Model ###")
            years = test_endpoint('/ConsultarAnoModelo', method='POST', data={
                'codigoTabelaReferencia': selected_month,
                'codigoTipoVeiculo': 1,
                'codigoMarca': selected_brand,
                'codigoModelo': selected_model
            })

            # Select first year if available
            selected_year = None
            if isinstance(years, list) and len(years) > 0:
                selected_year = years[0]['Value']
                print(f"\nSelected year for testing: {years[0]}")

            # Test 5: Get price data for specific vehicle
            if selected_year:
                print("\n\n### TEST 5: Get Price Data ###")

                # The year value format is usually: "YEAR-FUEL_CODE" (e.g., "2024-1")
                # We need to split it if it contains a dash
                if '-' in selected_year:
                    year_parts = selected_year.split('-')
                    ano_modelo = year_parts[0]
                    tipo_combustivel = year_parts[1] if len(year_parts) > 1 else '1'
                else:
                    ano_modelo = selected_year
                    tipo_combustivel = '1'

                price_data = test_endpoint('/ConsultarValorComTodosParametros', method='POST', data={
                    'codigoTabelaReferencia': selected_month,
                    'codigoTipoVeiculo': 1,
                    'codigoMarca': selected_brand,
                    'codigoModelo': selected_model,
                    'anoModelo': ano_modelo,
                    'codigoTipoCombustivel': tipo_combustivel,
                    'tipoConsulta': 'tradicional'
                })

    # Summary
    print("\n\n" + "=" * 80)
    print("API EXPLORATION SUMMARY")
    print("=" * 80)
    print("""
    If all endpoints returned valid data, the API is viable!

    Expected workflow:
    1. GET /ConsultarTabelaDeReferencia → List of reference months
    2. POST /ConsultarMarcas → List of brands (requires month)
    3. POST /ConsultarModelos → List of models (requires month + brand)
    4. POST /ConsultarAnoModelo → List of years (requires month + brand + model)
    5. POST /ConsultarValorComTodosParametros → Price data (requires all params)

    This API structure would allow us to:
    - Eliminate Selenium completely
    - Run 50-100x faster (pure HTTP vs browser automation)
    - Use async/await for concurrent requests
    - Dramatically reduce memory usage
    """)


def test_additional_endpoints():
    """Test other potential endpoints."""
    print("\n\n### TESTING ADDITIONAL ENDPOINTS ###")

    # Try some common endpoint variations
    endpoints_to_test = [
        '/ConsultarTiposVeiculo',
        '/ConsultarValor',
        '/ConsultarModelosAtravesDoAno',
    ]

    for endpoint in endpoints_to_test:
        test_endpoint(endpoint, method='POST')


if __name__ == "__main__":
    explore_api()

    # Uncomment to test additional endpoints
    # test_additional_endpoints()
