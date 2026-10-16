from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, Date, DateTime, UniqueConstraint

from app.database import Base


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_source_event"),)

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(64), nullable=False, index=True)
    source_id = Column(String(255), nullable=False)
    title = Column(String(500), nullable=False)
    url = Column(String(1000), nullable=False)
    date_start = Column(Date, nullable=True, index=True)
    date_end = Column(Date, nullable=True)
    time_text = Column(String(100), nullable=True)
    city = Column(String(200), nullable=True, index=True)
    country = Column(String(200), nullable=True)
    venue = Column(String(300), nullable=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(1000), nullable=True)
    category = Column(String(500), nullable=True)
    styles = Column(String(300), nullable=True)  # np. sensual,dominicana,urban - uzupelniane heurystycznie
    external_website = Column(String(1000), nullable=True)
    scraped_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SurveyResponse(Base):
    """Ankieta dopasowania skrapera.

    `home_city`/`custom_city` + `distance_scope` mówią nam, z jakiego miasta
    liczyć odległość i jak daleko użytkownik jest skłonny jeździć - to
    zastępuje poprzednie, niejednoznaczne wolne pole "cities".

    `whatsapp_groups` / `facebook_pages` / `event_pages` to listy linków
    (serializowane jako JSON) dodawane/usuwane dynamicznie w formularzu -
    każdy wpis to potencjalne nowe źródło do dopisania do skrapera.
    """

    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    home_city = Column(String(100), nullable=True)      # np. "Warszawa" albo "inne"
    custom_city = Column(String(200), nullable=True)     # wypełniane gdy home_city == "inne"
    distance_scope = Column(String(20), nullable=True)   # "5"|"10"|"15"|"25"|"100"|"150"|"all"

    styles = Column(String(300), nullable=True)           # sensual, dominicana, urban, festival, social, workshop
    event_types = Column(String(300), nullable=True)      # festiwal, social, warsztaty, wyjazd

    whatsapp_groups = Column(Text, nullable=True)  # JSON: ["https://chat.whatsapp.com/..."]
    facebook_pages = Column(Text, nullable=True)   # JSON: ["https://facebook.com/..."]
    event_pages = Column(Text, nullable=True)      # JSON: ["https://..."] - inne strony z eventami

    email = Column(String(300), nullable=True)
    comments = Column(Text, nullable=True)


class ScrapeRun(Base):
    """Historia uruchomień skrapera - pokazywana na stronie głównej jako
    'ostatnia aktualizacja bazy' i używana do decyzji o odświeżeniu w tle."""

    __tablename__ = "scrape_runs"

    id = Column(Integer, primary_key=True, index=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), default="running")  # running | ok | error
    events_found = Column(Integer, default=0)
    events_created = Column(Integer, default=0)
    events_updated = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
