"""Translate platform scheme snapshots into the multiSystem energy contract."""

from __future__ import annotations

from typing import Any


MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


class MultiSystemPayloadError(ValueError):
    """A platform entity cannot be represented by the current engine contract."""


def build_multisystem_payload(
    *,
    scheme: Any,
    building: Any,
    load_result: Any,
    equipment_map: dict[Any, Any],
    weather: dict[str, list[float]],
    altitude: float,
) -> dict[str, Any]:
    cooling = [float(value) for value in (load_result.hourly_cooling_load or [])]
    heating = [float(value) for value in (load_result.hourly_heating_load or [])]
    dry_bulb = weather.get("dry_bulb_temperature") or []
    relative_humidity = weather.get("relative_humidity") or []
    if not cooling or len(cooling) != len(heating):
        raise MultiSystemPayloadError("负荷结果缺少等长的逐时冷、热负荷")
    if len(dry_bulb) != len(cooling) or len(relative_humidity) != len(cooling):
        raise MultiSystemPayloadError("气象数据长度必须与逐时负荷长度一致")

    unsupported = [sub.name for sub in scheme.subsystems if sub.subsystem_type not in {"chiller_plant", "air_cooled"}]
    if unsupported:
        raise MultiSystemPayloadError(f"当前 multiSystem 尚不支持这些子系统：{', '.join(unsupported)}")

    hvac_system = []
    for subsystem in scheme.subsystems:
        strategy = (scheme.control_strategy or {}).get("system_strategies", {}).get(str(subsystem.id), {})
        if subsystem.subsystem_type == "chiller_plant":
            config = _chiller_config(subsystem, strategy, scheme.safety_margin, equipment_map)
            engine_type = "chiller_plant"
        else:
            config = _module_config(subsystem, strategy, scheme.safety_margin, equipment_map)
            engine_type = "module_plant"
        hvac_system.append({"id": str(subsystem.id), "type": engine_type, "config": config})

    if not hvac_system:
        raise MultiSystemPayloadError("方案至少需要一个可计算的子系统")

    meteorology = [
        {"Ta_db": float(temperature), "RH": _humidity_ratio(humidity)}
        for temperature, humidity in zip(dry_bulb, relative_humidity, strict=True)
    ]
    load_distribution = _load_distribution(scheme, cooling, heating)
    return {
        "hvac_system": hvac_system,
        "altitude": float(altitude or 0.0),
        "meteorology": meteorology,
        "load_distribution": load_distribution,
    }


def _load_distribution(scheme: Any, cooling: list[float], heating: list[float]) -> list[dict[str, Any]]:
    config = (scheme.control_strategy or {}).get("load_distribution") or {}
    groups = config.get("groups") or []
    if len(groups) != 1:
        raise MultiSystemPayloadError("当前负荷结果只保存建筑总负荷，能耗仿真暂只支持一个负荷分组")
    group_id = str(groups[0].get("id") or "")
    subsystem_group_map = config.get("subsystem_group_map") or {}
    system_ids = [str(sub.id) for sub in scheme.subsystems if str(subsystem_group_map.get(str(sub.id), group_id)) == group_id]
    if len(system_ids) != len(scheme.subsystems):
        raise MultiSystemPayloadError("存在未分配到唯一负荷组的子系统")

    setting = (config.get("group_settings") or {}).get(group_id) or {}
    raw_mode = setting.get("mode") or config.get("mode") or "fixed_ratio"
    hourly_load = [
        {"cooling_load": cool, "heating_load": heat}
        for cool, heat in zip(cooling, heating, strict=True)
    ]
    if raw_mode == "fixed_ratio":
        raw_ratios = setting.get("ratios") or {}
        ratios = {system_id: float(raw_ratios.get(system_id, 0.0)) for system_id in system_ids}
        if any(value <= 0 for value in ratios.values()):
            raise MultiSystemPayloadError("固定比例负荷分配中每个子系统比例必须大于 0")
        return [{"mode": "fixed_ratio", "ratios": ratios, "load": hourly_load}]
    if raw_mode == "by_priority":
        raw_priorities = setting.get("priorities") or {}
        priority = sorted(system_ids, key=lambda system_id: int(raw_priorities.get(system_id, 9999)))
        return [{"mode": "priority", "priority": priority, "load": hourly_load}]
    raise MultiSystemPayloadError(f"multiSystem 不支持负荷分配模式：{raw_mode}")


