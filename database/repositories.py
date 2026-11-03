from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from core.config import Settings
from database.models import Base
def build_engine(settings: Settings): return create_engine(settings.database_url, pool_pre_ping=True)
def create_session_factory(settings: Settings): return sessionmaker(bind=build_engine(settings), expire_on_commit=False)
def initialize_schema(settings: Settings) -> None: Base.metadata.create_all(build_engine(settings))
