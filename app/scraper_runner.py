"""Uruchamia wszystkie zarejestrowane scrapery, zapisuje/aktualizuje wydarzenia
w bazie i rejestruje historię uruchomień (ScrapeRun) wykorzystywaną na stronie
głównej ("ostatnia aktualizacja bazy: ...") oraz do automatycznego odświeżania.

Rejestr scraperów w `SCRAPERS` - dodanie kolejnego źródła to dodanie klasy
dziedziczącej po BaseScraper i wpisanie jej tutaj.
"""
from __future__ import annotations

import json
import logging
import threading
from collections import Counter
from datetime import datetime

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Event, ScrapeRun, SurveyResponse
from app.scrapers.bachatastars import BachataStarsScraper

logger = logging.getLogger("scraper_runner")

SCRAPERS = [
    BachataStarsScraper(),
]

# Prosty blokujacy flag w pamieci procesu - zapobiega rownoleglemu
# odpaleniu kilku scrapow naraz (np. gdy dwóch użytkowników wejdzie na strone
# w tym samym momencie, kiedy dane sa nieswieze).
_scrape_lock = threading.Lock()


def _parse_csv_field(value: str | None) -> list[str]:
    return [v.strip() for v in (value or "").split(",") if v.strip()]


def get_survey_priorities(db: Session) -> dict:
    """Agreguje odpowiedzi z ankiety, żeby w przyszłości priorytetyzować scraping
    (np. dodawać nowe źródła/miasta najczęściej wskazywane przez użytkowników).
    """
    responses = db.query(SurveyResponse).all()
    city_counter: Counter[str] = Counter()
    style_counter: Counter[str] = Counter()
    distance_counter: Counter[str] = Counter()
    link_sources: list[str] = []

    for r in responses:
        city = (r.custom_city if r.home_city == "inne" else r.home_city) or ""
        city = city.strip()
        if city:
            city_counter[city.lower()] += 1
        for style in _parse_csv_field(r.styles):
            style_counter[style.lower()] += 1
        if r.distance_scope:
            distance_counter[r.distance_scope] += 1
        for field in (r.whatsapp_groups, r.facebook_pages, r.event_pages):
            if not field:
                continue
            try:
                link_sources.extend(json.loads(field))
            except (json.JSONDecodeError, TypeError):
                continue

    return {
        "top_cities": city_counter.most_common(10),
        "top_styles": style_counter.most_common(10),
        "distance_scope_distribution": distance_counter.most_common(10),
        "suggested_sources": sorted(set(link_sources)),
        "responses_count": len(responses),
    }


def run_all_scrapers() -> dict:
    db = SessionLocal()
    run = ScrapeRun(started_at=datetime.utcnow(), status="running")
    db.add(run)
    db.commit()

    stats = {"created": 0, "updated": 0, "found": 0, "errors": 0, "per_source": {}}
    try:
        priorities = get_survey_priorities(db)
        logger.info("Priorytety z ankiety: %s", priorities)

        for scraper in SCRAPERS:
            created = updated = 0
            try:
                scraped = scraper.fetch_events()
            except Exception as exc:
                logger.exception("Scraper %s zawiodl", scraper.name)
                stats["errors"] += 1
                run.error_message = f"{scraper.name}: {exc}"
                continue

            for item in scraped:
                existing = (
                    db.query(Event)
                    .filter(Event.source == item.source, Event.source_id == item.source_id)
                    .first()
                )
                if existing:
                    for field in (
                        "title", "url", "date_start", "date_end", "time_text",
                        "city", "country", "venue", "description", "image_url",
                        "category", "styles", "external_website",
                    ):
                        setattr(existing, field, getattr(item, field))
                    updated += 1
                else:
                    db.add(Event(**item.__dict__))
                    created += 1

            db.commit()
            stats["per_source"][scraper.name] = {"created": created, "updated": updated, "found": len(scraped)}
            stats["created"] += created
            stats["updated"] += updated
            stats["found"] += len(scraped)

        stats["survey_priorities"] = priorities

        run.status = "error" if stats["errors"] and stats["found"] == 0 else "ok"
        run.finished_at = datetime.utcnow()
        run.events_found = stats["found"]
        run.events_created = stats["created"]
        run.events_updated = stats["updated"]
        db.commit()
        return stats
    except Exception as exc:  # zabezpieczenie na nieprzewidziane błędy
        run.status = "error"
        run.finished_at = datetime.utcnow()
        run.error_message = str(exc)
        db.commit()
        raise
    finally:
        db.close()


def trigger_background_refresh_if_stale(max_age_minutes: int) -> bool:
    """Jeśli dane są starsze niż `max_age_minutes` (albo nigdy nie odświeżane)
    i żaden scrape nie jest aktualnie w toku, odpala scraping w osobnym wątku
    (nie blokuje odpowiedzi HTTP). Zwraca True, jeśli odświeżanie zostało
    właśnie zlecone.
    """
    if not _scrape_lock.acquire(blocking=False):
        return False  # juz trwa odswiezanie

    db = SessionLocal()
    try:
        last_run = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()
        is_stale = (
            last_run is None
            or last_run.finished_at is None
            or (datetime.utcnow() - last_run.finished_at).total_seconds() > max_age_minutes * 60
        )
        if not is_stale:
            _scrape_lock.release()
            return False
    finally:
        db.close()

    def _worker():
        try:
            run_all_scrapers()
        except Exception:
            logger.exception("Odswiezanie w tle nie powiodlo sie")
        finally:
            _scrape_lock.release()

    threading.Thread(target=_worker, daemon=True).start()
    return True


def get_last_scrape_info() -> dict:
    db = SessionLocal()
    try:
        last_ok = (
            db.query(ScrapeRun)
            .filter(ScrapeRun.status == "ok")
            .order_by(ScrapeRun.finished_at.desc())
            .first()
        )
        last_any = db.query(ScrapeRun).order_by(ScrapeRun.started_at.desc()).first()
        return {
            "last_success_at": last_ok.finished_at if last_ok else None,
            "last_success_found": last_ok.events_found if last_ok else None,
            "last_success_created": last_ok.events_created if last_ok else None,
            "last_success_updated": last_ok.events_updated if last_ok else None,
            "refresh_in_progress": _scrape_lock.locked(),
            "last_run_status": last_any.status if last_any else None,
            "last_run_error": last_any.error_message if last_any else None,
        }
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_all_scrapers()
    print(result)
