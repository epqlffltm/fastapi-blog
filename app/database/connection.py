#app/database/connection.py

'''
2026-07-20
db연결

2026-07-23
Settings에 필드 추가

2026-07-24
쿠키 설정 추가

2026-07-27
async 전환 (asyncpg) / echo 를 설정으로

2026-07-28
업로드 이미지 크기 제한 설정 추가
'''

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    redis_host: str = "127.0.0.1"
    redis_port: int = 6379
    smtp_host: str = "smtp.gmail.com"      # 추가
    smtp_port: int = 587                    # 추가
    smtp_user: str = ""                     # 추가
    smtp_password: str = ""                 # 추가
    cookie_secure: bool = False    # 추가: 배포(HTTPS)에서 true
    cookie_max_age: int = 86400
    upload_max_bytes: int = 5 * 1024 * 1024
    upload_max_width: int = 10_000
    upload_max_height: int = 10_000
    upload_max_pixels: int = 25_000_000
    db_echo: bool = False    # 배포에선 False, 로컬 디버깅 때만 True


settings = Settings()


# psycopg(동기) URL 이 들어와도 asyncpg(비동기) 드라이버로 바꿔 쓴다.
# .env 를 postgresql+asyncpg://... 로 바꿔도 되지만, 안전하게 코드에서도 보정
def _to_async_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


engine = create_async_engine(_to_async_url(settings.database_url), echo=settings.db_echo)
SessionFactory = async_sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


# async 의존성 — 요청마다 AsyncSession 을 열고, 끝나면 닫는다
async def get_db():
    async with SessionFactory() as session:
        yield session