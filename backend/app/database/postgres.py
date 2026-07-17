from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import create_engine
from app.core.config import get_settings

settings = get_settings()

# Async engine for FastAPI
engine = create_async_engine(settings.DATABASE_URL, echo=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

async def get_db_session():
    async with async_session_maker() as session:
        yield session

# Sync engine for Alembic (which doesn't strictly need it to be sync, but standard async setups use sync for migrations or async env.py. We'll provide it just in case)
sync_engine = create_engine(settings.DATABASE_URL_SYNC)
