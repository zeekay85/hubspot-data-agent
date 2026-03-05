Project structure rules:
- Reusable logic goes in src/
- Runnable scripts go in scripts/
- Reports are written to reports/
- Never commit .env
- All scripts in /scripts must include a sys.path bootstrap so they can import from src.