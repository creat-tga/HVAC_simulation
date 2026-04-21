import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base, async_session
from app.routers import projects, buildings, simulation, reports, auth, ws
from app.routers import admin as admin_router
from app.routers import library as library_router
from app.services.auth_service import seed_admin
from app.services.library_service import seed_preset_weather
from app.simulation.energyplus.idf_generator import ZoneValidationError

# Configure logging — reduce noise from libraries
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# Suppress noisy loggers
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("aiosqlite").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic for production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # SQLite-only: lightweight column additions for existing user table
        if settings.database_url.startswith("sqlite"):
            await _sqlite_migrate_users(conn)
            await _sqlite_migrate_hvac_systems(conn)
    # Seed admin user + preset weather files
    async with async_session() as session:
        await seed_admin(session)
        try:
            await seed_preset_weather(session)
        except Exception as exc:
            logging.getLogger(__name__).warning("Seed weather failed: %s", exc)
    yield
    await engine.dispose()


async def _sqlite_migrate_users(conn) -> None:
    """Add new columns to users table on legacy SQLite installs."""
    from sqlalchemy import text
    res = await conn.execute(text("PRAGMA table_info(users)"))
    cols = {row[1] for row in res.fetchall()}
    statements = []
    if "email" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN email VARCHAR(200)")
    if "full_name" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN full_name VARCHAR(200)")
    if "role" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN role VARCHAR(20) NOT NULL DEFAULT 'user'")
    if "status" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
    if "last_login_at" not in cols:
        statements.append("ALTER TABLE users ADD COLUMN last_login_at DATETIME")
    for sql in statements:
        await conn.execute(text(sql))


async def _sqlite_migrate_hvac_systems(conn) -> None:
    """Drop & recreate hvac_systems if the schema diverges from the model.

    Legacy installs may have an older table without the building_id column,
    which causes OperationalError on relationship loads / cascade deletes.
    Since this table only stores derived runtime data, dropping is safe.
    """
    from sqlalchemy import text
    res = await conn.execute(text("PRAGMA table_info(hvac_systems)"))
    rows = res.fetchall()
    if not rows:
        return  # table absent; create_all will handle it
    cols = {row[1] for row in rows}
    if "building_id" not in cols:
        await conn.execute(text("DROP TABLE hvac_systems"))
        # Recreate via metadata (idempotent)
        from app.models.simulation import HVACSystem  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)


app = FastAPI(
    title=settings.app_name,
    description="HVAC系统仿真平台 — 建筑负荷模拟与系统能耗分析",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")
app.include_router(admin_router.me_router, prefix="/api")
app.include_router(library_router.weather_router, prefix="/api")
app.include_router(library_router.equipment_router, prefix="/api")
app.include_router(library_router.template_router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(buildings.router, prefix="/api")
app.include_router(simulation.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(ws.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    from app.utils.redis_check import is_redis_available
    return {
        "status": "ok",
        "app": settings.app_name,
        "redis_available": is_redis_available(),
    }


@app.exception_handler(ZoneValidationError)
async def zone_validation_handler(request: Request, exc: ZoneValidationError):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})
