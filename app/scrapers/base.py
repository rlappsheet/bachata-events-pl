"""Wspólny interfejs dla wszystkich scraperów wydarzeń."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class ScrapedEvent:
    source: str
    source_id: str
    title: str
    url: str
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    time_text: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    venue: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    category: Optional[str] = None
    styles: Optional[str] = None
    external_website: Optional[str] = None


class BaseScraper(ABC):
    """Każdy scraper źródła wydarzeń implementuje `fetch_events`."""

    name: str = "base"

    @abstractmethod
    def fetch_events(self) -> list[ScrapedEvent]:
        """Zwraca listę wydarzeń znalezionych w danym źródle."""
        raise NotImplementedError