def _chiller_config(subsystem: Any, strategy: dict[str, Any], safety_margin: float, equipment_map: dict[Any, Any]) -> dict[str, Any]:
    dp = subsystem.design_params or {}
    tower_head = max(
        (_number(_equipment(equipment_map, group.tower_model_id, "冷却塔").parameters, "head", 0.0) for group in subsystem.tower_groups),
        default=0.0,
    )
    chiller_groups = []
    for combo in subsystem.combos:
        primary = _equipment(equipment_map, combo.primary_model_id, "冷水机组")
        chw_pump = _equipment(equipment_map, combo.chw_pump_model_id, "冷冻水泵")
        cw_pump = _equipment(equipment_map, combo.cw_pump_model_id, "冷却水泵")
        pp = primary.parameters or {}
        number_chiller = int(combo.primary_count)
        evap_dp = _number(pp, "evap_dp")
        cond_dp = _number(pp, "cond_dp")
        evap_flow = _number(pp, "evap_flow") * number_chiller
        cond_flow = _number(pp, "cond_flow") * number_chiller
        chiller_groups.append({
            "id": str(combo.id),
            "condenser": _water_side(
                cw_pump, combo.cw_connection,
                max(0.0, _number(dp, "cw_pump_head", 30.0) - cond_dp - tower_head),
                cond_flow, max(int(combo.cw_pump_count) - int(combo.cw_pump_backup), 1), combo.cw_pump_factor,
            ),
            "evaporator": _water_side(
                chw_pump, combo.chw_connection,
                max(0.0, _number(dp, "chw_pump_head", 35.0) - _number(dp, "header_pressure_drop", 21.0) - evap_dp),
                evap_flow, max(int(combo.chw_pump_count) - int(combo.chw_pump_backup), 1), combo.chw_pump_factor,
            ),
            "chiller": {
                "machine_model": _model_no(primary),
                "machine_type": str(pp.get("machine_type") or "sllg"),
                "standby_power": _number(pp, "standby_power", 0.0),
                "manufacturer_factor": float(combo.primary_factor),
            },
            "number_chiller": number_chiller,
        })

    towers = []
    for group in subsystem.tower_groups:
        tower = _equipment(equipment_map, group.tower_model_id, "冷却塔")
        params = tower.parameters or {}
        towers.append({
            "id": str(group.id),
            "number_tower": int(group.count),
            "coe0": _number(params, "coe0"),
            "coe1": _number(params, "coe1"),
            "flux_w": _number(params, "flow"),
            "power_e": _number(params, "power"),
            "frequency": _number(params, "frequency_max", 50.0),
            "Ta_db_in": _number(params, "dry_bulb", 32.0),
            "Ta_wb_in": _number(params, "wet_bulb", 28.0),
            "Tw_in": _number(params, "inlet_temp", 37.0),
            "Tw_out": _number(params, "outlet_temp", 32.0),
            "Hw": _number(params, "head", 0.0),
            "RH_out_set": _number(params, "rh_out_set", 1.0),
            "frequency_min": _number(params, "frequency_min", 30.0),
            "frequency_max": _number(params, "frequency_max", 50.0),
            "manufacturer_factor": float(group.factor),
        })
    if not chiller_groups or not towers:
        raise MultiSystemPayloadError(f"子系统[{subsystem.name}]需要冷机组合和冷却塔组合")

    water = strategy.get("water_temp") or {}
    equipment = strategy.get("equipment") or {}
    tower_strategy = equipment.get("tower") or {}
    return {
        "chiller_pump": chiller_groups,
        "tower": towers,
        "design_condition": {
            "Te_out": _number(dp, "chw_supply_temp", 7.0),
            "Te_difference": _number(dp, "chw_delta_temp", 5.0),
            "Tc_in": _number(dp, "cw_supply_temp", 30.0),
            "Tc_difference": _number(dp, "cw_delta_temp", 5.0),
        },
        "strategy": {
            "running_times": _running_times(strategy.get("run_schedules") or []),
            "safety_margin": _safety_margin(safety_margin),
            "Te_out": _profile(water.get("chw_supply"), _number(dp, "chw_supply_temp", 7.0)),
            "Te_difference": _profile(water.get("chw_delta"), _number(dp, "chw_delta_temp", 5.0)),
            "approach_T": _profile(water.get("approach"), 3.0),
            "Tc_difference": _profile(water.get("cw_delta"), _number(dp, "cw_delta_temp", 5.0)),
            "equipment": {
                "chiller": _equipment_stages(equipment.get("chiller_stages") or [], minimum=0.3),
                "pump_evaporator": _frequency_range(equipment.get("chw_pump")),
                "pump_condenser": _frequency_range(equipment.get("cw_pump")),
                "tower": {
                    **_frequency_range(tower_strategy),
                    "m": int(tower_strategy.get("m", 1)),
                    "n": int(tower_strategy.get("k", 0)),
                },
            },
            "TTD_e": {"mode": "fixed", "value": 0.0},
            "TTD_c": {"mode": "fixed", "value": 0.0},
            "standby_power_flag": True,
        },
        "pressure_drop_header_evaporator": _number(dp, "header_pressure_drop", 21.0),
    }


