"""Scraper dla bachatastars.pl/wydarzenia/ (polska strona po polsku, dedykowana bachacie).

Struktura HTML (WordPress + wtyczka "Import Facebook Events", stan na 2026-10):

<div class="... post-XXXX facebook_events type-facebook_events ...">
  <div class="ife_event">
    <a href="DETAIL_URL"><div class="img_placeholder" style="background: url('IMG')"></div></a>
    <div class="event_details">
      <a href="DETAIL_URL">
        <div class="event_date">
          <span class="month">sie</span>
          <span class="date"> 13 </span>
        </div>
      </a>
      <div class="event_desc">
        <a href="DETAIL_URL" rel="bookmark"><div class="event_title">TITLE</div></a>
        <div class="event_address"><i class="fa fa-map-marker"></i> VENUE</div>
      </div>
    </div>
  </div>
</div>

Strona detalu zawiera dodatkowo: Date (np. "13 sierpnia"), Time, Event Category,
Website (link zewnętrzny), Venue + "Miasto, Kraj", oraz pełny opis.
"""
from __future__ import annotations

import re
from datetime import date, datetime

import requests
from bs4 import BeautifulSoup

from app.scrapers.base import BaseScraper, ScrapedEvent

LISTING_URL = "https://bachatastars.pl/wydarzenia/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BachataEventsBot/1.0; +local-network-app)"}

PL_MONTHS_ABBR = {
    "sty": 1, "lut": 2, "mar": 3, "kwi": 4, "maj": 5, "cze": 6,
    "lip": 7, "sie": 8, "wrz": 9, "paź": 10, "paz": 10, "lis": 11, "gru": 12,
}
PL_MONTHS_FULL = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9, "października": 10,
    "pazdziernika": 10, "listopada": 11, "grudnia": 12,
}

STYLE_KEYWORDS = {
    "sensual": "sensual",
    "dominicana": "dominicana",
    "urban": "urban",
    "zouk": "zouk",
    "kizomba": "kizomba",
    "salsa": "salsa",
}


def _guess_year(month: int, day: int, title: str) -> int:
    m = re.search(r"\b(20\d{2})\b", title)
    if m:
        return int(m.group(1))
    today = date.today()
    candidate_year = today.year
    try:
        candidate = date(candidate_year, month, day)
    except ValueError:
        candidate = date(candidate_year, month, min(day, 28))
    if candidate < today.replace(day=1):
        candidate_year += 1
    return candidate_year


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


