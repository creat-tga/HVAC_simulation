try:
    from app.tasks.simulation_task import run_load_simulation_task, run_energy_simulation_task  # noqa: F401
    __all__ = ["run_load_simulation_task", "run_energy_simulation_task"]
except Exception:
    # Celery/Redis not available — tasks module is still importable
    __all__ = []
