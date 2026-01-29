# Suggested Commands

## Environment Setup
```bash
# Create and activate virtual environment (Windows)
python -m venv venv
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment (optional)
cp .env.example .env
# Edit .env as needed

# Create database schema
python database_models.py
```

## Running the Scraper
```bash
# Run the main scraper
python fipe_api_scraper.py

# Monitor progress in real-time
tail -f fipe_scraper.log
# Or on Windows PowerShell:
Get-Content fipe_scraper.log -Wait
```

## Data Export and Analysis
```bash
# Show database statistics
python utils.py

# Export all data to CSV
python utils.py export

# Run example queries
python docs/example_usage.py
```

## Coverage Analysis
```bash
# Generate HTML coverage report (finds data gaps)
python coverage_report.py
# Output: coverage_report_YYYY-MM-DD.html
```

## Git Commands (Windows compatible)
```bash
git status
git add .
git commit -m "message"
git push
git pull
git log --oneline -10
```

## File System (Windows)
```bash
# List directory
dir
# Or use Git Bash: ls -la

# Find files
dir /s /b *.py
# Or use Git Bash: find . -name "*.py"
```

## Python Utilities
```bash
# Check Python version
python --version

# List installed packages
pip list

# Install single package
pip install <package>
```
