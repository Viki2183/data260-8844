from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

try:
    from . import crud_hw4, models, schemas
    from .database import get_db
except ImportError:
    import crud_hw4
    import models
    import schemas
    from database import get_db


router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
)

SESSION_COOKIE_NAME = "hw4_session"


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> models.UserDB:
    """Require a valid server-side session."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    session = crud_hw4.get_active_session(db, token)

    if session is None:
        raise HTTPException(
            status_code=401,
            detail="Login required",
        )

    user = (
        db.query(models.UserDB)
        .filter(models.UserDB.id == session.user_id)
        .first()
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Login required",
        )

    return user


@router.post("/login", response_model=schemas.LoginResponse)
def login(
    payload: schemas.LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate by email/password and issue an opaque cookie token."""
    user = crud_hw4.authenticate_user(
        db,
        email=str(payload.email),
        password=payload.password,
    )

    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )

    session = crud_hw4.create_session(
        db,
        user_id=user.id,
    )

    # The browser stores only the opaque session ID.
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session.id,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=crud_hw4.SESSION_TTL_SECONDS,
    )

    return {
        "message": "logged in",
        "user": user,
    }


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Delete the server-side session and clear the browser cookie."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    crud_hw4.delete_session(db, token)
    response.delete_cookie(SESSION_COOKIE_NAME)

    return {"message": "logged out"}


@router.get("/me", response_model=schemas.MeResponse)
def me(
    user: models.UserDB = Depends(get_current_user),
):
    """Return the authenticated user without exposing a password hash."""
    return {
        "logged_in": True,
        "user": user,
    }
