import sys
from getpass import getpass

from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(__file__))

from database import Base, engine, db_session_basede26
from crud_hw4 import create_user
from schemas import UserCreate
import models


def main() -> None:
    """Create one local test user without saving the plaintext password."""
    Base.metadata.create_all(bind=engine)

    name = input("Name: ").strip()
    email = input("Email: ").strip().lower()
    password = getpass("Password: ")

    db = db_session_basede26()

    try:
        user = create_user(
            db,
            UserCreate(
                name=name,
                email=email,
                password=password,
            ),
        )
        print(f"Created user ID: {user.id}")
        print(f"Created user email: {user.email}")
    except IntegrityError:
        db.rollback()
        print("A user with that email already exists.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
