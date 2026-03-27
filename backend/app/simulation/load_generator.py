"""Synthetic building load generator with zone-level ParamConfig support.

Provides a heat-balance-based fallback when EnergyPlus is not available.
"""

import math
import random
from typing import Any

# ---------------------------------------------------------------------------
# Climate data
# ---------------------------------------------------------------------------

CLIMATE_PROFILES: dict[str, list[float]] = {
    "severe_cold": [-20, -15, -5, 5, 15, 22, 25, 23, 15, 5, -8, -17],
    "cold": [-5, -2, 5, 14, 21, 26, 28, 27, 22, 14, 5, -2],
    "hot_summer_cold_winter": [4, 6, 11, 17, 22, 26, 30, 30, 25, 19, 13, 6],
    "hot_summer_warm_winter": [14, 15, 18, 23, 27, 29, 30, 30, 28, 25, 20, 16],
    "mild": [8, 10, 14, 18, 21, 22, 23, 23, 21, 17, 13, 9],
}

DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

DAILY_PROFILES: dict[str, list[float]] = {
    "office": [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.1, 0.5, 0.9, 1.0, 1.0, 0.95,
        0.5, 0.95, 1.0, 1.0, 0.9, 0.5,
        0.1, 0.0, 0.0, 0.0, 0.0, 0.0,
    ],
    "commercial": [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.0, 0.1, 0.4, 0.7, 0.9, 1.0,
        1.0, 1.0, 1.0, 1.0, 1.0, 0.9,
        0.8, 0.7, 0.5, 0.3, 0.1, 0.0,
    ],
    "hotel": [
        0.5, 0.4, 0.3, 0.3, 0.3, 0.4,
        0.6, 0.8, 0.7, 0.5, 0.4, 0.5,
        0.6, 0.5, 0.5, 0.6, 0.7, 0.8,
        0.9, 1.0, 1.0, 0.9, 0.8, 0.6,
    ],
}

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

# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------

RHO_CP = 1.2 * 1006              # air density * cp  [W*s/(m3*K)]
HEAT_PER_PERSON = 75.0            # sensible heat per occupant [W/person]
SETPOINT_DEADBAND = 6.0           # cooling - heating setpoint gap [degC]

# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def _hour_to_datetime(hour_idx: int) -> tuple[int, int, int, int]:
    """0-based hour -> (month 1-12, dom 1-31, hour 0-23, dow 1-7 Mon=1)."""
    day_of_year = hour_idx // 24
    hour_of_day = hour_idx % 24
    day_of_week = (day_of_year % 7) + 1

    cumulative = 0
    for m, days in enumerate(DAYS_PER_MONTH):
        if day_of_year < cumulative + days:
            return m + 1, day_of_year - cumulative + 1, hour_of_day, day_of_week
        cumulative += days
    return 12, 31, hour_of_day, (364 % 7) + 1


# ---------------------------------------------------------------------------
# ParamConfig resolver
# ---------------------------------------------------------------------------


def _schedule_matches(
    sched: dict[str, Any],
    month: int, dom: int, dow: int, hour: int,
) -> bool:
    sm, sd = sched.get("start_month", 1), sched.get("start_day", 1)
    em, ed = sched.get("end_month", 12), sched.get("end_day", 31)
    start, end, cur = sm * 100 + sd, em * 100 + ed, month * 100 + dom
    if start <= end:
        if not (start <= cur <= end):
            return False
    else:
        if not (cur >= start or cur <= end):
            return False
    days = sched.get("days", [])
    if days and dow not in days:
        return False
    hours = sched.get("hours", [])
    if hours and hour not in hours:
        return False
    return True


def resolve_param(
    param: dict[str, Any] | float | int | None,
    default: float,
    month: int, dom: int, hod: int, dow: int,
) -> float:
    """Resolve a ParamConfig (or raw number) to a concrete value."""
    if param is None:
        return default
    if isinstance(param, (int, float)):
        return float(param)
    fixed_value = param.get("fixed_value", default)
    if param.get("mode", "fixed") == "fixed":
        return fixed_value
    for sched in param.get("schedules", []):
        if _schedule_matches(sched, month, dom, dow, hod):
            return sched.get("value", fixed_value)
    return fixed_value


# ---------------------------------------------------------------------------
# Outdoor temperature synthesis
# ---------------------------------------------------------------------------


def _get_hourly_outdoor_temps(climate_zone: str) -> list[float]:
    avgs = CLIMATE_PROFILES.get(climate_zone, CLIMATE_PROFILES["hot_summer_cold_winter"])
    temps: list[float] = []
    for mi, days in enumerate(DAYS_PER_MONTH):
        avg = avgs[mi]
        nxt = avgs[(mi + 1) % 12]
        for d in range(days):
            base = avg + (nxt - avg) * (d / days) * 0.3
            for h in range(24):
                var = 5.0 * math.sin((h - 6) * math.pi / 12)
                temps.append(round(base + var + random.gauss(0, 0.5), 1))
    return temps[:8760]


# ---------------------------------------------------------------------------
# Zone-based heat-balance calculation
# ---------------------------------------------------------------------------


