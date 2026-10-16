#!/usr/bin/env python3
"""CLI do ręcznego/crontabowego uruchomienia scrapera.

Użycie:
    python3 scripts/run_scraper.py
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db
from app.scraper_runner import run_all_scrapers

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    init_db()
    result = run_all_scrapers()
    print(result)
