from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.config import settings

db_url = f"postgresql+psycopg://{settings.postgres_user}:{settings.postgres_password}@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
engine = create_async_engine(db_url, echo=False)

async def check_postgres():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
