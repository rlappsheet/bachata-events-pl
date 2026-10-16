from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import FastAPI, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import ADMIN_TOKEN, BASE_DIR
from app.database import get_db, init_db
from app.models import Event, SurveyResponse
from app.scraper_runner import run_all_scrapers, get_survey_priorities

app = FastAPI(title="Bachata Events PL")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

STYLE_CHOICES = ["sensual", "dominicana", "urban", "zouk", "kizomba", "salsa"]
EVENT_TYPE_CHOICES = ["festiwal", "social", "warsztaty", "wyjazd/plener"]
SOURCE_CHOICES = ["bachatastars.pl", "Facebook", "Instagram", "Grupy WhatsApp", "Inne (napisz w komentarzu)"]


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
            "source_choices": SOURCE_CHOICES,
            "submitted": False,
        },
    )


@app.post("/ankieta")
def survey_submit(
    request: Request,
    cities: str = Form(""),
    max_distance_km: Optional[int] = Form(None),
    styles: list[str] = Form([]),
    preferred_sources: list[str] = Form([]),
    event_types: list[str] = Form([]),
    email: str = Form(""),
    comments: str = Form(""),
    db: Session = Depends(get_db),
):
    response = SurveyResponse(
        cities=cities.strip(),
        max_distance_km=max_distance_km,
        styles=",".join(styles),
        preferred_sources=",".join(preferred_sources),
        event_types=",".join(event_types),
        email=email.strip() or None,
        comments=comments.strip() or None,
    )
    db.add(response)
    db.commit()

    return templates.TemplateResponse(
        "survey.html",
        {
            "request": request,
            "style_choices": STYLE_CHOICES,
            "event_type_choices": EVENT_TYPE_CHOICES,
            "source_choices": SOURCE_CHOICES,
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
