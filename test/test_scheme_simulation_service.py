from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace as NS

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.database import Base
from app.models import *  # noqa: F401,F403
from app.models.building import Building
from app.models.project import Project
from app.models.simulation import SimulationResult
from app.services import scheme_simulation_service as service


def test_scheme_task_is_submitted_synchronized_and_aggregated(monkeypatch):
    async def scenario():
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        project_id, building_id, scheme_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        async with session_factory() as db:
            db.add(Project(id=project_id, name="P", location="广东-广州", electricity_pricing={"fixed_price": 1.0}))
            db.add(Building(id=building_id, project_id=project_id, name="B", building_type="office"))
            load = SimulationResult(
                building_id=building_id, simulation_type="load", status="completed",
                hourly_cooling_load=[100.0, 50.0], hourly_heating_load=[0.0, 0.0],
                total_cooling_load=150.0, total_heating_load=0.0,
                peak_cooling_load=100.0, peak_heating_load=0.0,
            )
            db.add(load)
            await db.commit()

            scheme = NS(
                id=scheme_id, building_id=building_id, updated_at=None, safety_margin=1.0,
                subsystems=[NS(id="system-1", combos=[], tower_groups=[])], control_strategy={},
            )

            async def get_scheme(_db, _id):
                return scheme

            async def validate_scheme(_db, _scheme):
                return []

            async def weather(_project, _building):
                return {"dry_bulb_temperature": [30.0, 31.0], "relative_humidity": [50.0, 60.0]}, 10.0

            async def equipment_loader(_db, _ids):
                return {}

            async def start_energy(_payload):
                return {"simulation_id": "engine-1", "status": "pending"}

            monkeypatch.setattr(service.system_scheme_service, "get_scheme", get_scheme)
            monkeypatch.setattr(service.system_scheme_service, "validate_scheme", validate_scheme)
            monkeypatch.setattr(service, "_weather_data", weather)
            monkeypatch.setattr(service.library_service, "load_equipment_by_ids", equipment_loader)
            monkeypatch.setattr(service, "build_multisystem_payload", lambda **_: {
                "meteorology": [{}, {}], "hvac_system": [{"id": "system-1"}], "load_distribution": [{}],
            })
            monkeypatch.setattr(service.multisystem_client, "start_energy", start_energy)
            monkeypatch.setattr(service, "_start_tracking", lambda _id: None)

            created = await service.create_scheme_energy_simulation(db, scheme_id)
            assert created.scheme_id == scheme_id
            assert created.task_id == "engine-1"

            async def progress(_id):
                return {"status": "completed", "progress": {"percentage": 100}}

            async def simple_result(_id):
                return {
                    "status": "completed",
                    "results": {
                        "system-1": [{"power_total": 10.0}, {"power_total": 20.0}],
                        "system-2": [{"power_total": 1.0}, {"power_total": 2.0}],
                    },
                }

            monkeypatch.setattr(service.multisystem_client, "progress", progress)
            monkeypatch.setattr(service.multisystem_client, "simple_result", simple_result)
            completed = await service.synchronize_scheme_energy_result(db, created.id)
            assert completed is not None
            assert completed.status == "completed"
            assert completed.hourly_energy == [11.0, 22.0]
            assert completed.total_energy == 33.0
            assert completed.total_cost == 33.0
            assert completed.total_cooling_load == 150.0
        await engine.dispose()

    asyncio.run(scenario())