def _generate_from_zones(
    climate_zone: str,
    zones: list[dict[str, Any]],
) -> tuple[list[float], list[float]]:
    random.seed(42)
    outdoor = _get_hourly_outdoor_temps(climate_zone)
    hc = [0.0] * 8760
    hh = [0.0] * 8760

    for zone in zones:
        area = zone.get("area", 100.0)
        fh = zone.get("floor_height", 3.0)
        wall_u = zone.get("wall_u_value", 1.0)
        win_u = zone.get("window_u_value", 3.0)
        wwr = zone.get("window_wall_ratio", 0.4)
        roof_u = zone.get("roof_u_value", 0.8)

        side = math.sqrt(area)
        ext_wall = 4.0 * side * fh
        win_a = ext_wall * wwr
        ua = wall_u * (ext_wall - win_a) + win_u * win_a + roof_u * area

        for i in range(8760):
            mo, dom, hod, dow = _hour_to_datetime(i)
            t_out = outdoor[i]

            t_cool = resolve_param(zone.get("temperature"), 26.0, mo, dom, hod, dow)
            t_heat = t_cool - SETPOINT_DEADBAND

            ppl = resolve_param(zone.get("people_density"), 0.0, mo, dom, hod, dow)
            lgt = resolve_param(zone.get("lighting_density"), 0.0, mo, dom, hod, dow)
            eqp = resolve_param(zone.get("equipment_density"), 0.0, mo, dom, hod, dow)
            fav = resolve_param(zone.get("fresh_air_volume"), 0.0, mo, dom, hod, dow)

            q_int = (ppl * HEAT_PER_PERSON + lgt + eqp) * area
            v_dot = fav * ppl * area / 3600.0

            if t_out > t_cool:
                q_env = ua * (t_out - t_cool)
                q_vent = RHO_CP * v_dot * (t_out - t_cool)
                load = (q_env + q_vent + q_int) / 1000.0
                hc[i] += max(0.0, round(load, 3))
            elif t_out < t_heat:
                q_env = ua * (t_out - t_heat)
                q_vent = RHO_CP * v_dot * (t_out - t_heat)
                net = q_env + q_vent + q_int
                if net < 0:
                    hh[i] += round(abs(net) / 1000.0, 3)
            else:
                q_env = ua * (t_out - t_cool)
                q_vent = RHO_CP * v_dot * (t_out - t_cool)
                net = q_env + q_vent + q_int
                if net > 0:
                    hc[i] += round(net / 1000.0, 3)

    return hc, hh


# ---------------------------------------------------------------------------
# Legacy whole-building calculation (backward compat, no zone data)
# ---------------------------------------------------------------------------


def _generate_legacy(
    building_type: str,
    total_area: float,
    climate_zone: str,
    envelope_params: dict[str, Any] | None = None,
) -> tuple[list[float], list[float]]:
    random.seed(42)
    ci, hi = BUILDING_LOAD_INTENSITY.get(building_type, BUILDING_LOAD_INTENSITY["other"])

    if envelope_params:
        wu = envelope_params.get("wall_u_value", 1.0)
        wiu = envelope_params.get("window_u_value", 3.0)
        wwr = envelope_params.get("window_wall_ratio", 0.4)
        ru = envelope_params.get("roof_u_value", 0.8)
        ppl = envelope_params.get("people_density", 0.1)
        lgt = envelope_params.get("lighting_density", 10.0)
        eqp = envelope_params.get("equipment_density", 15.0)
        ef = (wu * (1 - wwr) + wiu * wwr + ru * 0.3) / (1.0 * 0.6 + 3.0 * 0.4 + 0.8 * 0.3)
        fi = (ppl * 75 + lgt + eqp) / 32.5
        ci *= ef * 0.5 + fi * 0.5
        hi *= ef

    pk_c = ci * total_area / 1000.0
    pk_h = hi * total_area / 1000.0
    outdoor = _get_hourly_outdoor_temps(climate_zone)
    profile = DAILY_PROFILES.get(building_type, DAILY_PROFILES["office"])

    hc: list[float] = []
    hh: list[float] = []
    for i in range(8760):
        t, occ = outdoor[i], profile[i % 24]
        hc.append(round(pk_c * min(1.0, max(0.0, t - 26.0) / 12.0) * occ, 2) if t > 26.0 else 0.0)
        hh.append(round(pk_h * min(1.0, max(0.0, 18.0 - t) / 25.0) * occ, 2) if t < 18.0 else 0.0)
    return hc, hh


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_hourly_loads(
    building_type: str,
    total_area: float,
    climate_zone: str,
    zones: list[dict[str, Any]] | None = None,
    envelope_params: dict[str, Any] | None = None,
) -> tuple[list[float], list[float]]:
    """Generate 8760 hourly cooling / heating loads [kW].

    Uses the zone-level heat-balance model when *zones* is provided,
    otherwise falls back to the legacy intensity-based model.
    """
    if zones:
        return _generate_from_zones(climate_zone, zones)
    return _generate_legacy(building_type, total_area, climate_zone, envelope_params)