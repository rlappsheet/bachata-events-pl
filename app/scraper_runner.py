"""Uruchamia wszystkie zarejestrowane scrapery i zapisuje/aktualizuje wydarzenia w bazie.

Rejestr scraperów w `SCRAPERS` - dodanie kolejnego źródła to dodanie klasy
dziedziczącej po BaseScraper i wpisanie jej tutaj.
"""
from __future__ import annotations

import logging
from collections import Counter

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Event, SurveyResponse
from app.scrapers.bachatastars import BachataStarsScraper

logger = logging.getLogger("scraper_runner")

SCRAPERS = [
    BachataStarsScraper(),
]


def get_survey_priorities(db: Session) -> dict:
    """Agreguje odpowiedzi z ankiety, żeby w przyszłości priorytetyzować scraping
    (np. dodawać nowe źródła/miasta najczęściej wskazywane przez użytkowników).
    Na razie tylko zwraca statystyki - wykorzystywane w panelu i logach.
    """
    responses = db.query(SurveyResponse).all()
    city_counter: Counter[str] = Counter()
    style_counter: Counter[str] = Counter()
    source_counter: Counter[str] = Counter()

    for r in responses:
        for city in (r.cities or "").split(","):
            city = city.strip()
            if city:
                city_counter[city.lower()] += 1
        for style in (r.styles or "").split(","):
            style = style.strip()
            if style:
                style_counter[style.lower()] += 1
        for src in (r.preferred_sources or "").split(","):
            src = src.strip()
            if src:
                source_counter[src.lower()] += 1

    return {
        "top_cities": city_counter.most_common(10),
        "top_styles": style_counter.most_common(10),
        "requested_sources": source_counter.most_common(10),
        "responses_count": len(responses),
    }


def run_all_scrapers() -> dict:
    db = SessionLocal()
    stats = {"created": 0, "updated": 0, "errors": 0, "per_source": {}}
    try:
        priorities = get_survey_priorities(db)
        logger.info("Priorytety z ankiety: %s", priorities)

        for scraper in SCRAPERS:
            created = updated = 0
            try:
                scraped = scraper.fetch_events()
            except Exception:
                logger.exception("Scraper %s zawiodl", scraper.name)
                stats["errors"] += 1
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

        stats["survey_priorities"] = priorities
        return stats
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_all_scrapers()
    print(result)
