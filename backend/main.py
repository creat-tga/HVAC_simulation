import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import engine, Base, async_session
from app.routers import projects, buildings, simulation, reports, auth, ws
from app.services.auth_service import seed_admin
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
    # Seed admin user
    async with async_session() as session:
        await seed_admin(session)
    yield
    await engine.dispose()


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
