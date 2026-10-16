"""Scraper dla where-to-dance-salsa.com/festivals/bachata/poland/ - międzynarodowy
katalog festiwali tańca latynoamerykańskiego z filtrem Polska+bachata.

Struktura HTML (stan 2026-10), karta festiwalu:

<a class="festival-listing-card" href="/festivals/katowice/bachaturo-festival-2026/"
   data-styles="salsa,bachata,kizomba,zouk" data-country="poland"
   data-month-start="2026-08" data-month-end="2026-08" data-title="bachaturo festival 2026">
  <div>...<span>bachata</span>...</div>
  <div class="p-5 ...">
    <h3>WARSAW ZUMBA FESTIVAL 2026</h3>
    <div>...<span>Warszawa, Poland</span> <span>🇵🇱</span></div>
    <div>...<span>October 9 – 10, 2026</span></div>
  </div>
</a>
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapedEvent

BASE_URL = "https://where-to-dance-salsa.com"
LISTING_URL = f"{BASE_URL}/festivals/bachata/poland/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BachataEventsBot/1.0; +local-network-app)"}

EN_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

DATE_RE = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2})\s*(?:[–\-]\s*\d{1,2})?\s*,\s*(\d{4})"
)


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


class WhereToDanceScraper(BaseScraper):
    name = "where-to-dance-salsa.com"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch_events(self) -> list[ScrapedEvent]:
        resp = requests.get(LISTING_URL, headers=HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        events: list[ScrapedEvent] = []
        for card in soup.select("a.festival-listing-card"):
            styles = (card.get("data-styles") or "").lower()
            if "bachata" not in styles:
                continue

            href = card.get("href", "").strip()
            if not href:
                continue
            url = urljoin(BASE_URL, href)
            source_id = href.strip("/").rsplit("/", 1)[-1] or href

            title_el = card.select_one("h3")
            title = title_el.get_text(strip=True) if title_el else (card.get("data-title") or "").title()
            if not title:
                continue

            spans = card.select("div.p-5 span")
            city = None
            date_start = None
            for span in spans:
                text = span.get_text(strip=True)
                if not text or text.startswith(("🇵🇱", "📍")):
                    continue
                if "," in text and city is None and not DATE_RE.search(text):
                    # np. "Warszawa, Poland"
                    city = text.split(",")[0].strip()
                m = DATE_RE.search(text)
                if m and date_start is None:
                    month_name, day_txt, year_txt = m.groups()
                    month_num = EN_MONTHS.get(month_name.lower())
                    if month_num:
                        date_start = _safe_date(int(year_txt), month_num, int(day_txt))

            events.append(
                ScrapedEvent(
                    source=self.name,
                    source_id=source_id,
                    title=title,
                    url=url,
                    date_start=date_start,
                    city=city,
                    country="Poland",
                    styles="bachata" if "bachata" in styles else None,
                )
            )

        return events
