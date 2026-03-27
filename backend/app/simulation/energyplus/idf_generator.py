"""Generate EnergyPlus IDF files from BuildingZone data.

Produces a complete IDF suitable for zone-level ideal-loads simulation.
Each zone gets a shoebox geometry, auto-generated constructions from U-values,
and schedules derived from ``ParamConfig``.
"""

from __future__ import annotations

import math
from typing import Any

# ---------------------------------------------------------------------------
# Climate zone → representative location
# ---------------------------------------------------------------------------

CLIMATE_ZONE_LOCATIONS: dict[str, dict[str, Any]] = {
    "severe_cold": {"name": "Harbin",    "lat": 45.75, "lon": 126.77, "tz": 8, "elev": 142.3},
    "cold":        {"name": "Beijing",   "lat": 39.93, "lon": 116.28, "tz": 8, "elev": 32.0},
    "hot_summer_cold_winter": {"name": "Shanghai", "lat": 31.17, "lon": 121.43, "tz": 8, "elev": 7.0},
    "hot_summer_warm_winter": {"name": "Guangzhou", "lat": 23.13, "lon": 113.32, "tz": 8, "elev": 41.0},
    "mild":        {"name": "Kunming",   "lat": 25.02, "lon": 102.68, "tz": 8, "elev": 1892.4},
}

SETPOINT_DEADBAND = 6.0  # cooling – heating gap [°C]
FILM_R_INT = 0.12   # interior surface film [m²·K/W]
FILM_R_EXT = 0.04   # exterior surface film

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sn(name: str) -> str:
    """Sanitise a name for IDF fields."""
    return name.replace(" ", "_").replace(",", "").replace(";", "").replace("!", "")[:40]


def _vstr(x: float, y: float, z: float) -> str:
    return f"  {x:.4f}, {y:.4f}, {z:.4f}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_idf(
    zones: list[dict[str, Any]],
    climate_zone: str,
    building_type: str = "office",
) -> str:
    """Return a complete IDF string for EnergyPlus ideal-loads simulation."""
    parts: list[str] = [
        _global_version(),
        _global_sim_control(),
        _global_building(building_type),
        _global_timestep(),
        _global_run_period(),
        _global_location(climate_zone),
        _global_geometry_rules(),
        _global_schedule_types(),
        _constant_schedules(),
    ]

    x_offset = 0.0
    zone_names: list[str] = []
    for idx, zone in enumerate(zones):
        zn = _sn(zone.get("name", f"Zone_{idx + 1}"))
        zone_names.append(zn)
        area = zone.get("area", 100.0)
        fh = zone.get("floor_height", 3.0)
        side = math.sqrt(area)

        parts.append(_zone_object(zn, x_offset))
        parts.append(_materials_constructions(zn, zone))
        parts.append(_zone_geometry(zn, side, side, fh, zone.get("window_wall_ratio", 0.4), x_offset))

        # Schedules
        sched_map: dict[str, str] = {}
        for key in ("people_density", "lighting_density", "equipment_density",
                     "fresh_air_volume", "temperature"):
            sn = f"{zn}_{key}"
            val = zone.get(key)
            # Temperature default = 26°C if not specified
            if key == "temperature" and val is None:
                val = 26.0
            parts.append(_param_config_schedule(sn, val))
            sched_map[key] = sn

        # Heating setpoint = cooling – deadband
        ht_sn = f"{zn}_heating_sp"
        temp_val = zone.get("temperature")
        if temp_val is None:
            temp_val = 26.0
        parts.append(_offset_schedule(ht_sn, temp_val, -SETPOINT_DEADBAND))
        sched_map["heating_sp"] = ht_sn

        # Internal gains
        parts.append(_people(zn, area, sched_map["people_density"]))
        parts.append(_lights(zn, area, sched_map["lighting_density"]))
        parts.append(_equipment(zn, area, sched_map["equipment_density"]))

        # Outdoor air — oa_per_person already in m³/s, schedule = Always_On (no extra multiplier)
        oa_per_person = _fixed_val(zone.get("fresh_air_volume"), 30.0) / 3600.0
        parts.append(_outdoor_air_spec(zn, oa_per_person, "Always_On"))

        # Ideal loads HVAC + thermostat + equipment connections
        parts.append(_thermostat(zn, sched_map["temperature"], sched_map["heating_sp"]))
        parts.append(_ideal_loads(zn))
        parts.append(_zone_equipment(zn))

        x_offset += side + 5.0

    parts.append(_output_variables(zone_names))
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# Fixed-value extractor
# ---------------------------------------------------------------------------

