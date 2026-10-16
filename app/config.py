"""Konfiguracja aplikacji wczytywana ze zmiennych środowiskowych / .env."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv(BASE_DIR / ".env")

APP_HOST = os.environ.get("APP_HOST", "0.0.0.0")
APP_PORT = int(os.environ.get("APP_PORT", "8000"))
DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'bachata_events.db'}")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "change-me")
SCRAPE_INTERVAL_HOURS = int(os.environ.get("SCRAPE_INTERVAL_HOURS", "0"))
# co ile minut dane sa uznawane za "nieswieze" - strona glowna zleca wtedy
# odswiezenie w tle (nie blokujac odpowiedzi HTTP)
SCRAPE_FRESHNESS_MINUTES = int(os.environ.get("SCRAPE_FRESHNESS_MINUTES", "60"))

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
