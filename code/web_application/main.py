from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

try:
    from .auth_hw4 import router as auth_router
    from .benchmark_hw4 import router as benchmark_router
    from .database import Base, engine
    from .packages_hw5 import router as packages_router
    from .reports_hw4 import router as reports_router
except ImportError:
    from auth_hw4 import router as auth_router
    from benchmark_hw4 import router as benchmark_router
    from database import Base, engine
    from packages_hw5 import router as packages_router
    from reports_hw4 import router as reports_router


# Create any missing tables defined by the SQLAlchemy models.
# Existing tables and columns are handled by the HW5 migration script.
Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="Open-Source Package Vulnerability API",
    version="5.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def measure_sql_statements(request: Request, call_next):
    """Add the actual SQL count to each HTTP response."""
    request.state.sql_count = 0

    response = await call_next(request)

    response.headers["X-SQL-Statements"] = str(
        getattr(request.state, "sql_count", 0)
    )

    return response


# Register all application routers after the FastAPI app exists.
app.include_router(auth_router)
app.include_router(packages_router)
app.include_router(reports_router)
app.include_router(benchmark_router)


@app.get("/health")
def health() -> dict[str, str]:
    """Objective application health check."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8744,
        reload=False,
    )