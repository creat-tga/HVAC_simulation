from __future__ import annotations

import uuid
from typing import Any

from app.models.building import Building
from app.models.system_scheme import SystemScheme, SystemSubsystem
from app.schemas.system_scheme import ValidationIssue


DAYS_PER_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def zone_key(zone: dict[str, Any], idx: int) -> str:
    zid = zone.get("id")
    if zid:
        return str(zid)
    return f"zone_{idx + 1}"


def default_run_schedule() -> dict[str, Any]:
    hourly = [0] * 24
    for hour in range(8, 18):
        hourly[hour] = 100
    return {
        "name": "日程组 1",
        "start_month": 6,
        "start_day": 15,
        "end_month": 10,
        "end_day": 15,
        "days": [1, 2, 3, 4, 5],
        "hours": list(range(8, 18)),
        "value": 1,
        "hourly_ratios": hourly,
    }


def default_profile(value: float) -> dict[str, Any]:
    fixed = round(float(value), 2)
    return {
        "mode": "fixed",
        "fixed_value": fixed,
        "month_values": [fixed] * 12,
        "load_values": [fixed] * 11,
        "dry_bulb_values": [fixed] * 10,
        "wet_bulb_values": [fixed] * 10,
        "constant_pressure": False,
    }


def _subsystem_order_key(sub: SystemSubsystem, derived_sub: dict[str, Any] | None) -> tuple[int, float, int]:
    rank = {
        "free_cooling": 0,
        "gshp": 1,
        "heat_recovery": 2,
        "chiller_plant": 3,
        "air_cooled": 4,
        "shared_tower": 5,
    }
    cooling = float((derived_sub or {}).get("cooling_capacity_total") or 0.0)
    return (rank.get(sub.subsystem_type, 99), cooling, sub.subsystem_index)


def _round_percent_list(raw: list[tuple[str, float]]) -> dict[str, float]:
    if not raw:
        return {}
    total = sum(val for _, val in raw)
    if total <= 0:
        even = round(100.0 / len(raw), 2)
        out = {key: even for key, _ in raw}
        diff = round(100.0 - sum(out.values()), 2)
        first = raw[0][0]
        out[first] = round(out[first] + diff, 2)
        return out
    scaled: list[tuple[str, float]] = []
    acc = 0.0
    for idx, (key, value) in enumerate(raw):
        if idx == len(raw) - 1:
            scaled.append((key, round(100.0 - acc, 2)))
            break
        pct = round(value / total * 100.0, 2)
        scaled.append((key, pct))
        acc += pct
    return {key: value for key, value in scaled}


