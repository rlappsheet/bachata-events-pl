from __future__ import annotations

import json
from datetime import date
from typing import Optional

from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import ADMIN_TOKEN, BASE_DIR, SCRAPE_FRESHNESS_MINUTES
from app.database import get_db, init_db
from app.models import Event, SurveyResponse
from app.scraper_runner import (
    run_all_scrapers,
    get_survey_priorities,
    get_last_scrape_info,
    trigger_background_refresh_if_stale,
)

app = FastAPI(title="Bachata Events PL")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

STYLE_CHOICES = ["sensual", "dominicana", "urban", "zouk", "kizomba", "salsa"]
EVENT_TYPE_CHOICES = ["festiwal", "social", "warsztaty", "wyjazd/plener"]
CITY_CHOICES = ["Warszawa", "Katowice", "Kraków", "Poznań", "Wrocław", "Gdańsk", "Łódź"]
DISTANCE_CHOICES = [
    ("5", "5 km"),
    ("10", "10 km"),
    ("15", "15 km"),
    ("25", "25 km"),
    ("100", "100 km"),
    ("150", "150 km"),
    ("all", "Cała Polska"),
]


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/")
def index(
    request: Request,
    db: Session = Depends(get_db),
    city: Optional[str] = None,
    q: Optional[str] = None,
    show_past: bool = False,
):
    # Dane sa odswiezane w tle, nie przy kazdym requescie synchronicznie -
    # uzytkownik nigdy nie czeka na scraper, ale sprawdzenie "czy jest nowe"
    # odbywa sie przy kazdym wejsciu na strone glowna.
    trigger_background_refresh_if_stale(SCRAPE_FRESHNESS_MINUTES)
    scrape_info = get_last_scrape_info()

    query = db.query(Event)
    if not show_past:
        query = query.filter(or_(Event.date_start >= date.today(), Event.date_start.is_(None)))
    if city:
        query = query.filter(Event.city.ilike(f"%{city}%"))
    if q:
        like = f"%{q}%"
        query = query.filter(or_(Event.title.ilike(like), Event.venue.ilike(like), Event.description.ilike(like)))

    events = query.order_by(Event.date_start.is_(None), Event.date_start.asc()).all()

    cities = sorted({e.city for e in db.query(Event.city).filter(Event.city.isnot(None)).distinct() if e.city})

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "events": events,
            "cities": cities,
            "selected_city": city or "",
            "q": q or "",
            "show_past": show_past,
            "total": len(events),
            "scrape_info": scrape_info,
        },
    )


@app.get("/ankieta")
def survey_form(request: Request):
    return templates.TemplateResponse(
        "survey.html",
        {
            "request": request,
            "style_choices": STYLE_CHOICES,
            "event_type_choices": EVENT_TYPE_CHOICES,
            "city_choices": CITY_CHOICES,
            "distance_choices": DISTANCE_CHOICES,
            "submitted": False,
        },
    )


@app.post("/ankieta")
async def survey_submit(request: Request, db: Session = Depends(get_db)):
    # Formularz jest parsowany recznie (request.form()), nie przez Pydantic/Form(...):
    # pola list (style, linki whatsapp/fb/event) sa dynamiczne (dodawane/usuwane w JS)
    # i opcjonalne puste wartosci liczbowe wczesniej powodowaly błąd walidacji 422
    # (odpowiedź JSON zamiast strony) - recznie parsujemy, zeby to wykluczyc raz na zawsze.
    form = await request.form()

    def _getlist_clean(key: str) -> list[str]:
        return [v.strip() for v in form.getlist(key) if v and v.strip()]

    home_city = (form.get("home_city") or "").strip()
    custom_city = (form.get("custom_city") or "").strip()
    distance_scope = (form.get("distance_scope") or "").strip()

    response = SurveyResponse(
        home_city=home_city or None,
        custom_city=custom_city or None,
        distance_scope=distance_scope or None,
        styles=",".join(_getlist_clean("styles")),
        event_types=",".join(_getlist_clean("event_types")),
        whatsapp_groups=json.dumps(_getlist_clean("whatsapp_groups")),
        facebook_pages=json.dumps(_getlist_clean("facebook_pages")),
        event_pages=json.dumps(_getlist_clean("event_pages")),
        email=(form.get("email") or "").strip() or None,
        comments=(form.get("comments") or "").strip() or None,
    )
    db.add(response)
    db.commit()

    return templates.TemplateResponse(
        "survey.html",
        {
            "request": request,
            "style_choices": STYLE_CHOICES,
            "event_type_choices": EVENT_TYPE_CHOICES,
            "city_choices": CITY_CHOICES,
            "distance_choices": DISTANCE_CHOICES,
            "submitted": True,
        },
    )


@app.get("/api/events")
def api_events(db: Session = Depends(get_db), city: Optional[str] = None):
    query = db.query(Event).filter(or_(Event.date_start >= date.today(), Event.date_start.is_(None)))
    if city:
        query = query.filter(Event.city.ilike(f"%{city}%"))
    events = query.order_by(Event.date_start.asc()).all()
    return [
        {
            "title": e.title,
            "url": e.url,
            "date_start": e.date_start.isoformat() if e.date_start else None,
            "city": e.city,
            "venue": e.venue,
            "styles": e.styles,
            "source": e.source,
        }
        for e in events
    ]


@app.get("/admin/scrape")
def admin_scrape(token: str = ""):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Nieprawidlowy token")
    result = run_all_scrapers()
    return JSONResponse(result)


@app.get("/admin/survey-stats")
def admin_survey_stats(token: str = "", db: Session = Depends(get_db)):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Nieprawidlowy token")
    return get_survey_priorities(db)
