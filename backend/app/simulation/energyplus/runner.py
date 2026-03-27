"""EnergyPlus runner – orchestrates IDF generation, execution and parsing."""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.config import settings
from app.simulation.energyplus.idf_generator import generate_idf
from app.simulation.energyplus.parser import parse_load_results

log = logging.getLogger(__name__)

# Climate zone -> standard EPW file basenames (CSWD format)
WEATHER_FILES: dict[str, str] = {
    "severe_cold": "CHN_Heilongjiang.Harbin.509530_CSWD.epw",
    "cold": "CHN_Beijing.Beijing.545110_CSWD.epw",
    "hot_summer_cold_winter": "CHN_Shanghai.Shanghai.583670_CSWD.epw",
    "hot_summer_warm_winter": "CHN_Guangdong.Guangzhou.592870_CSWD.epw",
    "mild": "CHN_Yunnan.Kunming.567780_CSWD.epw",
}


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

    def _find_weather(self, climate_zone: str) -> Path | None:
        basename = WEATHER_FILES.get(climate_zone)
        for d in self._weather_dirs:
            if not d.is_dir():
                continue
            if basename:
                p = d / basename
                if p.is_file():
                    return p
            # Fallback: first .epw containing the climate zone keyword
            for f in d.glob("*.epw"):
                if climate_zone.replace("_", "") in f.stem.lower().replace("_", ""):
                    return f
        return None

    def _ep_exe(self) -> str:
        assert self.ep_dir is not None
        for name in ("energyplus.exe", "energyplus"):
            p = self.ep_dir / name
            if p.is_file():
                return str(p)
        return str(self.ep_dir / "energyplus")

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run_load_simulation(
        self,
        zones: list[dict[str, Any]],
        climate_zone: str,
        building_type: str = "office",
    ) -> tuple[list[float], list[float]]:
        """Generate IDF -> run EnergyPlus -> return hourly loads [kW].

        Raises ``RuntimeError`` on any failure.
        """
        if not self.is_available():
            raise RuntimeError("EnergyPlus is not installed or not configured")

        weather = self._find_weather(climate_zone)
        if weather is None:
            raise RuntimeError(
                f"No EPW weather file found for climate zone '{climate_zone}'. "
                f"Searched: {[str(d) for d in self._weather_dirs]}"
            )

        idf_content = generate_idf(zones, climate_zone, building_type)
        work_dir = Path(tempfile.mkdtemp(prefix="hvac_ep_"))

        try:
            idf_path = work_dir / "in.idf"
            idf_path.write_text(idf_content, encoding="utf-8")
            # DEBUG: export IDF for inspection
            Path(r"C:\myProject\debug_export.idf").write_text(idf_content, encoding="utf-8")
            log.info("EnergyPlus IDF written to %s (%d bytes)", idf_path, len(idf_content))

            def _run_ep() -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [self._ep_exe(), "-w", str(weather), "-d", str(work_dir), "-r", str(idf_path)],
                    capture_output=True, text=True, timeout=3600,
                )

            proc = await asyncio.to_thread(_run_ep)

            if proc.returncode != 0:
                err = proc.stderr[:1000] if proc.stderr else ""
                log.error("EnergyPlus failed (rc=%d): %s", proc.returncode, err)
                raise RuntimeError(f"EnergyPlus exited with code {proc.returncode}: {err}")

            csv_path = work_dir / "eplusout.csv"
            if not csv_path.is_file():
                raise RuntimeError("EnergyPlus did not produce eplusout.csv")

            return parse_load_results(csv_path, len(zones))

        finally:
            shutil.rmtree(work_dir, ignore_errors=True)