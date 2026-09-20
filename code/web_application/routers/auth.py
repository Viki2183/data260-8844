import time
from pathlib import Path

from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND


# Locate the web_application directory from routers/auth.py.
WEB_ROOT = Path(__file__).resolve().parent.parent

# Load HTML files from web_application/templates.
templates = Jinja2Templates(
    directory=str(WEB_ROOT / "templates")
)

# Create a separate router for authentication-related routes.
router = APIRouter()

# Demo credentials for this homework.
VALID_USERNAME = "admin"
VALID_PASSWORD = "password"

# The user must be active within this many seconds.
IDLE_TIMEOUT_SECONDS = 900


def get_active_user(request: Request) -> str | None:
    """
    Return the logged-in username if the session is still active.

    The last_activity value is refreshed whenever the user visits
    a protected or authentication-related page.
    """
    username = request.session.get("user")
    last_activity = request.session.get("last_activity")

    if not username or not last_activity:
        return None

    try:
        elapsed_time = time.time() - float(last_activity)
    except (TypeError, ValueError):
        request.session.clear()
        return None

    if elapsed_time > IDLE_TIMEOUT_SECONDS:
        request.session.clear()
        return None

    # Refresh the idle timer after successful activity.
    request.session["last_activity"] = time.time()

    return str(username)


@router.get("/")
async def home(request: Request):
    """Display the domain application's home page."""
    user = get_active_user(request)

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"user": user},
    )


@router.get("/login")
async def login_page(request: Request):
    """Display the login form."""
    user = get_active_user(request)

    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "user": user,
            "error": None,
        },
    )


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    """Validate credentials and create a session for valid users."""
    if username == VALID_USERNAME and password == VALID_PASSWORD:
        request.session["user"] = username
        request.session["last_activity"] = time.time()

        return RedirectResponse(
            url="/dashboard",
            status_code=HTTP_302_FOUND,
        )

    # Render the login page again with a Bootstrap alert message.
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "user": None,
            "error": "Invalid username or password.",
        },
        status_code=401,
    )


@router.get("/dashboard")
async def dashboard(request: Request):
    """Display the protected dashboard only to active users."""
    user = get_active_user(request)

    if user is None:
        return RedirectResponse(
            url="/login",
            status_code=HTTP_302_FOUND,
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"user": user},
    )


@router.get("/logout")
async def logout(request: Request):
    """Destroy the session and return the user to the home page."""
    request.session.clear()

    return RedirectResponse(
        url="/",
        status_code=HTTP_302_FOUND,
    )