#app/database/connection.py

'''
2026-07-20
db연결

2026-07-23
Settings에 필드 추가
'''

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    redis_host: str = "127.0.0.1"   # 추가
    redis_port: int = 6379          # 추가


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