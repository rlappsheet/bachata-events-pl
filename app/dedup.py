"""Deduplikacja wydarzeń przy wyświetlaniu - niezależne źródła często opisują
ten sam festiwal z drobnymi różnicami (inny zapis tytułu, data przesunięta
o kilka dni przez niepewne parsowanie). Nie czyścimy surowych danych w bazie
(każdy wiersz ma wartość audytową - wiadomo co dany scraper faktycznie znalazł),
tylko redukujemy duplikaty w widoku listy.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date

# Priorytet źródeł przy wyborze "reprezentanta" grupy duplikatów - źródła
# dedykowane Polsce/bachacie wygrywają z ogólnymi katalogami międzynarodowymi.
SOURCE_PRIORITY = {
    "bachatastars.pl": 0,
    "salsalibre.pl (kalendarz)": 1,
    "socialpass.me": 2,
    "where-to-dance-salsa.com": 3,
}

MAX_DAY_DELTA = 3  # te samo wydarzenie z różnych źródeł rzadko różni się bardziej


def _normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKD", title or "").encode("ascii", "ignore").decode()
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    # usuwamy czeste, nieinformacyjne slowa, ktore psuly by porownanie
    for noise in ("official", "event", "promo", "code", "promocode", "discount", "grupa", "znizkowa"):
        text = text.replace(noise, " ")
    return re.sub(r"\s+", " ", text).strip()


def _similar(a: str, b: str) -> bool:
    if not a or not b:
        return False
    tokens_a, tokens_b = set(a.split()), set(b.split())
    if not tokens_a or not tokens_b:
        return False
    overlap = len(tokens_a & tokens_b) / min(len(tokens_a), len(tokens_b))
    return overlap >= 0.6


def dedupe_events(events: list) -> list:
    """events: lista obiektów z atrybutami .title, .date_start, .source (model Event).
    Zwraca liste bez duplikatow, zachowujac porzadek wejsciowy, wybierajac
    reprezentanta grupy wg SOURCE_PRIORITY (nizszy numer = wyzszy priorytet)."""
    groups: list[list] = []

    for event in events:
        norm_title = _normalize_title(event.title)
        placed = False
        for group in groups:
            rep = group[0]
            rep_norm = _normalize_title(rep.title)
            same_date_window = (
                event.date_start is not None
                and rep.date_start is not None
                and abs((event.date_start - rep.date_start).days) <= MAX_DAY_DELTA
            )
            if same_date_window and _similar(norm_title, rep_norm):
                group.append(event)
                # jesli nowy element ma wyzszy priorytet zrodla, staje sie reprezentantem
                group.sort(key=lambda e: SOURCE_PRIORITY.get(e.source, 99))
                placed = True
                break
        if not placed:
            groups.append([event])

    return [group[0] for group in groups]