def _module_config(subsystem: Any, strategy: dict[str, Any], safety_margin: float, equipment_map: dict[Any, Any]) -> dict[str, Any]:
    dp = subsystem.design_params or {}
    pipe_type = str(dp.get("pipe_system") or "two_pipe")
    groups = []
    for combo in subsystem.combos:
        primary = _equipment(equipment_map, combo.primary_model_id, "风冷模块机")
        pp = primary.parameters or {}
        module_count = int(combo.primary_count)
        group_config: dict[str, Any] = {
            "id": str(combo.id),
            "number_group": int(combo.group_count),
            "air_source_module": {
                "machine": _model_no(primary),
                "number": module_count,
                "frequency_mode": str(pp.get("frequency_mode") or "variable"),
                "standby_power": _number(pp, "standby_power", 0.0),
                "manufacturer_factor": float(combo.primary_factor),
            },
        }
        if pipe_type == "four_pipe":
            cooling_pump = _equipment(equipment_map, combo.chw_pump_model_id, "冷水泵")
            heating_pump = _equipment(equipment_map, combo.cw_pump_model_id, "热水泵")
            group_config["cooling"] = _water_side(
                cooling_pump, combo.chw_connection,
                max(0.0, _number(dp, "chw_pump_head", 35.0) - _number(dp, "chw_header_pressure_drop", 21.0) - _number(pp, "cooling_dp")),
                _number(pp, "cooling_flow") * module_count,
                max(int(combo.chw_pump_count) - int(combo.chw_pump_backup), 1), combo.chw_pump_factor,
            )
            group_config["heating"] = _water_side(
                heating_pump, combo.cw_connection,
                max(0.0, _number(dp, "hw_pump_head", 35.0) - _number(dp, "hw_header_pressure_drop", 21.0) - _number(pp, "heating_dp")),
                _number(pp, "heating_flow") * module_count,
                max(int(combo.cw_pump_count) - int(combo.cw_pump_backup), 1), combo.cw_pump_factor,
            )
        else:
            pump = _equipment(equipment_map, combo.chw_pump_model_id, "水泵")
            group_config["water"] = _water_side(
                pump, combo.chw_connection,
                max(0.0, _number(dp, "pump_head", 35.0) - _number(dp, "header_pressure_drop", 21.0) - max(_number(pp, "cooling_dp"), _number(pp, "heating_dp"))),
                max(_number(pp, "cooling_flow"), _number(pp, "heating_flow")) * module_count,
                max(int(combo.chw_pump_count) - int(combo.chw_pump_backup), 1), combo.chw_pump_factor,
            )
        groups.append(group_config)
    if not groups:
        raise MultiSystemPayloadError(f"子系统[{subsystem.name}]需要至少一个模块机组合")

    water = strategy.get("water_temp") or {}
    equipment = strategy.get("equipment") or {}
    pump_strategy: Any
    config: dict[str, Any] = {
        "pipe_type": pipe_type,
        "module_pump": groups,
        "design_condition": {
            "cooling_Ta_db": _number(dp, "cooling_outdoor_dry_bulb", 35.0),
            "cooling_Ta_wb": _number(dp, "cooling_outdoor_wet_bulb", 28.0),
            "heating_Ta_db": _number(dp, "heating_outdoor_dry_bulb", 7.0),
            "heating_Ta_wb": _number(dp, "heating_outdoor_wet_bulb", 6.0),
            "cooling_Tw_out": _number(dp, "cooling_supply_temp", 7.0),
            "cooling_Tw_difference": _number(dp, "cooling_delta_temp", 5.0),
            "heating_Tw_out": _number(dp, "heating_supply_temp", 45.0),
            "heating_Tw_difference": _number(dp, "heating_delta_temp", 5.0),
        },
    }
    if pipe_type == "four_pipe":
        config["pressure_drop_header_pipe_cooling"] = _number(dp, "chw_header_pressure_drop", 21.0)
        config["pressure_drop_header_pipe_heating"] = _number(dp, "hw_header_pressure_drop", 21.0)
        pump_strategy = {
            "cooling": _frequency_range(equipment.get("chw_pump")),
            "heating": _frequency_range(equipment.get("hw_pump")),
        }
    else:
        config["pressure_drop_header_pipe"] = _number(dp, "header_pressure_drop", 21.0)
        pump_strategy = _frequency_range(equipment.get("pump"))
    config["strategy"] = {
        "running_times": _running_times(strategy.get("run_schedules") or []),
        "safety_margin": _safety_margin(safety_margin),
        "cooling_Tw_out": _profile(water.get("cooling_supply"), _number(dp, "cooling_supply_temp", 7.0)),
        "cooling_Tw_difference": _profile(water.get("cooling_delta"), _number(dp, "cooling_delta_temp", 5.0)),
        "heating_Tw_out": _profile(water.get("heating_supply"), _number(dp, "heating_supply_temp", 45.0)),
        "heating_Tw_difference": _profile(water.get("heating_delta"), _number(dp, "heating_delta_temp", 5.0)),
        "equipment": {
            "module": _equipment_stages(equipment.get("module_stages") or [], minimum=0.0),
            "pump": pump_strategy,
        },
        "standby_power_flag": True,
    }
    return config