def _fixed_val(param: dict[str, Any] | float | int | None, default: float) -> float:
    if param is None:
        return default
    if isinstance(param, (int, float)):
        return float(param)
    return param.get("fixed_value", default)


# ---------------------------------------------------------------------------
# Global IDF sections
# ---------------------------------------------------------------------------

def _global_version() -> str:
    return "Version, 25.2;"


def _global_sim_control() -> str:
    return (
        "SimulationControl,\n"
        "  No,   !- Do Zone Sizing Calculation\n"
        "  No,   !- Do System Sizing Calculation\n"
        "  No,   !- Do Plant Sizing Calculation\n"
        "  No,   !- Run Simulation for Sizing Periods\n"
        "  Yes;  !- Run Simulation for Weather File Run Periods"
    )


def _global_building(btype: str) -> str:
    return (
        f"Building,\n"
        f"  {btype}_Building,  !- Name\n"
        f"  0.0,  !- North Axis (deg)\n"
        f"  City, !- Terrain\n"
        f"  0.04, !- Loads Convergence Tolerance\n"
        f"  0.4,  !- Temperature Convergence Tolerance\n"
        f"  FullInteriorAndExterior, !- Solar Distribution\n"
        f"  25,   !- Maximum Number of Warmup Days\n"
        f"  6;    !- Minimum Number of Warmup Days"
    )


def _global_timestep() -> str:
    return "Timestep, 1;"


def _global_run_period() -> str:
    return (
        "RunPeriod,\n"
        "  Annual,            !- Name\n"
        "  1,                 !- Begin Month\n"
        "  1,                 !- Begin Day of Month\n"
        "  ,                  !- Begin Year\n"
        "  12,                !- End Month\n"
        "  31,                !- End Day of Month\n"
        "  ,                  !- End Year\n"
        "  Sunday,            !- Day of Week for Start Day\n"
        "  Yes,               !- Use Weather File Holidays and Special Days\n"
        "  Yes,               !- Use Weather File Daylight Saving Period\n"
        "  No,                !- Apply Weekend Holiday Rule\n"
        "  Yes,               !- Use Weather File Rain Indicators\n"
        "  Yes;               !- Use Weather File Snow Indicators"
    )


def _global_location(cz: str) -> str:
    loc = CLIMATE_ZONE_LOCATIONS.get(cz, CLIMATE_ZONE_LOCATIONS["hot_summer_cold_winter"])
    return (
        f"Site:Location,\n"
        f"  {loc['name']},  !- Name\n"
        f"  {loc['lat']},   !- Latitude\n"
        f"  {loc['lon']},   !- Longitude\n"
        f"  {loc['tz']},    !- Time Zone\n"
        f"  {loc['elev']};  !- Elevation"
    )


def _global_geometry_rules() -> str:
    return "GlobalGeometryRules, UpperLeftCorner, Counterclockwise, World;"


def _global_schedule_types() -> str:
    return (
        "ScheduleTypeLimits, Any Number;\n\n"
        "ScheduleTypeLimits, Fractional, 0, 1, Continuous;\n\n"
        "ScheduleTypeLimits, Temperature, -100, 100, Continuous;"
    )


def _constant_schedules() -> str:
    return (
        "Schedule:Constant, Always_On, Fractional, 1.0;\n\n"
        "Schedule:Constant, Always_4, Any Number, 4;"
    )


# ---------------------------------------------------------------------------
# Zone object
# ---------------------------------------------------------------------------

def _zone_object(zn: str, x0: float) -> str:
    return (
        f"Zone,\n"
        f"  {zn},\n"
        f"  0.0,\n"
        f"  {x0:.4f}, 0.0, 0.0,\n"
        f"  1, 1,\n"
        f"  autocalculate, autocalculate;"
    )


# ---------------------------------------------------------------------------
# Materials & constructions
# ---------------------------------------------------------------------------

