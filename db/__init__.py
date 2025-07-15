from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

DATABASE_URL =  "sqlite+aiosqlite:///:memory:"

engine = create_engine(DATABASE_URL, echo=True)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def getsession():
    async with SessionLocal() as session:
        yield session