def _water_side(pump: Any, connection: str, header: float, flux: float, number_pump: int, factor: float) -> dict[str, Any]:
    params = pump.parameters or {}
    coe_head = _number_list(params, "coe_head")
    coe_power = _number_list(params, "coe_power")
    if not coe_head or not coe_power:
        raise MultiSystemPayloadError(f"水泵[{pump.name}]缺少扬程或功率曲线，请重新同步设备库")
    flux_max = _number(params, "flux_max", _number(params, "flow", 0.0))
    if flux <= 0 or flux_max <= 0:
        raise MultiSystemPayloadError(f"水泵[{pump.name}]或主机缺少有效流量参数")
    return {
        "connection_type": str(connection),
        "header": float(header),
        "flux": float(flux),
        "pump": {
            "coe_head": coe_head,
            "coe_power": coe_power,
            "frequency_min": _number(params, "frequency_min", 30.0),
            "frequency_max": _number(params, "frequency_max", 50.0),
            "flux_min": _number(params, "flux_min", 0.0),
            "flux_max": flux_max,
            "manufacturer_factor": float(factor),
        },
        "number_pump": int(number_pump),
    }


def _profile(raw: Any, default: float) -> dict[str, Any]:
    profile = raw if isinstance(raw, dict) else {}
    mode = str(profile.get("mode") or "fixed")
    if mode == "fixed":
        return {"mode": "fixed", "value": float(profile.get("fixed_value", default))}
    if mode == "by_month":
        values = profile.get("month_values") or []
        if len(values) != 12:
            raise MultiSystemPayloadError("按月策略必须包含 12 个值")
        return {"mode": "month", "value": {name: float(values[index]) for index, name in enumerate(MONTH_NAMES)}}
    if mode == "by_load":
        return {"mode": "load_rate", "value": _piecewise(profile.get("load_values"), [(index / 10, (index + 1) / 10) for index in range(10)] + [(1.0, None)])}
    if mode == "by_dry_bulb":
        return {"mode": "tdb", "value": _piecewise(profile.get("dry_bulb_values"), [(None, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 35), (35, 40), (40, 45), (45, 50), (50, None)])}
    if mode == "by_wet_bulb":
        return {"mode": "twb", "value": _piecewise(profile.get("wet_bulb_values"), [(None, 10), (10, 15), (15, 20), (20, 25), (25, 30), (30, 35), (35, 40), (40, 45), (45, 50), (50, None)])}
    raise MultiSystemPayloadError(f"multiSystem 不支持策略模式：{mode}")


