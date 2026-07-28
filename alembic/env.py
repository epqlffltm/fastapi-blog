import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# 앱의 Base와 모델을 가져온다.
# orm을 import해야 모든 테이블이 Base.metadata에 등록된다.
from app.database import orm  # noqa: F401
from app.database.connection import Base


load_dotenv()

config = context.config


def _to_async_url(url: str) -> str:
    """앱과 동일하게 PostgreSQL 연결 URL을 asyncpg 드라이버로 정규화한다."""
    if url.startswith("postgresql+psycopg://"):
        return url.replace(
            "postgresql+psycopg://",
            "postgresql+asyncpg://",
            1,
        )
    if url.startswith("postgresql://"):
        return url.replace(
            "postgresql://",
            "postgresql+asyncpg://",
            1,
        )
    return url


# alembic.ini에 URL을 하드코딩하지 않고 환경변수의 DATABASE_URL을 사용한다.
# Windows의 기본 ProactorEventLoop와 psycopg 비동기 연결은 호환되지 않으므로,
# 앱 런타임과 동일하게 asyncpg URL로 정규화한다.
database_url = _to_async_url(os.environ["DATABASE_URL"])

# ConfigParser의 % 보간과 비밀번호의 % 문자가 충돌하지 않도록 이스케이프한다.
config.set_main_option(
    "sqlalchemy.url",
    database_url.replace("%", "%%"),
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """DB 연결 없이 SQL만 생성하는 오프라인 마이그레이션을 실행한다."""
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """AsyncConnection의 동기 어댑터 안에서 Alembic 마이그레이션을 실행한다."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """asyncpg용 AsyncEngine을 생성해 온라인 마이그레이션을 실행한다."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Alembic의 동기 진입점에서 비동기 마이그레이션을 실행한다."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()