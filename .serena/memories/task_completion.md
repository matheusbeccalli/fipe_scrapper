# Task Completion Checklist

When completing a development task in this project, follow these steps:

## Before Committing

1. **Test the changes manually**
   - Run the affected script(s) to verify behavior
   - For scraper changes: test with a limited date range in `.env`

2. **Check for syntax errors**
   ```bash
   python -m py_compile <modified_file.py>
   ```

3. **Verify imports work**
   ```bash
   python -c "import <module_name>"
   ```

## No Formal Testing/Linting Setup
This project currently does not have:
- Automated test suite (pytest, unittest)
- Linting tools (flake8, pylint, ruff)
- Formatting tools (black, autopep8)

If adding these in the future, update this file.

## Git Workflow
```bash
# Check status
git status

# Stage changes
git add <files>

# Commit with descriptive message
git commit -m "feat/fix/docs/chore: description"

# Push to remote
git push
```

## Documentation
- Update `CLAUDE.md` if adding new commands or changing architecture
- Update `docs/` for user-facing documentation
- Add docstrings for new functions/classes
