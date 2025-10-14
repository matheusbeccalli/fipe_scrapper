@echo off
REM Batch script to activate virtual environment and run the FIPE scraper

echo ================================
echo FIPE Scraper - Starting
echo ================================
echo.

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please create it first with: python -m venv venv
    echo Then install dependencies with: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Check if activation was successful
if errorlevel 1 (
    echo ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)

echo Virtual environment activated
echo.

REM Run the scraper
echo Starting FIPE scraper...
echo.
python fipe_api_scraper.py

REM Check exit status
if errorlevel 1 (
    echo.
    echo ================================
    echo ERROR: Scraper encountered an error
    echo ================================
) else (
    echo.
    echo ================================
    echo Scraper completed successfully
    echo ================================
)

echo.
pause