def _materials_constructions(zn: str, zone: dict[str, Any]) -> str:
    wall_u = zone.get("wall_u_value", 1.0)
    roof_u = zone.get("roof_u_value", 0.8)
    win_u = zone.get("window_u_value", 3.0)

    wall_r = max(0.01, 1.0 / wall_u - FILM_R_INT - FILM_R_EXT)
    roof_r = max(0.01, 1.0 / roof_u - 0.10 - FILM_R_EXT)
    floor_r = max(0.01, 1.0 / 1.0 - 0.17 - FILM_R_EXT)  # assume U=1 for slab

    lines = [
        f"Material:NoMass, {zn}_WallMat, MediumRough, {wall_r:.4f}, 0.9, 0.7, 0.7;",
        f"Material:NoMass, {zn}_RoofMat, MediumRough, {roof_r:.4f}, 0.9, 0.7, 0.7;",
        f"Material:NoMass, {zn}_FloorMat, MediumRough, {floor_r:.4f}, 0.9, 0.7, 0.7;",
        f"WindowMaterial:SimpleGlazingSystem, {zn}_WinMat, {win_u}, 0.40;",
        f"Construction, {zn}_WallC, {zn}_WallMat;",
        f"Construction, {zn}_RoofC, {zn}_RoofMat;",
        f"Construction, {zn}_FloorC, {zn}_FloorMat;",
        f"Construction, {zn}_WinC, {zn}_WinMat;",
    ]
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# Geometry  (shoebox per zone)
# ---------------------------------------------------------------------------

def _zone_geometry(zn: str, w: float, d: float, h: float,
                   wwr: float, x0: float) -> str:
    parts: list[str] = []

    # Floor
    parts.append(_surface(
        f"{zn}_Floor", "Floor", f"{zn}_FloorC", zn,
        "Ground", False,
        [(x0 + w, d, 0), (x0 + w, 0, 0), (x0, 0, 0), (x0, d, 0)],
    ))
    # Roof
    parts.append(_surface(
        f"{zn}_Roof", "Roof", f"{zn}_RoofC", zn,
        "Outdoors", True,
        [(x0, d, h), (x0, 0, h), (x0 + w, 0, h), (x0 + w, d, h)],
    ))

    # Walls  (name, width_for_windows, 4 vertices)
    wall_defs = [
        ("South", w,
         [(x0, 0, h), (x0, 0, 0), (x0 + w, 0, 0), (x0 + w, 0, h)]),
        ("North", w,
         [(x0 + w, d, h), (x0 + w, d, 0), (x0, d, 0), (x0, d, h)]),
        ("East", d,
         [(x0 + w, 0, h), (x0 + w, 0, 0), (x0 + w, d, 0), (x0 + w, d, h)]),
        ("West", d,
         [(x0, d, h), (x0, d, 0), (x0, 0, 0), (x0, 0, h)]),
    ]

    for orient, ww, verts in wall_defs:
        wn = f"{zn}_Wall_{orient}"
        parts.append(_surface(wn, "Wall", f"{zn}_WallC", zn, "Outdoors", True, verts))
        if wwr > 0.01:
            wv = _window_verts(orient, ww, h, wwr, w, d, x0)
            if wv:
                parts.append(_fenestration(f"{zn}_Win_{orient}", f"{zn}_WinC", wn, wv))

    return "\n\n".join(parts)


def _surface(name: str, stype: str, constr: str, zone: str,
             bc: str, exposed: bool,
             verts: list[tuple[float, float, float]]) -> str:
    sun = "SunExposed" if exposed else "NoSun"
    wind = "WindExposed" if exposed else "NoWind"
    v = ",\n".join(_vstr(*v) for v in verts)
    return (
        f"BuildingSurface:Detailed,\n"
        f"  {name}, {stype}, {constr}, {zone}, ,\n"
        f"  {bc}, , {sun}, {wind}, , {len(verts)},\n"
        f"{v};"
    )


def _fenestration(name: str, constr: str, base: str,
                  verts: list[tuple[float, float, float]]) -> str:
    v = ",\n".join(_vstr(*v) for v in verts)
    return (
        f"FenestrationSurface:Detailed,\n"
        f"  {name}, Window, {constr}, {base},\n"
        f"  , , , , {len(verts)},\n"
        f"{v};"
    )


def _window_verts(orient: str, wall_w: float, wall_h: float, wwr: float,
                  W: float, D: float, x0: float,
                  ) -> list[tuple[float, float, float]] | None:
    wa = wall_w * wall_h * wwr
    wh = wall_h * 0.7
    ww = min(wa / wh, wall_w * 0.95)
    if ww < 0.1:
        return None
    wh = wa / ww
    hi = (wall_w - ww) / 2
    vi = (wall_h - wh) / 2
    zt, zb = vi + wh, vi

    if orient == "South":
        return [(x0 + hi, 0, zt), (x0 + hi, 0, zb),
                (x0 + hi + ww, 0, zb), (x0 + hi + ww, 0, zt)]
    if orient == "North":
        return [(x0 + W - hi, D, zt), (x0 + W - hi, D, zb),
                (x0 + hi, D, zb), (x0 + hi, D, zt)]
    if orient == "East":
        return [(x0 + W, hi, zt), (x0 + W, hi, zb),
                (x0 + W, hi + ww, zb), (x0 + W, hi + ww, zt)]
    # West
    return [(x0, D - hi, zt), (x0, D - hi, zb),
            (x0, hi, zb), (x0, hi, zt)]


