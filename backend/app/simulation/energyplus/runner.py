"""EnergyPlus runner for building load simulation (8760h)."""

import subprocess
from pathlib import Path

from app.config import settings


class EnergyPlusRunner:
    """Wrapper for EnergyPlus simulation execution."""

    def __init__(self) -> None:
        self.energyplus_path = Path(settings.energyplus_path) if settings.energyplus_path else None

    def validate_installation(self) -> bool:
        """Check if EnergyPlus is available."""
        if not self.energyplus_path or not self.energyplus_path.exists():
            return False
        return True

    async def run_simulation(
        self,
        idf_path: Path,
        weather_path: Path,
        output_dir: Path,
    ) -> dict:
        """
        Run an EnergyPlus simulation.

        Args:
            idf_path: Path to the IDF input file.
            weather_path: Path to the EPW weather file.
            output_dir: Directory for output files.

        Returns:
            Dictionary with simulation results including hourly loads.
        """
        if not self.validate_installation():
            raise RuntimeError(
                "EnergyPlus is not installed or path is not configured. "
                "Set ENERGYPLUS_PATH in environment variables."
            )

        output_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            str(self.energyplus_path / "energyplus"),
            "-w", str(weather_path),
            "-d", str(output_dir),
            "-r",
            str(idf_path),
        ]

        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
        )

        if process.returncode != 0:
            raise RuntimeError(f"EnergyPlus simulation failed: {process.stderr}")

        return self._parse_results(output_dir)

    def _parse_results(self, output_dir: Path) -> dict:
        """Parse EnergyPlus output files and extract hourly loads."""
        # TODO: Parse CSV/ESO output files from EnergyPlus
        # Return hourly cooling/heating loads (8760 hours)
        return {
            "hourly_cooling_load": [],
            "hourly_heating_load": [],
            "total_cooling_load": 0.0,
            "total_heating_load": 0.0,
            "peak_cooling_load": 0.0,
            "peak_heating_load": 0.0,
        }
