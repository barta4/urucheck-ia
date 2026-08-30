import databases
import sqlalchemy
from config import settings

database = databases.Database(
    settings.DATABASE_URL,
    min_size=2,
    max_size=10,
)

try:
    engine = sqlalchemy.create_engine(
        settings.DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://"),
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
except Exception as exc:
    # Graceful fallback for non-Postgres environments or unit tests
    engine = None

metadata = sqlalchemy.MetaData()
