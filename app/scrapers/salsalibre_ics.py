"""Scraper publicznego kalendarza Google używanego przez salsalibre.pl
(https://salsalibre.pl/kalendarz-wszystkich-imprez/) - kalendarz salsa/bachata/
kizomba/zouk w Warszawie, id kalendarza: salsa.bachata.kizomba.pl@gmail.com.

Pobieramy standardowy publiczny feed iCal (format tekstowy, RFC 5545) i parsujemy
go bez dodatkowej zależności (żadna biblioteka ICS nie jest potrzebna - format
jest prosty: bloki BEGIN:VEVENT...END:VEVENT z polami KEY:VALUE, z "unfoldingiem"
linii zaczynających się spacją/tabem oraz escapowaniem \\, \\; \\n).

Kalendarz zawiera ~870 wydarzeń od 2020 r. - filtrujemy do tych z "bachata"
w tytule i z data w przyszlosci (albo bez daty - nie powinno sie zdarzyc w ICS).
"""
from __future__ import annotations

import re
from datetime import date, datetime

import requests

from app.scrapers.base import BaseScraper, ScrapedEvent

CALENDAR_ID = "salsa.bachata.kizomba.pl@gmail.com"
ICS_URL = (
    "https://calendar.google.com/calendar/ical/"
    + CALENDAR_ID.replace("@", "%40")
    + "/public/basic.ics"
)
SOURCE_PAGE = "https://salsalibre.pl/kalendarz-wszystkich-imprez/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BachataEventsBot/1.0; +local-network-app)"}


def _unescape_ics(value: str) -> str:
    return (
        value.replace("\\n", " ")
        .replace("\\,", ",")
        .replace("\\;", ";")
        .replace("\\\\", "\\")
    )


def _unfold_lines(raw: str) -> list[str]:
    """ICS 'unfolding': linia kontynuacji zaczyna sie spacja/tabem i doklejana
    jest do poprzedniej."""
    lines: list[str] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        if line.startswith((" ", "\t")) and lines:
            lines[-1] += line[1:]
        elif line:
            lines.append(line)
    return lines


def _parse_dt(value: str) -> date | None:
    value = value.strip()
    try:
        if len(value) == 8:  # YYYYMMDD (cale wydarzenie, bez godziny)
            return datetime.strptime(value, "%Y%m%d").date()
        if "T" in value:
            value_clean = value.rstrip("Z")
            return datetime.strptime(value_clean[:15], "%Y%m%dT%H%M%S").date()
    except ValueError:
        return None
    return None


def _parse_ics_events(raw: str) -> list[dict]:
    lines = _unfold_lines(raw)
    events: list[dict] = []
    current: dict | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            current = {}
            continue
        if line == "END:VEVENT":
            if current is not None:
                events.append(current)
            current = None
            continue
        if current is None or ":" not in line:
            continue
        key_part, _, value = line.partition(":")
        key = key_part.split(";")[0]  # odciecie parametrow typu ;VALUE=DATE
        current[key] = _unescape_ics(value)
    return events


class SalsaLibreCalendarScraper(BaseScraper):
    name = "salsalibre.pl (kalendarz)"

    def __init__(self, timeout: int = 15):
        self.timeout = timeout

    def fetch_events(self) -> list[ScrapedEvent]:
        resp = requests.get(ICS_URL, headers=HEADERS, timeout=self.timeout)
        resp.raise_for_status()

        today = date.today()
        events: list[ScrapedEvent] = []
        for raw_event in _parse_ics_events(resp.text):
            summary = raw_event.get("SUMMARY", "").strip()
            if not summary or "bachata" not in summary.lower():
                continue

            date_start = _parse_dt(raw_event.get("DTSTART", ""))
            if date_start is None or date_start < today:
                continue  # pomijamy wydarzenia bez daty albo juz minione

            uid = raw_event.get("UID", summary)
            location = raw_event.get("LOCATION") or None

            events.append(
                ScrapedEvent(
                    source=self.name,
                    source_id=uid,
                    title=summary,
                    url=SOURCE_PAGE,  # kalendarz nie ma osobnych stron per-wydarzenie
                    date_start=date_start,
                    city="Warszawa",
                    country="Poland",
                    venue=location,
                    description=raw_event.get("DESCRIPTION") or None,
                )
            )

        return events