class BachataStarsScraper(BaseScraper):
    name = "bachatastars.pl"

    def __init__(self, fetch_details: bool = True, timeout: int = 15, poland_only: bool = True):
        self.fetch_details = fetch_details
        self.timeout = timeout
        self.poland_only = poland_only

    def fetch_events(self) -> list[ScrapedEvent]:
        resp = requests.get(LISTING_URL, headers=HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        events: list[ScrapedEvent] = []
        seen_urls: set[str] = set()

        for card in soup.select("div.facebook_events"):
            desc_block = card.select_one(".event_desc")
            if not desc_block:
                continue
            title_el = desc_block.select_one(".event_title")
            link_el = desc_block.select_one("a[rel='bookmark']") or card.select_one("a[href]")
            if not title_el or not link_el:
                continue

            url = link_el.get("href", "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)

            title = title_el.get_text(strip=True)
            source_id = url.rstrip("/").rsplit("/", 1)[-1]

            month_el = card.select_one(".event_date .month")
            day_el = card.select_one(".event_date .date")
            date_start = None
            if month_el and day_el:
                month_abbr = month_el.get_text(strip=True).lower()
                month_num = PL_MONTHS_ABBR.get(month_abbr)
                day_txt = re.sub(r"\D", "", day_el.get_text(strip=True))
                if month_num and day_txt:
                    day_num = int(day_txt)
                    year = _guess_year(month_num, day_num, title)
                    date_start = _safe_date(year, month_num, day_num)

            address_el = desc_block.select_one(".event_address")
            venue = address_el.get_text(strip=True) if address_el else None

            img_el = card.select_one(".img_placeholder")
            image_url = None
            if img_el and img_el.get("style"):
                m = re.search(r"url\(['\"]?(.*?)['\"]?\)", img_el["style"])
                if m:
                    image_url = m.group(1)

            event = ScrapedEvent(
                source=self.name,
                source_id=source_id,
                title=title,
                url=url,
                date_start=date_start,
                venue=venue,
                image_url=image_url,
            )
            events.append(event)

        if self.fetch_details:
            for event in events:
                try:
                    self._enrich_with_detail(event)
                except Exception:
                    # detal jest tylko wzbogaceniem - błąd nie powinien wyrzucać calego batcha
                    continue

        if self.poland_only:
            events = [e for e in events if self._looks_polish(e)]

        return events

    @staticmethod
    def _looks_polish(event: ScrapedEvent) -> bool:
        if event.country:
            return event.country.strip().lower() in ("poland", "polska")
        # brak danych o kraju (np. detal nie zaladowal sie) - sprawdz tekst jako fallback
        haystack = " ".join(filter(None, [event.title, event.venue, event.city])).lower()
        return "poland" in haystack or "polska" in haystack or any(
            city in haystack for city in (
                "warszawa", "warsaw", "kraków", "krakow", "katowice", "wrocław", "wroclaw",
                "poznań", "poznan", "gdańsk", "gdansk", "łódź", "lodz",
            )
        )

    def _enrich_with_detail(self, event: ScrapedEvent) -> None:
        resp = requests.get(event.url, headers=HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        details_block = soup.select_one(".organizermain .details")
        if details_block:
            text = details_block.get_text("\n", strip=True)

            date_m = re.search(r"Date:\s*\n?\s*(\d{1,2})\s+([a-ząćęłńóśźż]+)", text, re.IGNORECASE)
            if date_m:
                day_num = int(date_m.group(1))
                month_name = date_m.group(2).lower()
                month_num = PL_MONTHS_FULL.get(month_name)
                if month_num:
                    year = _guess_year(month_num, day_num, event.title)
                    better_date = _safe_date(year, month_num, day_num)
                    if better_date:
                        event.date_start = better_date

            time_m = re.search(r"Time:\s*\n?\s*([0-9:\-\s]+)", text)
            if time_m:
                event.time_text = time_m.group(1).strip()

            cat_links = details_block.select("p a")
            if cat_links:
                event.category = ", ".join(a.get_text(strip=True) for a in cat_links)

            website_el = details_block.select_one(".website_wrap a")
            if website_el:
                event.external_website = website_el.get("href")

        venue_block = soup.select_one(".organizermain.library .venue")
        if venue_block:
            paras = venue_block.select("p")
            if paras:
                event.venue = event.venue or paras[0].get_text(strip=True)
            # Linia(e) adresowe sa kursywa (<i>); ostatnia zwykle ma format
            # "Miasto, Miasto, Kraj" albo "Miasto, Kraj" - bierzemy ostatnia.
            addr_paras = [p for p in paras[1:] if p.get_text(strip=True)]
            if addr_paras:
                loc = addr_paras[-1].get_text(strip=True)
                parts = [p.strip() for p in loc.split(",") if p.strip()]
                if parts:
                    event.country = parts[-1]
                    event.city = parts[-2] if len(parts) > 1 else parts[0]

        content_m = soup.select_one("article") or soup.select_one(".ife_eventmeta")
        if content_m:
            full_text = content_m.get_text(" ", strip=True)
            event.description = full_text[:4000]
            lowered = full_text.lower()
            matched_styles = [v for k, v in STYLE_KEYWORDS.items() if k in lowered]
            if matched_styles:
                event.styles = ",".join(sorted(set(matched_styles)))
