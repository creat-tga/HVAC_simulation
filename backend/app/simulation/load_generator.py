"""Synthetic building load generator for 8760 hourly simulation."""

import math
import random

# Climate zone outdoor temperature profiles (monthly avg in °C)
CLIMATE_PROFILES: dict[str, list[float]] = {
    "severe_cold": [-20, -15, -5, 5, 15, 22, 25, 23, 15, 5, -8, -17],
    "cold": [-5, -2, 5, 14, 21, 26, 28, 27, 22, 14, 5, -2],
    "hot_summer_cold_winter": [4, 6, 11, 17, 22, 26, 30, 30, 25, 19, 13, 6],
    "hot_summer_warm_winter": [14, 15, 18, 23, 27, 29, 30, 30, 28, 25, 20, 16],
    "mild": [8, 10, 14, 18, 21, 22, 23, 23, 21, 17, 13, 9],
}

# Building type load intensity (W/m²) — peak cooling / peak heating
BUILDING_LOAD_INTENSITY: dict[str, tuple[float, float]] = {
    "office": (120.0, 80.0),
    "commercial": (150.0, 70.0),
    "hotel": (130.0, 90.0),
    "hospital": (160.0, 100.0),
    "school": (100.0, 75.0),
    "residential": (80.0, 65.0),
    "industrial": (100.0, 60.0),
    "other": (110.0, 75.0),
}

# Daily load profile multipliers (24 hours) for different building types
DAILY_PROFILES: dict[str, list[float]] = {
    "office": [
        0.1, 0.1, 0.1, 0.1, 0.1, 0.15,
        0.4, 0.7, 0.9, 1.0, 1.0, 0.95,
        0.7, 0.95, 1.0, 1.0, 0.9, 0.6,
        0.3, 0.15, 0.1, 0.1, 0.1, 0.1,
    ],
    "commercial": [
        0.1, 0.1, 0.1, 0.1, 0.1, 0.1,
        0.2, 0.4, 0.7, 0.9, 1.0, 1.0,
        1.0, 1.0, 1.0, 1.0, 1.0, 0.9,
        0.8, 0.7, 0.5, 0.3, 0.15, 0.1,
    ],
    "hotel": [
        0.5, 0.4, 0.3, 0.3, 0.3, 0.4,
        0.6, 0.8, 0.7, 0.5, 0.4, 0.5,
        0.6, 0.5, 0.5, 0.6, 0.7, 0.8,
        0.9, 1.0, 1.0, 0.9, 0.8, 0.6,
    ],
}

COOLING_SETPOINT = 26.0  # °C
HEATING_SETPOINT = 18.0  # °C


def _get_hourly_outdoor_temps(climate_zone: str) -> list[float]:
    """Generate 8760 hourly outdoor temperatures from monthly averages."""
    monthly_avgs = CLIMATE_PROFILES.get(climate_zone, CLIMATE_PROFILES["hot_summer_cold_winter"])
    temps = []
    days_per_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    for month_idx, days in enumerate(days_per_month):
        avg = monthly_avgs[month_idx]
        # Smooth transition with next month
        next_avg = monthly_avgs[(month_idx + 1) % 12]

        for day in range(days):
            day_fraction = day / days
            base = avg + (next_avg - avg) * day_fraction * 0.3

            for hour in range(24):
                # Daily temperature variation: cooler at night, warmer in afternoon
                daily_var = 5.0 * math.sin((hour - 6) * math.pi / 12)
                noise = random.gauss(0, 0.5)
                temps.append(round(base + daily_var + noise, 1))

    return temps[:8760]


def generate_hourly_loads(
    building_type: str,
    total_area: float,
    climate_zone: str,
    envelope_params: dict | None = None,
) -> tuple[list[float], list[float]]:
    """
    Generate 8760 hourly cooling and heating loads for a building.

    Args:
        building_type: Type of building (office, commercial, etc.)
        total_area: Total building area in m²
        climate_zone: Climate zone identifier
        envelope_params: Optional dict with envelope/internal gains parameters

    Returns:
        Tuple of (hourly_cooling_load, hourly_heating_load) in kW
    """
    random.seed(42)  # Reproducible results

    cooling_intensity, heating_intensity = BUILDING_LOAD_INTENSITY.get(
        building_type, BUILDING_LOAD_INTENSITY["other"]
    )

    # Apply envelope parameter adjustments if provided
    if envelope_params:
        # Wall U-value adjustment (default ~1.0 W/m²K for baseline)
        wall_u = envelope_params.get("wall_u_value", 1.0)
        # Window U-value adjustment (default ~3.0 W/m²K)
        window_u = envelope_params.get("window_u_value", 3.0)
        # Window-wall ratio (default 0.4)
        wwr = envelope_params.get("window_wall_ratio", 0.4)
        # Roof U-value (default ~0.8 W/m²K)
        roof_u = envelope_params.get("roof_u_value", 0.8)
        # Internal gains: people density (person/m²), default 0.1
        people_density = envelope_params.get("people_density", 0.1)
        # Lighting power density (W/m²), default 10
        lighting_density = envelope_params.get("lighting_density", 10.0)
        # Equipment power density (W/m²), default 15
        equipment_density = envelope_params.get("equipment_density", 15.0)

        # Compute adjustment factor based on envelope & internal gains
        # Higher U-values mean more heat transfer -> higher loads
        envelope_factor = (wall_u * (1 - wwr) + window_u * wwr + roof_u * 0.3) / (1.0 * 0.6 + 3.0 * 0.4 + 0.8 * 0.3)
        # Internal gains factor (default internal_gain = 0.1*75 + 10 + 15 = 32.5 W/m²)
        internal_gain = people_density * 75 + lighting_density + equipment_density
        internal_factor = internal_gain / 32.5

        cooling_intensity = cooling_intensity * (envelope_factor * 0.5 + internal_factor * 0.5)
        heating_intensity = heating_intensity * envelope_factor

    # Peak loads in kW
    peak_cooling = cooling_intensity * total_area / 1000.0
    peak_heating = heating_intensity * total_area / 1000.0

    outdoor_temps = _get_hourly_outdoor_temps(climate_zone)
    daily_profile = DAILY_PROFILES.get(building_type, DAILY_PROFILES["office"])

    hourly_cooling = []
    hourly_heating = []

    for hour_idx in range(8760):
        t_outdoor = outdoor_temps[hour_idx]
        hour_of_day = hour_idx % 24
        occupancy = daily_profile[hour_of_day]

        # Cooling load — proportional to temperature difference above setpoint
        if t_outdoor > COOLING_SETPOINT:
            dt = t_outdoor - COOLING_SETPOINT
            load_ratio = min(1.0, dt / 12.0)  # Normalize to ~12°C range
            cooling = peak_cooling * load_ratio * occupancy
        else:
            cooling = 0.0

        # Heating load — proportional to temperature difference below setpoint
        if t_outdoor < HEATING_SETPOINT:
            dt = HEATING_SETPOINT - t_outdoor
            load_ratio = min(1.0, dt / 25.0)  # Normalize to ~25°C range
            heating = peak_heating * load_ratio * occupancy
        else:
            heating = 0.0

        hourly_cooling.append(round(cooling, 2))
        hourly_heating.append(round(heating, 2))

    return hourly_cooling, hourly_heating
