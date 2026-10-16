import sys
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.scrapers.bachatastars import _guess_year, _safe_date, PL_MONTHS_ABBR, PL_MONTHS_FULL


def test_pl_months_abbr_mapping():
    assert PL_MONTHS_ABBR["sie"] == 8
    assert PL_MONTHS_ABBR["lip"] == 7
    assert PL_MONTHS_ABBR["lis"] == 11


def test_pl_months_full_mapping():
    assert PL_MONTHS_FULL["sierpnia"] == 8
    assert PL_MONTHS_FULL["stycznia"] == 1


def test_guess_year_uses_title_year_if_present():
    assert _guess_year(8, 13, "Bachaturo festiwal 2026") == 2026


def test_guess_year_falls_back_to_future_year_when_past():
    today = date.today()
    past_month = 1 if today.month > 1 else 12
    year = _guess_year(past_month, 1, "Wydarzenie bez roku w tytule")
    assert year >= today.year


def test_safe_date_handles_invalid_day():
    assert _safe_date(2026, 2, 30) is None
    assert _safe_date(2026, 8, 13) == date(2026, 8, 13)


if __name__ == "__main__":
    test_pl_months_abbr_mapping()
    test_pl_months_full_mapping()
    test_guess_year_uses_title_year_if_present()
    test_guess_year_falls_back_to_future_year_when_past()
    test_safe_date_handles_invalid_day()
    print("OK - wszystkie testy przeszly")