def _derived_maps(derived: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    sub_map: dict[str, dict[str, Any]] = {}
    combo_map: dict[str, dict[str, Any]] = {}
    for sub in derived.get("subsystems", []):
        sid = str(sub.get("id") or "")
        if sid:
            sub_map[sid] = sub
        for combo in sub.get("combos", []):
            cid = str(combo.get("id") or "")
            if cid:
                combo_map[cid] = combo
    return sub_map, combo_map


def _default_stages_for_chiller(sub: SystemSubsystem, derived_sub: dict[str, Any]) -> list[dict[str, Any]]:
    combo_map = {
        str(combo.get("id")): combo for combo in derived_sub.get("combos", []) if combo.get("id")
    }
    units: list[tuple[str, float]] = []
    for combo in sub.combos:
        cid = str(combo.id)
        d = combo_map.get(cid)
        if not d:
            continue
        total_cooling = float(d.get("cooling_capacity") or 0.0)
        unit_cooling = total_cooling / max(combo.primary_count, 1)
        for _ in range(combo.primary_count):
            units.append((cid, unit_cooling))
    units.sort(key=lambda item: item[1])
    if not units:
        return [{
            "id": str(uuid.uuid4()),
            "combo_counts": {},
            "loading_down": None,
            "loading_up": None,
            "cooling_capacity_total": 0.0,
            "cooling_capacity_min": None,
            "cooling_capacity_max": None,
        }]

    stages: list[dict[str, Any]] = []
    combo_counts: dict[str, int] = {}
    combo_unit_capacity: dict[str, float] = {}
    for idx, (cid, unit_capacity) in enumerate(units):
        combo_counts[cid] = combo_counts.get(cid, 0) + 1
        combo_unit_capacity[cid] = unit_capacity
        total = round(sum(combo_unit_capacity[k] * v for k, v in combo_counts.items()), 1)
        prev_total = float(stages[-1]["cooling_capacity_total"]) if stages else 0.0
        loading_down = None if idx == 0 else round(max(30.0, prev_total * 70.0 / max(total, 0.1)), 2)
        loading_up = None if idx == len(units) - 1 else 90.0
        stages.append({
            "id": str(uuid.uuid4()),
            "combo_counts": dict(combo_counts),
            "loading_down": loading_down,
            "loading_up": loading_up,
            "cooling_capacity_total": total,
            "cooling_capacity_min": None if loading_down is None else round(total * loading_down / 100.0, 1),
            "cooling_capacity_max": None if loading_up is None else round(total * loading_up / 100.0, 1),
        })
    return stages


def _default_stages_for_air_cooled(sub: SystemSubsystem, derived_sub: dict[str, Any]) -> list[dict[str, Any]]:
    combo_map = {
        str(combo.get("id")): combo for combo in derived_sub.get("combos", []) if combo.get("id")
    }
    units: list[tuple[str, float, float]] = []
    for combo in sub.combos:
        cid = str(combo.id)
        d = combo_map.get(cid)
        if not d:
            continue
        group_count = max(combo.group_count, 1)
        cool_per_group = float(d.get("cooling_capacity") or 0.0) / group_count
        heat_per_group = float(d.get("heating_capacity") or 0.0) / group_count
        for _ in range(group_count):
            units.append((cid, cool_per_group, heat_per_group))
    units.sort(key=lambda item: item[1])
    if not units:
        return [{
            "id": str(uuid.uuid4()),
            "combo_counts": {},
            "loading_down": None,
            "loading_up": None,
            "cooling_capacity_total": 0.0,
            "cooling_capacity_min": None,
            "cooling_capacity_max": None,
            "heating_capacity_total": 0.0,
            "heating_capacity_min": None,
            "heating_capacity_max": None,
        }]

    stages: list[dict[str, Any]] = []
    combo_counts: dict[str, int] = {}
    combo_caps: dict[str, tuple[float, float]] = {}
    for idx, (cid, cool_per_group, heat_per_group) in enumerate(units):
        combo_counts[cid] = combo_counts.get(cid, 0) + 1
        combo_caps[cid] = (cool_per_group, heat_per_group)
        total_cool = round(sum(combo_caps[k][0] * v for k, v in combo_counts.items()), 1)
        total_heat = round(sum(combo_caps[k][1] * v for k, v in combo_counts.items()), 1)
        prev_cool = float(stages[-1]["cooling_capacity_total"]) if stages else 0.0
        loading_down = None if idx == 0 else round(max(30.0, prev_cool * 70.0 / max(total_cool, 0.1)), 2)
        loading_up = None if idx == len(units) - 1 else 90.0
        stages.append({
            "id": str(uuid.uuid4()),
            "combo_counts": dict(combo_counts),
            "loading_down": loading_down,
            "loading_up": loading_up,
            "cooling_capacity_total": total_cool,
            "cooling_capacity_min": None if loading_down is None else round(total_cool * loading_down / 100.0, 1),
            "cooling_capacity_max": None if loading_up is None else round(total_cool * loading_up / 100.0, 1),
            "heating_capacity_total": total_heat,
            "heating_capacity_min": None if loading_down is None else round(total_heat * loading_down / 100.0, 1),
            "heating_capacity_max": None if loading_up is None else round(total_heat * loading_up / 100.0, 1),
        })
    return stages


def default_subsystem_strategy(sub: SystemSubsystem, derived_sub: dict[str, Any]) -> dict[str, Any]:
    dp = sub.design_params or {}
    if sub.subsystem_type == "chiller_plant":
        return {
            "subsystem_id": str(sub.id),
            "subsystem_type": sub.subsystem_type,
            "run_schedules": [default_run_schedule()],
            "water_temp": {
                "chw_supply": default_profile(dp.get("chw_supply_temp", 7.0)),
                "chw_delta": default_profile(dp.get("chw_delta_temp", 5.0)),
                "approach": default_profile(3.0),
                "cw_delta": default_profile(dp.get("cw_delta_temp", 5.0)),
            },
            "equipment": {
                "chiller_stages": _default_stages_for_chiller(sub, derived_sub),
                "chw_pump": {"min_freq": 30, "max_freq": 50},
                "cw_pump": {"min_freq": 30, "max_freq": 50},
                "tower": {"min_freq": 30, "max_freq": 50, "m": 1, "k": 0},
            },
        }
    if sub.subsystem_type == "air_cooled":
        pipe_system = str(dp.get("pipe_system", "two_pipe"))
        equipment: dict[str, Any] = {
            "module_stages": _default_stages_for_air_cooled(sub, derived_sub),
        }
        if pipe_system == "four_pipe":
            equipment["chw_pump"] = {"min_freq": 30, "max_freq": 50}
            equipment["hw_pump"] = {"min_freq": 30, "max_freq": 50}
        else:
            equipment["pump"] = {"min_freq": 30, "max_freq": 50}
        return {
            "subsystem_id": str(sub.id),
            "subsystem_type": sub.subsystem_type,
            "run_schedules": [default_run_schedule()],
            "water_temp": {
                "cooling_supply": default_profile(dp.get("cooling_supply_temp", 7.0)),
                "cooling_delta": default_profile(dp.get("cooling_delta_temp", 5.0)),
                "heating_supply": default_profile(dp.get("heating_supply_temp", 45.0)),
                "heating_delta": default_profile(dp.get("heating_delta_temp", 5.0)),
            },
            "equipment": equipment,
        }
    return {
        "subsystem_id": str(sub.id),
        "subsystem_type": sub.subsystem_type,
        "run_schedules": [default_run_schedule()],
        "water_temp": {},
        "equipment": {},
    }


def default_load_distribution(
    scheme: SystemScheme,
    building: Building | None,
    derived: dict[str, Any],
) -> dict[str, Any]:
    group_id = "group-1"
    zones = building.zones or [] if building else []
    sub_map, _combo_map = _derived_maps(derived)
    zone_group_map: dict[str, str] = {}
    for idx, zone in enumerate(zones):
        zone_group_map[zone_key(zone, idx)] = group_id

    subsystem_group_map = {str(sub.id): group_id for sub in scheme.subsystems}
    ratios = _round_percent_list([
        (str(sub.id), float((sub_map.get(str(sub.id)) or {}).get("cooling_capacity_total") or 0.0))
        for sub in scheme.subsystems
    ])
    ordered = sorted(
        scheme.subsystems,
        key=lambda sub: _subsystem_order_key(sub, sub_map.get(str(sub.id))),
    )
    priorities = {str(sub.id): idx + 1 for idx, sub in enumerate(ordered)}
    return {
        "mode": "fixed_ratio",
        "groups": [{"id": group_id, "name": "负荷组 1"}],
        "zone_group_map": zone_group_map,
        "subsystem_group_map": subsystem_group_map,
        "group_settings": {
            group_id: {
                "mode": "fixed_ratio",
                "ratios": ratios,
                "priorities": priorities,
            },
        },
    }


def default_control_strategy() -> dict[str, Any]:
    return {
        "version": 2,
        "load_distribution": {
            "mode": "fixed_ratio",
            "groups": [{"id": "group-1", "name": "负荷组 1"}],
            "zone_group_map": {},
            "subsystem_group_map": {},
            "group_settings": {"group-1": {"mode": "fixed_ratio", "ratios": {}, "priorities": {}}},
        },
        "system_strategies": {},
    }


def _subsystem_signature(sub: SystemSubsystem) -> tuple[Any, ...]:
    combo_sig = tuple(
        (
            combo.combo_index,
            str(combo.primary_model_id) if combo.primary_model_id else None,
            combo.primary_count,
            combo.group_count,
            str(combo.chw_pump_model_id) if combo.chw_pump_model_id else None,
            combo.chw_pump_count,
            str(combo.cw_pump_model_id) if combo.cw_pump_model_id else None,
            combo.cw_pump_count,
        )
        for combo in sorted(sub.combos, key=lambda item: item.combo_index)
    )
    tower_sig = tuple(
        (
            tower.group_index,
            str(tower.tower_model_id) if tower.tower_model_id else None,
            tower.count,
        )
        for tower in sorted(sub.tower_groups, key=lambda item: item.group_index)
    )
    return (sub.subsystem_type, combo_sig, tower_sig)


def _ensure_profile(data: Any, default_value: float, allow_constant_pressure: bool) -> dict[str, Any]:
    if not isinstance(data, dict):
        return default_profile(default_value)
    profile = default_profile(default_value)
    mode = str(data.get("mode") or "fixed")
    if mode not in {"fixed", "by_month", "by_load", "by_dry_bulb", "by_wet_bulb", "constant_pressure"}:
        mode = "fixed"
    if mode == "constant_pressure" and not allow_constant_pressure:
        mode = "fixed"
    profile["mode"] = mode
    for key, size in (("month_values", 12), ("load_values", 11), ("dry_bulb_values", 10), ("wet_bulb_values", 10)):
        vals = data.get(key)
        if isinstance(vals, list) and len(vals) == size:
            profile[key] = [round(float(v), 2) for v in vals]
    if data.get("fixed_value") is not None:
        profile["fixed_value"] = round(float(data.get("fixed_value")), 2)
    profile["constant_pressure"] = bool(data.get("constant_pressure"))
    return profile


def _normalize_subsystem_strategy(existing: Any, sub: SystemSubsystem, derived_sub: dict[str, Any]) -> dict[str, Any]:
    default = default_subsystem_strategy(sub, derived_sub)
    if not isinstance(existing, dict):
        return default
    current = dict(default)
    schedules = existing.get("run_schedules")
    if isinstance(schedules, list) and schedules:
        current["run_schedules"] = schedules[:20]
    water_existing = existing.get("water_temp") if isinstance(existing.get("water_temp"), dict) else {}
    water_default = default.get("water_temp", {})
    water: dict[str, Any] = {}
    for field, prof in water_default.items():
        water[field] = _ensure_profile(
            water_existing.get(field),
            float(prof.get("fixed_value") or 0.0),
            field.endswith("delta"),
        )
    current["water_temp"] = water

    equipment_existing = existing.get("equipment") if isinstance(existing.get("equipment"), dict) else {}
    equipment_default = default.get("equipment", {})
    equipment: dict[str, Any] = {}
    for key, value in equipment_default.items():
        if isinstance(value, list):
            raw = equipment_existing.get(key)
            equipment[key] = raw if isinstance(raw, list) and raw else value
        elif isinstance(value, dict):
            raw = equipment_existing.get(key)
            if isinstance(raw, dict):
                merged = dict(value)
                merged.update({k: raw[k] for k in raw.keys() if k in merged})
                equipment[key] = merged
            else:
                equipment[key] = value
        else:
            equipment[key] = value
    current["equipment"] = equipment
    current["subsystem_id"] = str(sub.id)
    current["subsystem_type"] = sub.subsystem_type
    return current


def rebuild_control_strategy(
    existing: Any,
    old_subsystems: list[SystemSubsystem],
    scheme: SystemScheme,
    building: Building | None,
    derived: dict[str, Any],
) -> dict[str, Any]:
    sub_map, _combo_map = _derived_maps(derived)
    existing_dict = existing if isinstance(existing, dict) else default_control_strategy()
    old_by_id = {str(sub.id): sub for sub in old_subsystems}
    new_ids = {str(sub.id) for sub in scheme.subsystems}
    old_ids = {str(sub.id) for sub in old_subsystems}
    structure_changed = old_ids != new_ids
    if not structure_changed:
        for sub in scheme.subsystems:
            old = old_by_id.get(str(sub.id))
            if old is None or old.subsystem_type != sub.subsystem_type:
                structure_changed = True
                break

    load_distribution = default_load_distribution(scheme, building, derived)
    if not structure_changed and isinstance(existing_dict.get("load_distribution"), dict):
        ld = existing_dict.get("load_distribution") or {}
        groups = ld.get("groups")
        if isinstance(groups, list) and groups:
            valid_groups = []
            for idx, group in enumerate(groups):
                if not isinstance(group, dict):
                    continue
                gid = str(group.get("id") or f"group-{idx + 1}")
                valid_groups.append({"id": gid, "name": str(group.get("name") or f"负荷组 {idx + 1}")})
            if valid_groups:
                group_ids = {group["id"] for group in valid_groups}
                zone_group_map = {}
                for idx, zone in enumerate((building.zones or []) if building else []):
                    zkey = zone_key(zone, idx)
                    gid = str((ld.get("zone_group_map") or {}).get(zkey) or load_distribution["zone_group_map"].get(zkey) or valid_groups[0]["id"])
                    zone_group_map[zkey] = gid if gid in group_ids else valid_groups[0]["id"]
                subsystem_group_map = {}
                for sub in scheme.subsystems:
                    sid = str(sub.id)
                    gid = str((ld.get("subsystem_group_map") or {}).get(sid) or load_distribution["subsystem_group_map"].get(sid) or valid_groups[0]["id"])
                    subsystem_group_map[sid] = gid if gid in group_ids else valid_groups[0]["id"]
                group_settings = {}
                current_settings = ld.get("group_settings") if isinstance(ld.get("group_settings"), dict) else {}
                for group in valid_groups:
                    gid = group["id"]
                    assigned_sub_ids = [sid for sid, mapped_gid in subsystem_group_map.items() if mapped_gid == gid]
                    default_ratios = _round_percent_list([
                        (sid, float((sub_map.get(sid) or {}).get("cooling_capacity_total") or 0.0))
                        for sid in assigned_sub_ids
                    ])
                    ordered_subs = sorted(
                        [sub for sub in scheme.subsystems if str(sub.id) in assigned_sub_ids],
                        key=lambda sub: _subsystem_order_key(sub, sub_map.get(str(sub.id))),
                    )
                    default_priorities = {str(sub.id): idx + 1 for idx, sub in enumerate(ordered_subs)}
                    raw_setting = current_settings.get(gid) if isinstance(current_settings.get(gid), dict) else {}
                    raw_ratios = raw_setting.get("ratios") if isinstance(raw_setting.get("ratios"), dict) else {}
                    raw_priorities = raw_setting.get("priorities") if isinstance(raw_setting.get("priorities"), dict) else {}
                    raw_mode = raw_setting.get("mode")
                    group_mode = str(raw_mode) if raw_mode in {"fixed_ratio", "by_priority", "other"} else str(ld.get("mode") or "fixed_ratio")
                    group_settings[gid] = {
                        "mode": group_mode,
                        "ratios": {
                            sid: round(float(raw_ratios.get(sid, default_ratios.get(sid, 0.0))), 2)
                            for sid in assigned_sub_ids
                        },
                        "priorities": {
                            sid: int(raw_priorities.get(sid, default_priorities.get(sid, 1)))
                            for sid in assigned_sub_ids
                        },
                    }
                load_distribution = {
                    "mode": str(ld.get("mode") or "fixed_ratio"),
                    "groups": valid_groups,
                    "zone_group_map": zone_group_map,
                    "subsystem_group_map": subsystem_group_map,
                    "group_settings": group_settings,
                }

    system_strategies: dict[str, Any] = {}
    existing_sub_map = existing_dict.get("system_strategies") if isinstance(existing_dict.get("system_strategies"), dict) else {}
    for sub in scheme.subsystems:
        sid = str(sub.id)
        old = old_by_id.get(sid)
        equipment_changed = old is None or _subsystem_signature(old) != _subsystem_signature(sub)
        if structure_changed or equipment_changed:
            system_strategies[sid] = default_subsystem_strategy(sub, sub_map.get(sid, {}))
        else:
            system_strategies[sid] = _normalize_subsystem_strategy(existing_sub_map.get(sid), sub, sub_map.get(sid, {}))

    return {
        "version": 2,
        "load_distribution": load_distribution,
        "system_strategies": system_strategies,
    }


def _add(issues: list[ValidationIssue], **kw: Any) -> None:
    issues.append(ValidationIssue(**kw))


def _month_day_to_ordinal(month: int, day: int) -> int:
    ordinal = day
    for idx in range(month - 1):
        ordinal += DAYS_PER_MONTH[idx]
    return ordinal


def _schedule_slots(schedule: dict[str, Any]) -> set[int]:
    start_month = int(schedule.get("start_month") or 1)
    start_day = int(schedule.get("start_day") or 1)
    end_month = int(schedule.get("end_month") or 12)
    end_day = int(schedule.get("end_day") or 31)
    weekdays = {int(day) for day in (schedule.get("days") or []) if 1 <= int(day) <= 7}
    hourly = schedule.get("hourly_ratios") if isinstance(schedule.get("hourly_ratios"), list) else None
    hours = {hour for hour in range(24) if hourly and hour < len(hourly) and float(hourly[hour] or 0) > 0}
    if not hours:
        hours = {int(hour) for hour in (schedule.get("hours") or []) if 0 <= int(hour) <= 23}
    slots: set[int] = set()
    start_ordinal = _month_day_to_ordinal(start_month, start_day)
    end_ordinal = _month_day_to_ordinal(end_month, end_day)
    day_ranges: list[range]
    if start_ordinal <= end_ordinal:
        day_ranges = [range(start_ordinal, end_ordinal + 1)]
    else:
        day_ranges = [range(start_ordinal, 366), range(1, end_ordinal + 1)]
    for day_range in day_ranges:
        for ordinal in day_range:
            dow = ((ordinal - 1) % 7) + 1
            if weekdays and dow not in weekdays:
                continue
            for hour in hours:
                slots.add((ordinal - 1) * 24 + hour)
    return slots


def _validate_profile_range(
    issues: list[ValidationIssue],
    scheme: SystemScheme,
    sub: SystemSubsystem,
    field_prefix: str,
    field_name: str,
    data: Any,
    min_value: float,
    max_value: float,
    allow_constant_pressure: bool,
) -> None:
    if not isinstance(data, dict):
        _add(issues, code="STR_PROFILE_MISSING", severity="error",
             message=f"子系统[{sub.name}] {field_name} 未配置",
             scheme_id=scheme.id, subsystem_id=sub.id, field=field_prefix)
        return
    mode = str(data.get("mode") or "fixed")
    if mode == "constant_pressure" and not allow_constant_pressure:
        _add(issues, code="STR_PROFILE_MODE", severity="error",
             message=f"子系统[{sub.name}] {field_name} 不支持定压差模式",
             scheme_id=scheme.id, subsystem_id=sub.id, field=field_prefix)
        return
    if mode == "fixed":
        values = [data.get("fixed_value")]
    elif mode == "by_month":
        values = data.get("month_values") if isinstance(data.get("month_values"), list) and len(data.get("month_values")) == 12 else None
    elif mode == "by_load":
        values = data.get("load_values") if isinstance(data.get("load_values"), list) and len(data.get("load_values")) == 11 else None
    elif mode == "by_dry_bulb":
        values = data.get("dry_bulb_values") if isinstance(data.get("dry_bulb_values"), list) and len(data.get("dry_bulb_values")) == 10 else None
    elif mode == "by_wet_bulb":
        values = data.get("wet_bulb_values") if isinstance(data.get("wet_bulb_values"), list) and len(data.get("wet_bulb_values")) == 10 else None
    elif mode == "constant_pressure":
        values = []
    else:
        values = None
    if values is None:
        _add(issues, code="STR_PROFILE_VALUES", severity="error",
             message=f"子系统[{sub.name}] {field_name} 配置项不完整",
             scheme_id=scheme.id, subsystem_id=sub.id, field=field_prefix)
        return
    for value in values:
        if value is None:
            _add(issues, code="STR_PROFILE_EMPTY", severity="error",
                 message=f"子系统[{sub.name}] {field_name} 存在空值",
                 scheme_id=scheme.id, subsystem_id=sub.id, field=field_prefix)
            return
        fval = float(value)
        if fval < min_value or fval > max_value:
            _add(issues, code="STR_PROFILE_RANGE", severity="error",
                 message=f"子系统[{sub.name}] {field_name} 超出范围 {min_value}~{max_value}",
                 scheme_id=scheme.id, subsystem_id=sub.id, field=field_prefix)
            return


def validate_control_strategy(
    scheme: SystemScheme,
    building: Building | None,
    derived: dict[str, Any],
    strategy: dict[str, Any],
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    load_distribution = strategy.get("load_distribution") if isinstance(strategy.get("load_distribution"), dict) else {}
    groups = load_distribution.get("groups") if isinstance(load_distribution.get("groups"), list) else []
    if not groups:
        _add(issues, code="STR_LD_GROUPS", severity="error",
             message=f"方案[{scheme.name}] 负荷分配至少需要 1 个分组",
             scheme_id=scheme.id, field="control_strategy.load_distribution.groups")
        return issues
    group_ids = [str(group.get("id") or "") for group in groups if isinstance(group, dict)]
    group_ids = [gid for gid in group_ids if gid]
    if not group_ids:
        _add(issues, code="STR_LD_GROUP_IDS", severity="error",
             message=f"方案[{scheme.name}] 负荷分配分组缺少 id",
             scheme_id=scheme.id, field="control_strategy.load_distribution.groups")
        return issues

    zone_group_map = load_distribution.get("zone_group_map") if isinstance(load_distribution.get("zone_group_map"), dict) else {}
    subsystem_group_map = load_distribution.get("subsystem_group_map") if isinstance(load_distribution.get("subsystem_group_map"), dict) else {}
    group_settings = load_distribution.get("group_settings") if isinstance(load_distribution.get("group_settings"), dict) else {}

    zone_keys = [zone_key(zone, idx) for idx, zone in enumerate((building.zones or []) if building else [])]
    for zkey in zone_keys:
        gid = zone_group_map.get(zkey)
        if gid not in group_ids:
            _add(issues, code="STR_LD_ZONE_ASSIGN", severity="error",
                 message=f"方案[{scheme.name}] 负荷分区 {zkey} 未分配到有效分组",
                 scheme_id=scheme.id, field="control_strategy.load_distribution.zone_group_map")
            break

    subsystem_ids = [str(sub.id) for sub in scheme.subsystems]
    for sid in subsystem_ids:
        gid = subsystem_group_map.get(sid)
        if gid not in group_ids:
            _add(issues, code="STR_LD_SUB_ASSIGN", severity="error",
                 message=f"方案[{scheme.name}] 子系统 {sid[:8]} 未分配到有效分组",
                 scheme_id=scheme.id, field="control_strategy.load_distribution.subsystem_group_map")
            break

    fallback_mode = str(load_distribution.get("mode") or "fixed_ratio")
    for gid in group_ids:
        assigned_sub_ids = [sid for sid, mapped_gid in subsystem_group_map.items() if mapped_gid == gid]
        assigned_zone_ids = [zid for zid, mapped_gid in zone_group_map.items() if mapped_gid == gid]
        if assigned_zone_ids and not assigned_sub_ids:
            _add(issues, code="STR_LD_EMPTY_SYSTEM", severity="error",
                 message=f"方案[{scheme.name}] 分组 {gid} 已分配负荷分区但没有承担该分组的系统",
                 scheme_id=scheme.id, field=f"control_strategy.load_distribution.group_settings.{gid}")
        setting = group_settings.get(gid) if isinstance(group_settings.get(gid), dict) else {}
        raw_mode = setting.get("mode") if isinstance(setting, dict) else None
        mode = str(raw_mode) if raw_mode in {"fixed_ratio", "by_priority", "other"} else fallback_mode
        if mode == "fixed_ratio":
            ratios = setting.get("ratios") if isinstance(setting.get("ratios"), dict) else {}
            values = [float(ratios.get(sid, -1)) for sid in assigned_sub_ids]
            if any(val < 0 or val > 100 for val in values):
                _add(issues, code="STR_LD_RATIO_RANGE", severity="error",
                     message=f"方案[{scheme.name}] 分组 {gid} 存在超出范围的负荷比例",
                     scheme_id=scheme.id, field=f"control_strategy.load_distribution.group_settings.{gid}.ratios")
            if assigned_sub_ids and abs(sum(values) - 100.0) > 0.05:
                _add(issues, code="STR_LD_RATIO_SUM", severity="error",
                     message=f"方案[{scheme.name}] 分组 {gid} 所有系统负荷比例之和必须为 100%",
                     scheme_id=scheme.id, field=f"control_strategy.load_distribution.group_settings.{gid}.ratios")
        if mode == "by_priority":
            priorities = setting.get("priorities") if isinstance(setting.get("priorities"), dict) else {}
            vals = [int(priorities.get(sid, 0)) for sid in assigned_sub_ids]
            if any(val <= 0 for val in vals) or len(set(vals)) != len(vals):
                _add(issues, code="STR_LD_PRIORITY", severity="error",
                     message=f"方案[{scheme.name}] 分组 {gid} 启动优先级必须为唯一的正整数",
                     scheme_id=scheme.id, field=f"control_strategy.load_distribution.group_settings.{gid}.priorities")

    sub_map = strategy.get("system_strategies") if isinstance(strategy.get("system_strategies"), dict) else {}
    for sub in scheme.subsystems:
        sid = str(sub.id)
        data = sub_map.get(sid)
        if not isinstance(data, dict):
            _add(issues, code="STR_SUB_MISSING", severity="error",
                 message=f"子系统[{sub.name}] 缺少详细策略配置",
                 scheme_id=scheme.id, subsystem_id=sub.id, field=f"control_strategy.system_strategies.{sid}")
            continue
        schedules = data.get("run_schedules") if isinstance(data.get("run_schedules"), list) else []
        if len(schedules) < 1 or len(schedules) > 20:
            _add(issues, code="STR_SCHEDULE_COUNT", severity="error",
                 message=f"子系统[{sub.name}] 运行时间日程组数量必须在 1~20 之间",
                 scheme_id=scheme.id, subsystem_id=sub.id, field=f"control_strategy.system_strategies.{sid}.run_schedules")
        occupied: set[int] = set()
        for idx, schedule in enumerate(schedules):
            if not isinstance(schedule, dict):
                continue
            slots = _schedule_slots(schedule)
            if occupied.intersection(slots):
                _add(issues, code="STR_SCHEDULE_CONFLICT", severity="error",
                     message=f"子系统[{sub.name}] 日程组 {idx + 1} 与其他日程组存在时间冲突",
                     scheme_id=scheme.id, subsystem_id=sub.id,
                     field=f"control_strategy.system_strategies.{sid}.run_schedules[{idx}]")
                break
            occupied.update(slots)

        water = data.get("water_temp") if isinstance(data.get("water_temp"), dict) else {}
        if sub.subsystem_type == "chiller_plant":
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.chw_supply", "冷冻出水温度", water.get("chw_supply"), 1.0, 25.0, False)
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.chw_delta", "冷冻进出水温差", water.get("chw_delta"), 1.0, 15.0, True)
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.approach", "逼近温差", water.get("approach"), 1.0, 15.0, False)
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.cw_delta", "冷却进出水温差", water.get("cw_delta"), 1.0, 15.0, True)
        elif sub.subsystem_type == "air_cooled":
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.cooling_supply", "制冷出水温度", water.get("cooling_supply"), 1.0, 25.0, False)
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.cooling_delta", "制冷进出水温差", water.get("cooling_delta"), 1.0, 15.0, True)
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.heating_supply", "制热出水温度", water.get("heating_supply"), 30.0, 100.0, False)
            _validate_profile_range(issues, scheme, sub, f"control_strategy.system_strategies.{sid}.water_temp.heating_delta", "制热进出水温差", water.get("heating_delta"), 1.0, 15.0, True)

        equipment = data.get("equipment") if isinstance(data.get("equipment"), dict) else {}
        stage_key = "chiller_stages" if sub.subsystem_type == "chiller_plant" else "module_stages"
        stages = equipment.get(stage_key) if isinstance(equipment.get(stage_key), list) else []
        if stage_key in equipment and (len(stages) < 1 or len(stages) > 600):
            _add(issues, code="STR_STAGE_COUNT", severity="error",
                 message=f"子系统[{sub.name}] 开机组合数量必须在 1~600 之间",
                 scheme_id=scheme.id, subsystem_id=sub.id, field=f"control_strategy.system_strategies.{sid}.equipment.{stage_key}")
        prev_cap_max: float | None = None
        for idx, stage in enumerate(stages):
            if not isinstance(stage, dict):
                continue
            down = stage.get("loading_down")
            up = stage.get("loading_up")
            if down is not None and up is not None and float(down) >= float(up):
                _add(issues, code="STR_STAGE_LOAD_RANGE", severity="error",
                     message=f"子系统[{sub.name}] 开机组合 {idx + 1} 的减机负荷率必须小于加机负荷率",
                     scheme_id=scheme.id, subsystem_id=sub.id, field=f"control_strategy.system_strategies.{sid}.equipment.{stage_key}[{idx}]")
            current_min = stage.get("cooling_capacity_min")
            if prev_cap_max is not None and current_min is not None and float(current_min) >= prev_cap_max:
                _add(issues, code="STR_STAGE_SEGMENT", severity="warning",
                     message=f"子系统[{sub.name}] 开机组合 {idx + 1} 的冷量段最小值应小于前一组最大值",
                     scheme_id=scheme.id, subsystem_id=sub.id, field=f"control_strategy.system_strategies.{sid}.equipment.{stage_key}[{idx}]")
            current_max = stage.get("cooling_capacity_max")
            prev_cap_max = float(current_max) if current_max is not None else None

        for key, label in (("pump", "水泵"), ("chw_pump", "冷冻水泵"), ("cw_pump", "冷却水泵"), ("hw_pump", "热水泵"), ("tower", "冷却塔")):
            conf = equipment.get(key)
            if not isinstance(conf, dict):
                continue
            min_freq = conf.get("min_freq")
            max_freq = conf.get("max_freq")
            if min_freq is None or max_freq is None:
                continue
            if float(min_freq) >= float(max_freq):
                _add(issues, code="STR_FREQ_RANGE", severity="error",
                     message=f"子系统[{sub.name}] {label} 最小频率必须小于最大频率",
                     scheme_id=scheme.id, subsystem_id=sub.id, field=f"control_strategy.system_strategies.{sid}.equipment.{key}")
    return issues