"""EnergyPlus runner – orchestrates IDF generation, execution and parsing."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from app.config import settings
from app.simulation.energyplus.idf_generator import generate_idf
from app.simulation.energyplus.parser import parse_load_results
from app.simulation.energyplus.weather_utils import find_epw_for_location

log = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]

# Maximum parallel EnergyPlus processes (capped by CPU cores)
_MAX_EP_WORKERS = min(os.cpu_count() or 4, 8)


def _run_single_ep(
    ep_exe: str, idf_content: str, weather_path: str,
) -> tuple[list[float], list[float]]:
    """Run a single EnergyPlus subprocess. Module-level function for pickling."""
    work_dir = Path(tempfile.mkdtemp(prefix="hvac_ep_"))
    try:
        idf_path = work_dir / "in.idf"
        idf_path.write_text(idf_content, encoding="utf-8")

        proc = subprocess.run(
            [ep_exe, "-w", weather_path, "-d", str(work_dir), "-r", str(idf_path)],
            capture_output=True, text=True, timeout=3600,
            cwd=str(work_dir),  # Avoid file locking conflicts between parallel instances
        )

        if proc.returncode != 0:
            err = proc.stderr[:500] if proc.stderr else ""
            # Read EnergyPlus error file for details
            err_file = work_dir / "eplusout.err"
            if err_file.is_file():
                err_content = err_file.read_text(encoding="utf-8", errors="replace")
                # Extract severe/fatal lines
                severe_lines = [
                    l for l in err_content.splitlines()
                    if "** Severe  **" in l or "** Fatal  **" in l
                ]
                err += "\n" + "\n".join(severe_lines[-10:])
            raise RuntimeError(f"EnergyPlus exited with code {proc.returncode}: {err}")

        csv_path = work_dir / "eplusout.csv"
        if not csv_path.is_file():
            raise RuntimeError("EnergyPlus did not produce eplusout.csv")

        return parse_load_results(csv_path, 1)
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


class EnergyPlusRunner:
    """High-level EnergyPlus simulation orchestrator."""

    def __init__(self) -> None:
        self.ep_dir = Path(settings.energyplus_path) if settings.energyplus_path else None
        # Weather files may live next to the EP install or in a project data/ folder
        self._weather_dirs: list[Path] = []
        if self.ep_dir:
            self._weather_dirs.append(self.ep_dir / "WeatherData")
            self._weather_dirs.append(self.ep_dir.parent / "WeatherData")
        # Also look in project-local data/weather/
        self._weather_dirs.append(Path(__file__).resolve().parents[4] / "data" / "weather")

    # ------------------------------------------------------------------
    # Availability checks
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if not self.ep_dir:
            return False
        for name in ("energyplus", "energyplus.exe"):
            if (self.ep_dir / name).is_file():
                return True
        return False

    def _find_weather(self, location: list[str]) -> Path | None:
        epw_path, _ = find_epw_for_location(location, self._weather_dirs)
        return epw_path

    def _ep_exe(self) -> str:
        assert self.ep_dir is not None
        for name in ("energyplus.exe", "energyplus"):
            p = self.ep_dir / name
            if p.is_file():
                return str(p)
        return str(self.ep_dir / "energyplus")

    # ------------------------------------------------------------------
    # Shared preparation logic
    # ------------------------------------------------------------------

    def _prepare_simulation(
        self, zones: dict[str, dict[str, Any]], location: list[str]
    ) -> tuple[str, Path]:
        """Validate inputs, find weather, generate IDF. Returns (idf_content, weather_path)."""
        if not self.is_available():
            raise RuntimeError("EnergyPlus is not installed or not configured")

        weather = self._find_weather(location)
        if weather is None:
            raise RuntimeError(
                f"No EPW weather file found for location {location}. "
                f"Searched: {[str(d) for d in self._weather_dirs]}"
            )

        idf_content = generate_idf(zones, location)
        return idf_content, weather

    def _execute_and_parse(
        self, idf_content: str, weather: Path, num_zones: int
    ) -> tuple[list[float], list[float]]:
        """Write IDF, run EnergyPlus subprocess, parse results. Synchronous."""
        work_dir = Path(tempfile.mkdtemp(prefix="hvac_ep_"))
        try:
            idf_path = work_dir / "in.idf"
            idf_path.write_text(idf_content, encoding="utf-8")
            log.info("EnergyPlus IDF written to %s (%d bytes)", idf_path, len(idf_content))

            proc = subprocess.run(
                [self._ep_exe(), "-w", str(weather), "-d", str(work_dir), "-r", str(idf_path)],
                capture_output=True, text=True, timeout=3600,
                cwd=str(work_dir),
            )

            if proc.returncode != 0:
                err = proc.stderr[:1000] if proc.stderr else ""
                log.error("EnergyPlus failed (rc=%d): %s", proc.returncode, err)
                raise RuntimeError(f"EnergyPlus exited with code {proc.returncode}: {err}")

            csv_path = work_dir / "eplusout.csv"
            if not csv_path.is_file():
                raise RuntimeError("EnergyPlus did not produce eplusout.csv")

            return parse_load_results(csv_path, num_zones)
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Async entry point (used by FastAPI request handlers)
    # ------------------------------------------------------------------

    async def run_load_simulation(
        self,
        zones: dict[str, dict[str, Any]],
        location: list[str],
    ) -> tuple[list[float], list[float]]:
        """Generate IDF -> run EnergyPlus -> return hourly loads [kW]. Async.

        For multi-zone buildings, delegates to the sync parallel implementation.
        """
        return await asyncio.to_thread(
            self.run_load_simulation_sync, zones, location, None
        )

    # ------------------------------------------------------------------
    # Sync entry point (used by Celery worker tasks)
    # ------------------------------------------------------------------

    def run_load_simulation_sync(
        self,
        zones: dict[str, dict[str, Any]],
        location: list[str],
        on_progress: ProgressCallback | None = None,
    ) -> tuple[list[float], list[float]]:
        """Generate IDF -> run EnergyPlus -> return hourly loads [kW]. Synchronous.

        For multi-zone buildings (>1 zone), each zone is simulated in a separate
        EnergyPlus subprocess in parallel, then results are aggregated.
        ``on_progress(percent, message)`` is called at each milestone.
        """
        if on_progress:
            on_progress(15, "正在验证输入并查找天气文件")

        num_zones = len(zones)

        if num_zones <= 1:
            # Single zone: same as before (no parallelism overhead)
            idf_content, weather = self._prepare_simulation(zones, location)
            if on_progress:
                on_progress(20, "IDF文件已生成")
            if on_progress:
                on_progress(30, "正在运行EnergyPlus")
            result = self._execute_and_parse(idf_content, weather, num_zones)
            if on_progress:
                on_progress(70, "EnergyPlus计算完成，正在解析结果")
            return result

        # Multi-zone: parallel execution
        if on_progress:
            on_progress(18, f"正在为{num_zones}个区域生成独立IDF文件")

        if not self.is_available():
            raise RuntimeError("EnergyPlus is not installed or not configured")

        weather = self._find_weather(location)
        if weather is None:
            raise RuntimeError(
                f"No EPW weather file found for location {location}. "
                f"Searched: {[str(d) for d in self._weather_dirs]}"
            )

        # Generate individual IDF for each zone
        zone_idfs: list[str] = []
        for zone_id, zone_data in zones.items():
            single_zone = {zone_id: zone_data}
            idf_content = generate_idf(single_zone, location)
            zone_idfs.append(idf_content)

        if on_progress:
            on_progress(22, f"{num_zones}个IDF文件已生成")

        # Run EnergyPlus in parallel
        workers = min(num_zones, _MAX_EP_WORKERS)
        ep_exe = self._ep_exe()
        weather_str = str(weather)

        if on_progress:
            on_progress(30, f"正在并行运行{num_zones}个EnergyPlus进程（{workers}工作线程）")

        log.info(
            "Starting parallel EnergyPlus: %d zones, %d workers",
            num_zones, workers,
        )

        # Aggregate hourly results
        cooling_agg = [0.0] * 8760
        heating_agg = [0.0] * 8760
        completed = 0

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(_run_single_ep, ep_exe, idf, weather_str): i
                for i, idf in enumerate(zone_idfs)
            }
            for future in as_completed(futures):
                zone_idx = futures[future]
                try:
                    cooling, heating = future.result()
                    for h in range(min(len(cooling), 8760)):
                        cooling_agg[h] += cooling[h]
                        heating_agg[h] += heating[h]
                    completed += 1
                    if on_progress:
                        # Progress from 30 to 70 based on completion ratio
                        pct = 30 + int(40 * completed / num_zones)
                        on_progress(pct, f"已完成 {completed}/{num_zones} 个区域")
                except Exception as exc:
                    log.error("Zone %d simulation failed: %s", zone_idx, exc)
                    raise RuntimeError(
                        f"Zone {zone_idx} EnergyPlus failed: {exc}"
                    ) from exc

        if on_progress:
            on_progress(70, "所有区域EnergyPlus计算完成，正在汇总结果")

        return cooling_agg, heating_agg