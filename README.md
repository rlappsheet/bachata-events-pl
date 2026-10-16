# Bachata Events PL

Lekka aplikacja webowa (FastAPI + SQLite), która scrapuje i wyświetla
wydarzenia bachata w Polsce. Zaprojektowana do pracy w sieci lokalnej, z
łatwą ścieżką migracji do kontenera LXC na Proxmox.

## Funkcje

- Strona startowa z listą nadchodzących wydarzeń bachata w Polsce,
  filtrowanie po mieście i tekście, baner "ostatnia aktualizacja bazy: ...".
- Każde wejście na stronę główną sprawdza świeżość danych i — jeśli są
  starsze niż `SCRAPE_FRESHNESS_MINUTES` (domyślnie 60 min) — zleca
  odświeżenie **w tle** (osobny wątek, z blokadą przed równoległym
  odpaleniem dwóch scraperów naraz). Strona nigdy nie czeka na scraper.
- Ankieta (`/ankieta`), kompaktowa i w stylu "chips": wybór miasta z listy
  (Warszawa/Katowice/Kraków/Poznań/...) + promień (5/10/15/25/100/150 km lub
  cała Polska), style i typy wydarzeń jako klikalne tagi, oraz dynamiczne
  listy (dodaj/usuń) na grupy WhatsApp, strony/grupy Facebook i inne strony
  z wydarzeniami — każdy wpis to potencjalne nowe źródło do skrapera.
- Skraper `bachatastars.pl/wydarzenia/` (polska strona poświęcona bachacie) —
  modularny, łatwo dodać kolejne źródła (`app/scrapers/`).
- SQLite jako baza (jeden plik, łatwy backup/migracja).
- REST `/api/events` do dalszej integracji (np. bot, kalendarz).
- Endpoint administracyjny `/admin/scrape?token=...` do ręcznego odpalenia
  scrapera przez HTTP (chroniony tokenem z `.env`).

## Szybki start (lokalnie / sieć lokalna)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env     # ustaw ADMIN_TOKEN

python3 scripts/run_scraper.py     # pierwsze napełnienie bazy
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Aplikacja będzie dostępna:
- lokalnie: http://localhost:8000
- z innych urządzeń w sieci LAN: http://<IP-tego-komputera>:8000

## Docker (opcjonalnie, też lokalnie)

```bash
cp .env.example .env
docker compose up -d --build
```

`docker-compose.yml` uruchamia web (port 8000) oraz osobny kontener
`scraper`, który odświeża dane co 6h.

## Automatyczne odświeżanie danych

- Docker: kontener `scraper` w `docker-compose.yml` (co 6h).
- Bez Dockera: `deploy/bachata-scraper.service` + `.timer` (systemd timer).
- Ręcznie: `python3 scripts/run_scraper.py` albo `GET /admin/scrape?token=...`.

## Dodawanie kolejnych źródeł wydarzeń

1. Utwórz `app/scrapers/<nazwa>.py` z klasą dziedziczącą po `BaseScraper`
   (patrz `app/scrapers/bachatastars.py` jako wzór).
2. Zaimplementuj `fetch_events() -> list[ScrapedEvent]`.
3. Dodaj instancję klasy do listy `SCRAPERS` w `app/scraper_runner.py`.

Odpowiedzi z ankiety (`/admin/survey-stats?token=...`) pokazują, jakie
miasta/style/źródła najczęściej wskazują użytkownicy — to podstawa do
priorytetyzacji kolejnych źródeł do dodania.

## Migracja na Proxmox LXC

Pełna instrukcja: [`deploy/README-PROXMOX-LXC.md`](deploy/README-PROXMOX-LXC.md).
W skrócie: skopiować repo + katalog `data/` (SQLite) do kontenera LXC,
uruchomić przez Docker Compose albo systemd + venv.

## Struktura projektu

```text
app/
├── main.py              FastAPI: trasy / i /ankieta, API, admin
├── config.py            konfiguracja z .env
├── database.py          SQLAlchemy engine/sesja
├── models.py            Event, SurveyResponse
├── scraper_runner.py    uruchamia wszystkie scrapery, zapisuje do bazy
├── scrapers/
│   ├── base.py          interfejs BaseScraper / ScrapedEvent
│   └── bachatastars.py  scraper bachatastars.pl
├── templates/           Jinja2 (base, index, survey)
└── static/style.css
scripts/run_scraper.py   CLI do ręcznego/cron odświeżenia danych
deploy/                  systemd units + instrukcja Proxmox LXC
tests/test_scraper.py    testy logiki dat skrapera
```

## Prywatność i etyka scrapowania

Skraper pobiera tylko publicznie dostępne strony wydarzeń, ustawia własny
User-Agent i nie omija żadnych zabezpieczeń. Przy dodawaniu kolejnych źródeł
sprawdź ich `robots.txt` i regulamin przed scrapowaniem.
