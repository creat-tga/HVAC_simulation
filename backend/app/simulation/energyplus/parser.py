"""Parse EnergyPlus CSV output files to extract hourly zone loads."""

from __future__ import annotations

import csv
from pathlib import Path


def parse_load_results(
    csv_path: Path,
    num_zones: int = 1,
) -> tuple[list[float], list[float]]:
    """Read *eplusout.csv* and return aggregated hourly cooling / heating [kW].

    EnergyPlus reports ideal-loads energy in **Joules per timestep**.
    For Timestep=1 (hourly), power [kW] = energy [J] / 3 600 000.

    Returns
    -------
    (hourly_cooling, hourly_heating) : tuple[list[float], list[float]]
        Each has 8760 values in kW.
    """
    J_TO_KW = 3_600_000.0

    cooling_cols: list[int] = []
    heating_cols: list[int] = []
    hourly_cooling = [0.0] * 8760
    hourly_heating = [0.0] * 8760

    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)

        for idx, col in enumerate(header):
            upper = col.upper()
            if "IDEAL LOADS" in upper and "COOLING" in upper and "ENERGY" in upper:
                cooling_cols.append(idx)
            elif "IDEAL LOADS" in upper and "HEATING" in upper and "ENERGY" in upper:
                heating_cols.append(idx)

        if not cooling_cols and not heating_cols:
            raise RuntimeError(
                "EnergyPlus CSV does not contain ideal-loads columns. "
                f"Header sample: {header[:10]}"
            )

        for row_idx, row in enumerate(reader):
            if row_idx >= 8760:
                break
            for ci in cooling_cols:
                try:
                    hourly_cooling[row_idx] += float(row[ci]) / J_TO_KW
                except (ValueError, IndexError):
                    pass
            for hi in heating_cols:
                try:
                    hourly_heating[row_idx] += float(row[hi]) / J_TO_KW
                except (ValueError, IndexError):
                    pass

    hourly_cooling = [round(v, 2) for v in hourly_cooling]
    hourly_heating = [round(v, 2) for v in hourly_heating]
    return hourly_cooling, hourly_heating
