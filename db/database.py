from sqlalchemy import create_engine


DATABASE_URL =  "sqlite+aiosqlite:///:memory:"
engine = create_engine(DATABASE_URL, echo=True)

