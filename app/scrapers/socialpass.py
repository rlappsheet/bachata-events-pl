"""Scraper dla socialpass.me/poland - kalendarz socjali i festiwali Latin dance
w 7 miastach Polski (salsa/bachata/kizomba/zouk).

Struktura HTML (stan 2026-10), każdy wiersz wydarzenia to <li> zawierające:

<h3><a class="ld-event-card-link" href="/poland/katowice/events/slug">Tytuł</a></h3>
<p data-testid="event-row-when">Fri 6 Nov — Sun 8 Nov</p>
<p data-testid="event-row-where">Nazwa miejsca / adres</p>
<div>...<span>Zouk</span>...</div>   (style wydarzenia)

Drugi segment ścieżki w href to slug miasta (np. "katowice") - uzywany jako city,
bo strona /poland juz filtruje po kraju.
"""
from __future__ import annotations

import re
from datetime import date
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapedEvent

BASE_URL = "https://socialpass.me"
LISTING_URL = f"{BASE_URL}/poland"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BachataEventsBot/1.0; +local-network-app)"}

EN_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# np. "Fri 6 Nov — Sun 8 Nov" albo samo "Fri 6 Nov"
WHEN_RE = re.compile(r"(\d{1,2})\s+([A-Za-z]{3})")


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _guess_year(month: int, day: int) -> int:
    today = date.today()
    year = today.year
    try:
        candidate = date(year, month, day)
    except ValueError:
        candidate = date(year, month, min(day, 28))
    if candidate < today.replace(day=1):
        year += 1
    return year


class SocialPassScraper(BaseScraper):
    name = "socialpass.me"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch_events(self) -> list[ScrapedEvent]:
        resp = requests.get(LISTING_URL, headers=HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        events: list[ScrapedEvent] = []
        seen_urls: set[str] = set()

        for when_el in soup.select('p[data-testid="event-row-when"]'):
            # szukamy najblizszego kontenera <li>, ktory zawiera cala karte wydarzenia
            li = when_el.find_parent("li")
            if not li:
                continue
            link_el = li.select_one("a.ld-event-card-link")
            if not link_el:
                continue

            href = link_el.get("href", "").strip()
            if not href or href in seen_urls:
                continue
            seen_urls.add(href)
            url = urljoin(BASE_URL, href)

            title = link_el.get_text(strip=True)
            if not title:
                continue

            where_el = li.select_one('p[data-testid="event-row-where"]')
            venue = where_el.get_text(strip=True) if where_el else None

            # drugi segment sciezki to slug miasta, np. /poland/katowice/events/...
            parts = [p for p in href.split("/") if p]
            city = parts[1].replace("-", " ").title() if len(parts) > 1 else None

            style_spans = li.select("span")
            styles = ",".join(
                sorted({s.get_text(strip=True).lower() for s in style_spans
                        if s.get_text(strip=True).lower() in
                        {"salsa", "bachata", "kizomba", "zouk"}})
            ) or None

            m = WHEN_RE.search(when_el.get_text(strip=True))
            date_start = None
            if m:
                day_txt, month_abbr = m.groups()
                month_num = EN_MONTHS.get(month_abbr.lower())
                if month_num:
                    year = _guess_year(month_num, int(day_txt))
                    date_start = _safe_date(year, month_num, int(day_txt))

            # Socialpass miesza style (salsa/bachata/kizomba/zouk) - pomijamy wpisy,
            # dla ktorych jednoznacznie wykryto styl inny niz bachata.
            if styles and "bachata" not in styles:
                continue

            events.append(
                ScrapedEvent(
                    source=self.name,
                    source_id=href.strip("/"),
                    title=title,
                    url=url,
                    date_start=date_start,
                    city=city,
                    country="Poland",
                    venue=venue,
                    styles=styles,
                )
            )

        return events