def _piecewise(values: Any, ranges: list[tuple[float | None, float | None]]) -> list[dict[str, Any]]:
    if not isinstance(values, list) or len(values) != len(ranges):
        raise MultiSystemPayloadError("分段策略值数量与区间数量不一致")
    return [{"min": lower, "max": upper, "value": float(values[index])} for index, (lower, upper) in enumerate(ranges)]


def _running_times(schedules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in schedules:
        result.append({
            "startDate": f"{int(item.get('start_month', 1)):02d}-{int(item.get('start_day', 1)):02d}",
            "endDate": f"{int(item.get('end_month', 12)):02d}-{int(item.get('end_day', 31)):02d}",
            "weekdays": [int(day) - 1 for day in item.get("days", [])],
            "hours": [int(hour) for hour in item.get("hours", [])],
        })
    return result


def _equipment_stages(stages: list[dict[str, Any]], minimum: float) -> list[dict[str, Any]]:
    if not stages:
        raise MultiSystemPayloadError("设备启停策略至少需要一个阶段")
    result = []
    for stage in stages:
        running = {str(key): int(value) for key, value in (stage.get("combo_counts") or {}).items() if int(value) > 0}
        if not running:
            raise MultiSystemPayloadError("设备启停阶段没有运行设备")
        lower = stage.get("loading_down")
        upper = stage.get("loading_up")
        result.append({
            "running_equipment": running,
            "min": minimum if lower is None else max(minimum, float(lower) / 100.0),
            "max": 1.0 if upper is None else min(1.0, float(upper) / 100.0),
        })
    return result


def _frequency_range(raw: Any) -> dict[str, float]:
    value = raw if isinstance(raw, dict) else {}
    return {"min": float(value.get("min_freq", 30.0)), "max": float(value.get("max_freq", 50.0))}


def _safety_margin(value: Any) -> dict[str, Any]:
    number = float(value or 1.0)
    if not 0.5 <= number <= 2.0:
        raise MultiSystemPayloadError("安全裕量必须在 0.5 到 2.0 之间")
    return {"mode": "energy", "value": number}


def _equipment(equipment_map: dict[Any, Any], equipment_id: Any, label: str) -> Any:
    equipment = equipment_map.get(equipment_id)
    if equipment is None:
        raise MultiSystemPayloadError(f"{label}未选择或设备记录不存在")
    return equipment


def _model_no(equipment: Any) -> str:
    value = str(equipment.model_no or "").strip()
    if not value:
        raise MultiSystemPayloadError(f"设备[{equipment.name}]缺少型号")
    return value


def _number(source: Any, key: str, default: float | None = None) -> float:
    value = source.get(key) if isinstance(source, dict) else getattr(source, key, None)
    if value in (None, ""):
        if default is not None:
            return float(default)
        raise MultiSystemPayloadError(f"缺少计算参数：{key}")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise MultiSystemPayloadError(f"计算参数 {key} 不是有效数字") from exc


def _number_list(source: dict[str, Any], key: str) -> list[float]:
    values = source.get(key)
    if not isinstance(values, list):
        return []
    return [float(value) for value in values]


def _humidity_ratio(value: float) -> float:
    number = float(value)
    if number > 1.0:
        number /= 100.0
    if not 0.0 <= number <= 1.0:
        raise MultiSystemPayloadError(f"相对湿度超出 0~1 范围：{value}")
    return number