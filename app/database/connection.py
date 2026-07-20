#app/database/connection.py

'''
2026-07-20
db연결
'''

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str


settings = Settings()

engine = create_engine(settings.database_url, echo=True)
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()