# ---------------------------------------------------------------------------
# Schedule generation from ParamConfig
# ---------------------------------------------------------------------------

def _param_config_schedule(name: str, param: dict[str, Any] | float | int | None) -> str:
    """Convert a ParamConfig to EnergyPlus schedule objects.

    Uses Schedule:Day:Hourly + Schedule:Week:Daily + Schedule:Year for
    scheduled mode; Schedule:Constant for fixed mode.
    """
    if param is None:
        return f"Schedule:Constant, {name}, Any Number, 0;"
    if isinstance(param, (int, float)):
        return f"Schedule:Constant, {name}, Any Number, {param};"

    fv = param.get("fixed_value", 0.0)
    if param.get("mode", "fixed") == "fixed" or not param.get("schedules"):
        return f"Schedule:Constant, {name}, Any Number, {fv};"

    schedules = param["schedules"]
    # Group by date period
    periods: dict[tuple[int, int, int, int], list[dict]] = {}
    for s in schedules:
        key = (s["start_month"], s["start_day"], s["end_month"], s["end_day"])
        periods.setdefault(key, []).append(s)

    parts: list[str] = []
    year_entries: list[str] = []

    for pi, ((sm, sd, em, ed), entries) in enumerate(sorted(periods.items())):
        # 7×24 matrix initialised to fixed_value  (index 0=Mon .. 6=Sun)
        matrix = [[fv] * 24 for _ in range(7)]
        for entry in entries:
            for dow in entry.get("days", list(range(1, 8))):
                for hr in entry.get("hours", list(range(24))):
                    if 0 <= dow - 1 < 7 and 0 <= hr < 24:
                        matrix[dow - 1][hr] = entry.get("value", fv)

        unique: dict[tuple[float, ...], str] = {}
        dow_names: list[str] = [""] * 7
        for dow in range(7):
            key = tuple(matrix[dow])
            if key not in unique:
                dn = f"{name}_P{pi}_D{len(unique)}"
                unique[key] = dn
                vals = ", ".join(str(v) for v in key)
                parts.append(f"Schedule:Day:Hourly, {dn}, Any Number, {vals};")
            dow_names[dow] = unique[key]

        # Week schedule:  Sun Mon Tue Wed Thu Fri Sat  Hol SDD WDD CD1 CD2
        wk = f"{name}_W{pi}"
        week = [
            dow_names[6],  # Sunday
            dow_names[0],  # Monday
            dow_names[1],
            dow_names[2],
            dow_names[3],
            dow_names[4],
            dow_names[5],  # Saturday
        ]
        week += [dow_names[6]] * 5  # Holiday, SDD, WDD, CD1, CD2
        parts.append(f"Schedule:Week:Daily, {wk}, " + ", ".join(week) + ";")
        year_entries.append(f"  {wk}, {sm}, {sd}, {em}, {ed}")

    parts.append(f"Schedule:Year, {name}, Any Number,\n" + ",\n".join(year_entries) + ";")
    return "\n\n".join(parts)


def _offset_schedule(name: str, param: dict[str, Any] | float | int | None,
                     offset: float) -> str:
    """Create a schedule identical to *param* but with all values shifted by *offset*."""
    if param is None:
        return f"Schedule:Constant, {name}, Temperature, {0 + offset};"
    if isinstance(param, (int, float)):
        return f"Schedule:Constant, {name}, Temperature, {float(param) + offset};"

    fv = param.get("fixed_value", 0.0) + offset
    if param.get("mode", "fixed") == "fixed" or not param.get("schedules"):
        return f"Schedule:Constant, {name}, Temperature, {fv};"

    shifted = dict(param)
    shifted["fixed_value"] = fv
    shifted["schedules"] = [
        {**s, "value": s.get("value", param.get("fixed_value", 0.0)) + offset}
        for s in param.get("schedules", [])
    ]
    return _param_config_schedule(name, shifted)


# ---------------------------------------------------------------------------
# Internal gains
# ---------------------------------------------------------------------------

def _people(zn: str, area: float, sched: str) -> str:
    """Design level = 1 person/m²; schedule carries actual density values."""
    return (
        f"People,\n"
        f"  {zn}_People, {zn}, {sched},\n"
        f"  People/Area, , 1.0, ,\n"
        f"  0.3, autocalculate, Always_On;"
    )


