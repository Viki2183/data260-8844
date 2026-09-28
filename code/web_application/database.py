from pathlib import Path
import os

from dotenv import load_dotenv
from fastapi import Request
from sqlalchemy import URL, create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker


ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)


DB_HOST = os.environ["DB_HOST"]
DB_PORT = int(os.environ["DB_PORT"])
DB_USER = os.environ["DB_USER"]
DB_PASSWORD = os.environ["DB_PASSWORD"]
DB_NAME = os.environ["DB_NAME"]


DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
)


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)


@event.listens_for(engine, "before_cursor_execute")
def count_sql_statements(
    connection,
    cursor,
    statement,
    parameters,
    context,
    executemany,
):
    """Count statements and attach the count to the active request."""
    request = connection.info.get("hw4_request")

    if request is None:
        return

    count = connection.info.get("hw4_sql_count", 0) + 1
    connection.info["hw4_sql_count"] = count
    request.state.sql_count = count


# Required HW4 variable name.
db_session_basede26 = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


Base = declarative_base()


def get_db(request: Request):
    """Provide one request-associated database session."""
    request.state.sql_count = 0

    db = db_session_basede26()

    # Check out the connection and associate it with this HTTP request.
    connection = db.connection()
    connection.info["hw4_request"] = request
    connection.info["hw4_sql_count"] = 0

    try:
        yield db
    finally:
        db.close()
