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
    __tablename__ = "survey_responses"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    cities = Column(String(500), nullable=True)          # preferowane miasta, oddzielone przecinkiem
    max_distance_km = Column(Integer, nullable=True)
    styles = Column(String(300), nullable=True)           # sensual, dominicana, urban, festival, social, workshop
    preferred_sources = Column(String(500), nullable=True)  # np. Facebook, bachatastars.pl, Instagram...
    event_types = Column(String(300), nullable=True)      # festiwal, social, warsztaty, wyjazd
    email = Column(String(300), nullable=True)
    comments = Column(Text, nullable=True)