def _lights(zn: str, area: float, sched: str) -> str:
    return (
        f"Lights,\n"
        f"  {zn}_Lights, {zn}, {sched},\n"
        f"  Watts/Area, , 1.0, ,\n"
        f"  0.0, 0.7, 0.2, 1.0;"
    )


def _equipment(zn: str, area: float, sched: str) -> str:
    return (
        f"ElectricEquipment,\n"
        f"  {zn}_Equip, {zn}, {sched},\n"
        f"  Watts/Area, , 1.0, ,\n"
        f"  0.0, 0.3, 0.0;"
    )


# ---------------------------------------------------------------------------
# Outdoor air
# ---------------------------------------------------------------------------

def _outdoor_air_spec(zn: str, oa_per_person: float, sched: str) -> str:
    return (
        f"DesignSpecification:OutdoorAir,\n"
        f"  {zn}_DSOA,\n"
        f"  Flow/Person,\n"
        f"  {oa_per_person:.6f}, , , ,\n"
        f"  {sched};"
    )


# ---------------------------------------------------------------------------
# Thermostat + Ideal loads
# ---------------------------------------------------------------------------

def _thermostat(zn: str, cool_sched: str, heat_sched: str) -> str:
    return (
        f"ThermostatSetpoint:DualSetpoint,\n"
        f"  {zn}_DualSP, {heat_sched}, {cool_sched};\n\n"
        f"ZoneControl:Thermostat,\n"
        f"  {zn}_Thermostat, {zn}, Always_4,\n"
        f"  ThermostatSetpoint:DualSetpoint, {zn}_DualSP;"
    )


def _ideal_loads(zn: str) -> str:
    return (
        f"ZoneHVAC:IdealLoadsAirSystem,\n"
        f"  {zn}_IdealLoads,\n"
        f"  ,\n"                             # Availability schedule (always)
        f"  {zn}_IdealLoads_SupplyInlet,\n"  # Zone Supply Air Node
        f"  ,\n"                             # Zone Exhaust Air Node
        f"  ,\n"                             # System Inlet Air Node (blank)
        f"  50,\n"                           # Max Heating SAT
        f"  13,\n"                           # Min Cooling SAT
        f"  0.0156,\n"                       # Max Heating Humidity Ratio
        f"  0.0077,\n"                       # Min Cooling Humidity Ratio
        f"  NoLimit, , ,\n"                  # Heating limit
        f"  NoLimit, , ,\n"                  # Cooling limit
        f"  , ,\n"                           # Heat/Cool availability
        f"  ConstantSensibleHeatRatio, 0.7,\n"
        f"  None,\n"                         # Humidification Control
        f"  {zn}_DSOA,\n"                    # Design Spec OA
        f"  ,\n"                             # OA inlet node
        f"  None,\n"                         # DCV type
        f"  NoEconomizer,\n"
        f"  None,\n"                         # Heat Recovery
        f"  0.70, 0.65;"
    )


def _zone_equipment(zn: str) -> str:
    """Generate EquipmentList, EquipmentConnections and NodeList for a zone."""
    return (
        f"ZoneHVAC:EquipmentList,\n"
        f"  {zn}_EquipList,\n"
        f"  SequentialLoad,\n"
        f"  ZoneHVAC:IdealLoadsAirSystem,\n"
        f"  {zn}_IdealLoads,\n"
        f"  1, 1, , ;  !- Priority\n\n"
        f"ZoneHVAC:EquipmentConnections,\n"
        f"  {zn},\n"
        f"  {zn}_EquipList,\n"
        f"  {zn}_InletNodes,\n"
        f"  ,\n"                       # exhaust node list (blank)
        f"  {zn}_AirNode,\n"           # zone air node
        f"  {zn}_ReturnNode;\n\n"      # zone return air node
        f"NodeList, {zn}_InletNodes, {zn}_IdealLoads_SupplyInlet;"
    )


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------

def _output_variables(zone_names: list[str]) -> str:
    lines = [
        "Output:Variable, *, Zone Ideal Loads Supply Air Total Cooling Energy, Hourly;",
        "Output:Variable, *, Zone Ideal Loads Supply Air Total Heating Energy, Hourly;",
        "Output:Variable, *, Zone Mean Air Temperature, Hourly;",
        "OutputControl:Table:Style, HTML;",
        "Output:Table:SummaryReports, AllSummary;",
    ]
    return "\n\n".join(lines)
