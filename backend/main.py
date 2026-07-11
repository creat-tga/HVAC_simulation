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
from app.routers import system_scheme as scheme_router
from app.services.auth_service import seed_admin
from app.services.scheme_simulation_service import resume_scheme_energy_tasks, shutdown_scheme_energy_tasks
# Library seeding (weather / equipment) is no longer auto-run on startup.
# Use scripts/seed_weather.py and scripts/seed_equipment.py manually.
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
            # Legacy user columns are additive. All structural migrations,
            # especially scheme/simulation changes, are handled by Alembic.
            await _sqlite_migrate_users(conn)
    # Seed admin user only. Weather/equipment seeding lives in scripts/.
    async with async_session() as session:
        await seed_admin(session)
    await resume_scheme_energy_tasks()
    try:
        yield
    finally:
        await shutdown_scheme_energy_tasks()
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
app.include_router(scheme_router.router, prefix="/api")
app.include_router(scheme_router.scheme_router, prefix="/api")
app.include_router(scheme_router.eq_search_router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(ws.router, prefix="/api")


@app.get("/api/health")
async def health_check():
    import asyncio
    from app.integrations.multisystem_client import MultiSystemClientError, multisystem_client
    from app.utils.redis_check import is_redis_available

    try:
        engine_health = await multisystem_client.health()
        multisystem_available = engine_health.get("status") == "ok"
    except MultiSystemClientError:
        multisystem_available = False
    redis_available = await asyncio.to_thread(is_redis_available)
    return {
        "status": "ok" if multisystem_available else "degraded",
        "app": settings.app_name,
        "redis_available": redis_available,
        "multisystem_available": multisystem_available,
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
