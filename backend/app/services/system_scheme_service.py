"""System scheme service: CRUD, derived display data, validation.

New hierarchy: Project → SystemScheme → Subsystem → Combos / TowerGroups.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.building import Building
from app.models.simulation import SimulationResult
from app.models.system_scheme import (
    SystemScheme,
    SystemSubsystem,
    SchemeCombo,
    SchemeTowerGroup,
)
from app.services import control_strategy_service as cs
from app.services import library_service as lib
from app.schemas.system_scheme import (
    SystemSchemeCreate,
    SystemSchemeUpdate,
    SubsystemCreate,
    ValidationIssue,
    ValidationReport,
    CapacitySummary,
)


# ---------------------------------------------------------------------------
# CRUD: project-level schemes
# ---------------------------------------------------------------------------

def _scheme_loader_options():
    return [
        selectinload(SystemScheme.subsystems).selectinload(SystemSubsystem.combos),
        selectinload(SystemScheme.subsystems).selectinload(SystemSubsystem.tower_groups),
    ]


async def list_schemes(db: AsyncSession, project_id: uuid.UUID) -> list[SystemScheme]:
    stmt = (
        select(SystemScheme)
        .where(SystemScheme.project_id == project_id)
        .options(*_scheme_loader_options())
        .order_by(SystemScheme.scheme_index)
    )
    return list((await db.execute(stmt)).scalars().all())


async def get_scheme(db: AsyncSession, scheme_id: uuid.UUID) -> SystemScheme | None:
    stmt = (
        select(SystemScheme)
        .where(SystemScheme.id == scheme_id)
        .options(*_scheme_loader_options())
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def _check_building_load_completed(db: AsyncSession, building_id: uuid.UUID) -> Building:
    b = await db.get(Building, building_id)
    if not b:
        raise ValueError("绑定建筑不存在")
    stmt = (
        select(SimulationResult)
        .where(SimulationResult.building_id == building_id)
        .where(SimulationResult.simulation_type == "load")
        .where(SimulationResult.status == "completed")
        .limit(1)
    )
    sr = (await db.execute(stmt)).scalar_one_or_none()
    if sr is None:
        raise ValueError("绑定建筑尚未完成负荷仿真")
    return b


async def create_scheme(
    db: AsyncSession, project_id: uuid.UUID, data: SystemSchemeCreate
) -> SystemScheme:
    existing = await list_schemes(db, project_id)
    if len(existing) >= 5:
        raise ValueError("每个项目至多 5 个系统方案")

    building = await _check_building_load_completed(db, data.building_id)

    scheme = SystemScheme(
        project_id=project_id,
        building_id=data.building_id,
        scheme_index=data.scheme_index,
        name=data.name,
        control_strategy=data.control_strategy,
        diagram_json=data.diagram_json,
        safety_margin=data.safety_margin,
    )
    for sub in data.subsystems:
        scheme.subsystems.append(_build_subsystem(sub))

    if scheme.subsystems:
        derived = await compute_scheme_derived(db, scheme)
        scheme.control_strategy = cs.rebuild_control_strategy(
            data.control_strategy,
            [],
            scheme,
            building,
            derived,
        )
    elif not scheme.control_strategy:
        scheme.control_strategy = cs.default_control_strategy()

    db.add(scheme)
    await db.commit()
    return await get_scheme(db, scheme.id)  # type: ignore[return-value]


def _build_subsystem(data: SubsystemCreate) -> SystemSubsystem:
    sub_kwargs: dict[str, Any] = dict(
        subsystem_index=data.subsystem_index,
        subsystem_type=data.subsystem_type,
        name=data.name,
        design_params=data.design_params,
    )
    if data.id is not None:
        sub_kwargs["id"] = data.id
    else:
        sub_kwargs["id"] = uuid.uuid4()
    sub = SystemSubsystem(**sub_kwargs)
    # Initialize relationship collections explicitly to avoid lazy-load attempts
    # in async context when the lists are empty (e.g. air_cooled with no towers).
    sub.combos = []
    sub.tower_groups = []
    for c in data.combos:
        combo_kwargs = c.model_dump()
        combo_kwargs["id"] = combo_kwargs.get("id") or uuid.uuid4()
        sub.combos.append(SchemeCombo(**combo_kwargs))
    for t in data.tower_groups:
        tower_kwargs = t.model_dump()
        tower_kwargs["id"] = tower_kwargs.get("id") or uuid.uuid4()
        sub.tower_groups.append(SchemeTowerGroup(**tower_kwargs))
    return sub


def _build_subsystem_with_ids(data: SubsystemCreate) -> SystemSubsystem:
    """Preserve caller-supplied ids on transient objects used by dry-run validation."""
    return _build_subsystem(data)


async def update_scheme(
    db: AsyncSession, scheme_id: uuid.UUID, data: SystemSchemeUpdate
) -> SystemScheme | None:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return None

    old_subsystems = list(scheme.subsystems)

    if data.building_id is not None and data.building_id != scheme.building_id:
        await _check_building_load_completed(db, data.building_id)

    payload = data.model_dump(exclude_unset=True, exclude={"subsystems"})
    for k, v in payload.items():
        setattr(scheme, k, v)

    if data.subsystems is not None:
        # full replacement of subsystem tree
        scheme.subsystems.clear()
        await db.flush()
        for sub in data.subsystems:
            scheme.subsystems.append(_build_subsystem(sub))

    if data.control_strategy is not None or data.subsystems is not None or not scheme.control_strategy:
        building = await db.get(Building, scheme.building_id)
        derived = await compute_scheme_derived(db, scheme)
        base_strategy = data.control_strategy if data.control_strategy is not None else scheme.control_strategy
        scheme.control_strategy = cs.rebuild_control_strategy(
            base_strategy,
            old_subsystems,
            scheme,
            building,
            derived,
        )

    await db.commit()
    return await get_scheme(db, scheme_id)


async def delete_scheme(db: AsyncSession, scheme_id: uuid.UUID) -> bool:
    scheme = await db.get(SystemScheme, scheme_id)
    if not scheme:
        return False
    await db.delete(scheme)
    await db.commit()
    return True


# ---------------------------------------------------------------------------
# Equipment-aware derived data
# ---------------------------------------------------------------------------

async def _get_equipment_map(
    db: AsyncSession, ids: list[uuid.UUID]
) -> dict[uuid.UUID, Any]:
    return await lib.load_equipment_by_ids(db, ids)


def _model_param(eq: Any | None, key: str, default: float = 0.0) -> float:
    if not eq:
        return default
    if eq.parameters and key in eq.parameters:
        try:
            return float(eq.parameters[key])
        except (TypeError, ValueError):
            return default
    return default


def _eq_brief(eq: Any | None) -> dict[str, Any] | None:
    if not eq:
        return None
    return {
        "id": str(eq.id),
        "name": eq.name,
        "brand": eq.brand,
        "model_no": eq.model_no,
        "series": (eq.parameters or {}).get("series") if eq.parameters else None,
    }


def _pump_view(pump: Any | None, active_count: int) -> dict[str, Any] | None:
    if not pump:
        return None
    flow = _model_param(pump, "flow", 0.0)
    head = _model_param(pump, "head", 0.0)
    power = _model_param(pump, "power", 0.0)
    eff = _model_param(pump, "efficiency", 0.0)
    return {
        "brand": pump.brand,
        "name": pump.name,
        "flow": round(flow * active_count, 1),
        "head": round(head, 1),
        "power": round(power * active_count, 2),
        "efficiency": round(eff * 100, 1) if eff <= 1 else round(eff, 1),
        "active_count": active_count,
    }


def _collect_subsystem_equipment_ids(sub: SystemSubsystem) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    for c in sub.combos:
        for fid in (c.primary_model_id, c.chw_pump_model_id, c.cw_pump_model_id):
            if fid is not None:
                ids.append(fid)
    for tg in sub.tower_groups:
        if tg.tower_model_id is not None:
            ids.append(tg.tower_model_id)
    return ids


def _collect_subsystem_typed_ids(sub: SystemSubsystem) -> dict[str, list[uuid.UUID]]:
    """Group equipment IDs by their known equipment type for batched typed lookups."""
    if sub.subsystem_type == "air_cooled":
        primary_type = "air_cooled_module"
    else:
        primary_type = "chiller"
    typed: dict[str, list[uuid.UUID]] = {primary_type: [], "pump": [], "cooling_tower": []}
    for c in sub.combos:
        if c.primary_model_id is not None:
            typed[primary_type].append(c.primary_model_id)
        if c.chw_pump_model_id is not None:
            typed["pump"].append(c.chw_pump_model_id)
        if c.cw_pump_model_id is not None:
            typed["pump"].append(c.cw_pump_model_id)
    for tg in sub.tower_groups:
        if tg.tower_model_id is not None:
            typed["cooling_tower"].append(tg.tower_model_id)
    return typed


async def compute_subsystem_derived(
    db: AsyncSession,
    sub: SystemSubsystem,
    eqmap: dict[uuid.UUID, Any] | None = None,
) -> dict[str, Any]:
    if eqmap is None:
        eqmap = await _get_equipment_map(db, _collect_subsystem_equipment_ids(sub))

    total_cooling = 0.0
    total_heating = 0.0
    combo_data: list[dict[str, Any]] = []

    for c in sub.combos:
        primary = eqmap.get(c.primary_model_id) if c.primary_model_id else None
        chw_pump = eqmap.get(c.chw_pump_model_id) if c.chw_pump_model_id else None
        cw_pump = eqmap.get(c.cw_pump_model_id) if c.cw_pump_model_id else None

        cop_h: float | None = None
        heating_power: float = 0.0
        if sub.subsystem_type == "chiller_plant":
            unit_cooling = (primary.capacity or 0.0) if primary else 0.0
            cooling = unit_cooling * c.primary_count
            unit_power = _model_param(primary, "power", 0.0)
            power = unit_power * c.primary_count
            cop = (cooling / power) if power > 0 else (primary.cop if primary else 0.0)
            chw_flow = _model_param(primary, "evap_flow", 0.0) * c.primary_count
            cw_flow = _model_param(primary, "cond_flow", 0.0) * c.primary_count
            evap_dp = _model_param(primary, "evap_dp", 0.0)
            cond_dp = _model_param(primary, "cond_dp", 0.0)
            heating = 0.0
        elif sub.subsystem_type == "air_cooled":
            n = c.primary_count * c.group_count
            unit_cooling = (primary.capacity or 0.0) if primary else 0.0
            unit_heating = _model_param(primary, "heating_capacity", unit_cooling * 0.95)
            unit_pwr_cool = _model_param(primary, "power", 0.0)
            unit_pwr_heat = _model_param(primary, "heating_power", unit_pwr_cool * 1.1)
            cooling = unit_cooling * n
            heating = unit_heating * n
            cop_c = (unit_cooling / unit_pwr_cool) if unit_pwr_cool > 0 else (primary.cop if primary else 0.0)
            cop_h = (unit_heating / unit_pwr_heat) if unit_pwr_heat > 0 else 0.0
            chw_flow = _model_param(primary, "cooling_flow", 0.0) * n
            cw_flow = _model_param(primary, "heating_flow", 0.0) * n
            evap_dp = _model_param(primary, "cooling_dp", 0.0)
            cond_dp = _model_param(primary, "heating_dp", 0.0)
            power = unit_pwr_cool * n
            heating_power = unit_pwr_heat * n
            cop = cop_c
        else:
            cooling = heating = power = cop = chw_flow = cw_flow = evap_dp = cond_dp = 0.0

        total_cooling += cooling
        total_heating += heating

        chw_active = max(c.chw_pump_count - c.chw_pump_backup, 0)
        cw_active = max(c.cw_pump_count - c.cw_pump_backup, 0)

        combo_data.append({
            "id": str(c.id),
            "combo_index": c.combo_index,
            "primary": _eq_brief(primary),
            "primary_count": c.primary_count,
            "group_count": c.group_count,
            "cooling_capacity": round(cooling, 1),
            "heating_capacity": round(heating, 1),
            "power": round(power, 2),
            "heating_power": round(heating_power, 2),
            "cop": round(cop, 2) if cop else None,
            "cop_heat": round(cop_h, 2) if cop_h else None,
            "chw_flow": round(chw_flow, 1),
            "cw_flow": round(cw_flow, 1),
            "evap_dp": round(evap_dp, 2),
            "cond_dp": round(cond_dp, 2),
            "chw_pump": _pump_view(chw_pump, chw_active),
            "cw_pump": _pump_view(cw_pump, cw_active),
        })

    tower_data: list[dict[str, Any]] = []
    tower_flow_total = 0.0
    for tg in sub.tower_groups:
        eq = eqmap.get(tg.tower_model_id) if tg.tower_model_id else None
        unit_flow = _model_param(eq, "flow", 0.0)
        unit_power = _model_param(eq, "power", 0.0)
        flow = unit_flow * tg.count
        tower_flow_total += flow
        tower_data.append({
            "id": str(tg.id),
            "group_index": tg.group_index,
            "model": _eq_brief(eq),
            "count": tg.count,
            "flow": round(flow, 1),
            "power": round(unit_power * tg.count, 2),
            "head": _model_param(eq, "head", 0.0),
            "inlet_temp": _model_param(eq, "inlet_temp", 0.0),
            "outlet_temp": _model_param(eq, "outlet_temp", 0.0),
            "wet_bulb": _model_param(eq, "wet_bulb", 0.0),
        })

    return {
        "id": str(sub.id),
        "subsystem_index": sub.subsystem_index,
        "subsystem_type": sub.subsystem_type,
        "name": sub.name,
        "cooling_capacity_total": round(total_cooling, 1),
        "heating_capacity_total": round(total_heating, 1),
        "combos": combo_data,
        "tower_groups": tower_data,
        "tower_flow_total": round(tower_flow_total, 1),
    }


async def compute_scheme_derived(
    db: AsyncSession, scheme: SystemScheme
) -> dict[str, Any]:
    # Batch-load all equipment referenced by this scheme in a single round-trip
    # (per typed table) instead of repeating the lookup for each subsystem.
    typed_ids: dict[str, list[uuid.UUID]] = {}
    for sub in scheme.subsystems:
        for eq_type, ids in _collect_subsystem_typed_ids(sub).items():
            typed_ids.setdefault(eq_type, []).extend(ids)
    eqmap = await lib.load_equipment_by_typed_ids(db, typed_ids) if any(typed_ids.values()) else {}

    subs_derived = []
    cool_total = 0.0
    heat_total = 0.0
    for sub in scheme.subsystems:
        d = await compute_subsystem_derived(db, sub, eqmap=eqmap)
        subs_derived.append(d)
        cool_total += d["cooling_capacity_total"]
        heat_total += d["heating_capacity_total"]
    return {
        "scheme_id": str(scheme.id),
        "cooling_capacity_total": round(cool_total, 1),
        "heating_capacity_total": round(heat_total, 1),
        "subsystems": subs_derived,
    }


# ---------------------------------------------------------------------------
# Capacity summary (per scheme: load from bound building, capacity from subsystems)
# ---------------------------------------------------------------------------

async def _compute_capacity_totals(db: AsyncSession, scheme: SystemScheme) -> tuple[float, float]:
    """Lightweight cooling/heating totals — only loads primary equipment (chiller / module)."""
    typed_ids: dict[str, list[uuid.UUID]] = {"chiller": [], "air_cooled_module": []}
    for sub in scheme.subsystems:
        key = "air_cooled_module" if sub.subsystem_type == "air_cooled" else "chiller"
        for c in sub.combos:
            if c.primary_model_id is not None:
                typed_ids.setdefault(key, []).append(c.primary_model_id)
    if not any(typed_ids.values()):
        return 0.0, 0.0
    eqmap = await lib.load_equipment_by_typed_ids(db, typed_ids)
    cool_total = 0.0
    heat_total = 0.0
    for sub in scheme.subsystems:
        for c in sub.combos:
            primary = eqmap.get(c.primary_model_id) if c.primary_model_id else None
            if not primary:
                continue
            unit_cooling = float(primary.capacity or 0.0)
            if sub.subsystem_type == "chiller_plant":
                cool_total += unit_cooling * c.primary_count
            elif sub.subsystem_type == "air_cooled":
                n = c.primary_count * c.group_count
                cool_total += unit_cooling * n
                unit_heating = _model_param(primary, "heating_capacity", unit_cooling * 0.95)
                heat_total += unit_heating * n
    return round(cool_total, 1), round(heat_total, 1)


async def get_scheme_summary(db: AsyncSession, scheme: SystemScheme) -> CapacitySummary:
    cool_total, heat_total = await _compute_capacity_totals(db, scheme)
    stmt = (
        select(SimulationResult)
        .where(SimulationResult.building_id == scheme.building_id)
        .where(SimulationResult.simulation_type == "load")
        .where(SimulationResult.status == "completed")
        .order_by(SimulationResult.created_at.desc())
        .limit(1)
    )
    latest = (await db.execute(stmt)).scalar_one_or_none()
    return CapacitySummary(
        cooling_load_peak=latest.peak_cooling_load if latest else None,
        heating_load_peak=latest.peak_heating_load if latest else None,
        cooling_capacity_total=cool_total,
        heating_capacity_total=heat_total,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _add(issues: list[ValidationIssue], **kw: Any) -> None:
    issues.append(ValidationIssue(**kw))


async def validate_subsystem(
    db: AsyncSession, scheme: SystemScheme, sub: SystemSubsystem
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    derived = await compute_subsystem_derived(db, sub)

    if sub.subsystem_type == "chiller_plant":
        _validate_chiller_plant(scheme, sub, derived, issues)
    elif sub.subsystem_type == "air_cooled":
        _validate_air_cooled(scheme, sub, derived, issues)
    return issues


def _validate_chiller_plant(scheme, sub, derived, issues):
    dp = sub.design_params or {}
    chw_pump_head_design = dp.get("chw_pump_head", 35.0)
    cw_pump_head_design = dp.get("cw_pump_head", 30.0)
    header_dp = dp.get("header_pressure_drop", 21.0)

    max_evap_dp = 0.0
    cooling_required_total = 0.0
    for c, c_orm in zip(derived["combos"], sub.combos):
        # 设备选型缺失校验（error）
        if not c_orm.primary_model_id:
            _add(issues, code="CP_CHILLER_MISSING", severity="error",
                 message=f"组合{c_orm.combo_index} 未选择冷机型号",
                 scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id, field="primary_model_id")
        if not c_orm.chw_pump_model_id:
            _add(issues, code="CP_CHW_PUMP_MISSING", severity="error",
                 message=f"组合{c_orm.combo_index} 未选择冷冻水泵型号",
                 scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id, field="chw_pump_model_id")
        if not c_orm.cw_pump_model_id:
            _add(issues, code="CP_CW_PUMP_MISSING", severity="error",
                 message=f"组合{c_orm.combo_index} 未选择冷却水泵型号",
                 scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id, field="cw_pump_model_id")

        chw_flow = c["chw_flow"]
        cw_flow = c["cw_flow"]
        cooling_required_total += cw_flow

        chw_pump = c.get("chw_pump")
        if chw_pump and chw_flow > 0:
            ratio = chw_pump["flow"] / chw_flow
            if not (0.9 <= ratio <= 1.3):
                _add(issues, code="CP_CHW_FLOW", severity="warning",
                     message=f"子系统[{sub.name}] 组合{c['combo_index']} 冷冻水泵流量与冷机不匹配 (比例 {ratio:.2f})",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
            head = chw_pump["head"]
            if not (chw_pump_head_design * 0.9 <= head <= chw_pump_head_design * 1.3):
                _add(issues, code="CP_CHW_HEAD", severity="warning",
                     message=f"子系统[{sub.name}] 组合{c['combo_index']} 冷冻水泵扬程偏离设计值",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)

        cw_pump = c.get("cw_pump")
        if cw_pump and cw_flow > 0:
            ratio = cw_pump["flow"] / cw_flow
            if not (0.9 <= ratio <= 1.3):
                _add(issues, code="CP_CW_FLOW", severity="warning",
                     message=f"子系统[{sub.name}] 组合{c['combo_index']} 冷却水泵流量与冷机不匹配 (比例 {ratio:.2f})",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
            head = cw_pump["head"]
            if not (cw_pump_head_design * 0.9 <= head <= cw_pump_head_design * 1.3):
                _add(issues, code="CP_CW_HEAD", severity="warning",
                     message=f"子系统[{sub.name}] 组合{c['combo_index']} 冷却水泵扬程偏离设计值",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)

        if c["evap_dp"] > max_evap_dp:
            max_evap_dp = c["evap_dp"]

        chw_active = chw_pump["active_count"] if chw_pump else 0
        cw_active = cw_pump["active_count"] if cw_pump else 0
        # 设备未选型时跳过连接形式 / 数量校验，避免连锁误报
        if c_orm.chw_pump_model_id:
            if c_orm.chw_connection == "direct" and chw_active != c_orm.primary_count:
                _add(issues, code="CP_CHW_DIRECT", severity="error",
                     message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 冷冻侧泵机直连时, 水泵数量-备用={chw_active} 必须等于冷机数量={c_orm.primary_count}",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
            if c_orm.chw_connection == "parallel" and chw_active < c_orm.primary_count:
                _add(issues, code="CP_CHW_PARALLEL", severity="error",
                     message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 冷冻侧水泵并联时, 水泵数量-备用 必须 ≥ 冷机数量",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
        if c_orm.cw_pump_model_id:
            if c_orm.cw_connection == "direct" and cw_active != c_orm.primary_count:
                _add(issues, code="CP_CW_DIRECT", severity="error",
                     message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 冷却侧泵机直连时, 水泵数量-备用 必须等于冷机数量",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
            if c_orm.cw_connection == "parallel" and cw_active < c_orm.primary_count:
                _add(issues, code="CP_CW_PARALLEL", severity="error",
                     message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 冷却侧水泵并联时, 水泵数量-备用 必须 ≥ 冷机数量",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)

    tower_total = derived["tower_flow_total"]
    # 冷却塔选型缺失校验（error）
    for tg in (sub.tower_groups or []):
        if not tg.tower_model_id:
            _add(issues, code="CP_TOWER_MISSING", severity="error",
                 message=f"冷却塔组 #{tg.group_index} 未选择型号",
                 scheme_id=scheme.id, subsystem_id=sub.id, field=f"tower_groups[{tg.group_index - 1}].tower_model_id")
    if cooling_required_total > 0 and tower_total > 0:
        ratio = tower_total / cooling_required_total
        if not (0.9 <= ratio <= 1.3):
            _add(issues, code="CP_TOWER_FLOW", severity="warning",
                 message=f"子系统[{sub.name}] 冷却塔可提供流量 {tower_total} 与冷机需求 {cooling_required_total:.1f} 不匹配 (比例 {ratio:.2f})",
                 scheme_id=scheme.id, subsystem_id=sub.id)

    head_budget = chw_pump_head_design - header_dp
    if max_evap_dp >= head_budget:
        _add(issues, code="CP_EVAP_DP", severity="error",
             message=f" 机房冷冻侧设计压降（冷冻水泵扬程 - 总管末端侧扬程 - 冷机冷冻侧最大压降） 应大于 0 ",
             scheme_id=scheme.id, subsystem_id=sub.id)
    elif (head_budget - max_evap_dp) < 4 and max_evap_dp > 0:
        _add(issues, code="CP_EVAP_DP_MARGIN", severity="warning",
             message=f" 机房冷冻侧设计压降（冷冻水泵扬程 - 总管末端侧扬程 - 冷机冷冻侧最大压降） < 4 (建议 ≥ 4)",
             scheme_id=scheme.id, subsystem_id=sub.id)


def _validate_air_cooled(scheme, sub, derived, issues):
    dp = sub.design_params or {}
    pipe_system = dp.get("pipe_system", "two_pipe")

    for c, c_orm in zip(derived["combos"], sub.combos):
        # 设备选型缺失校验（error）
        if not c_orm.primary_model_id:
            _add(issues, code="AC_MODULE_MISSING", severity="error",
                 message=f"组合{c_orm.combo_index} 未选择风冷模块型号",
                 scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id, field="primary_model_id")
        if not c_orm.chw_pump_model_id:
            _add(issues, code="AC_CHW_PUMP_MISSING", severity="error",
                 message=f"组合{c_orm.combo_index} 未选择" + ("冷水泵型号" if pipe_system == "four_pipe" else "水泵型号"),
                 scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id, field="chw_pump_model_id")
        if pipe_system == "four_pipe" and not c_orm.cw_pump_model_id:
            _add(issues, code="AC_HW_PUMP_MISSING", severity="error",
                 message=f"组合{c_orm.combo_index} 未选择热水泵型号",
                 scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id, field="cw_pump_model_id")

        cooling_flow = c["chw_flow"]
        heating_flow = c["cw_flow"]

        if pipe_system == "two_pipe":
            design_head = dp.get("pump_head", 35.0)
            header_dp = dp.get("header_pressure_drop", 21.0)
            ref_flow = max(cooling_flow, heating_flow)
            pump = c.get("chw_pump")
            if pump and ref_flow > 0:
                ratio = pump["flow"] / ref_flow
                if not (0.9 <= ratio <= 1.4):
                    _add(issues, code="AC_PUMP_FLOW", severity="warning",
                         message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 水泵流量与最大水流量不匹配 (比例 {ratio:.2f})",
                         scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
                head = pump["head"]
                if not (design_head <= head <= design_head * 1.4):
                    _add(issues, code="AC_PUMP_HEAD", severity="warning",
                         message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 水泵扬程偏离设计值",
                         scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
            max_dp = max(c["evap_dp"], c["cond_dp"])
            head_budget = design_head - header_dp
            if max_dp >= head_budget and max_dp > 0:
                _add(issues, code="AC_DP_BUDGET", severity="error",
                     message=f"子系统[{sub.name}] 风冷模块最大压降 {max_dp} 应 < 水泵扬程-总管末端 ({head_budget:.1f})",
                     scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)

            chw_active = pump["active_count"] if pump else 0
            if c_orm.chw_pump_model_id:
                if c_orm.chw_connection == "direct" and chw_active != c_orm.group_count:
                    _add(issues, code="AC_CONN_DIRECT", severity="error",
                         message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 直连时, 水泵数量-备用 必须等于风冷模块分组数",
                         scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
                if c_orm.chw_connection == "parallel" and chw_active < c_orm.group_count:
                    _add(issues, code="AC_CONN_PARALLEL", severity="error",
                         message=f"子系统[{sub.name}] 组合{c_orm.combo_index} 并联时, 水泵数量-备用 必须 ≥ 风冷模块分组数",
                         scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
        else:
            for label, flow, pump, conn, count, dp_key, header_key, dp_field, pump_model_id in [
                ("冷水", cooling_flow, c.get("chw_pump"), c_orm.chw_connection,
                 c_orm.chw_pump_count - c_orm.chw_pump_backup,
                 "chw_pump_head", "chw_header_pressure_drop", "evap_dp", c_orm.chw_pump_model_id),
                ("热水", heating_flow, c.get("cw_pump"), c_orm.cw_connection,
                 c_orm.cw_pump_count - c_orm.cw_pump_backup,
                 "hw_pump_head", "hw_header_pressure_drop", "cond_dp", c_orm.cw_pump_model_id),
            ]:
                if pump and flow > 0:
                    ratio = pump["flow"] / flow
                    if not (0.9 <= ratio <= 1.4):
                        _add(issues, code=f"AC4_FLOW_{label}", severity="warning",
                             message=f"子系统[{sub.name}] 组合{c_orm.combo_index} {label}泵流量不匹配",
                             scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
                    design_head = dp.get(dp_key, 35.0)
                    if not (design_head <= pump["head"] <= design_head * 1.4):
                        _add(issues, code=f"AC4_HEAD_{label}", severity="warning",
                             message=f"子系统[{sub.name}] 组合{c_orm.combo_index} {label}泵扬程偏离设计值",
                             scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
                head_budget = dp.get(dp_key, 35.0) - dp.get(header_key, 21.0)
                module_dp = c[dp_field]
                if module_dp >= head_budget and module_dp > 0:
                    _add(issues, code=f"AC4_DP_{label}", severity="error",
                         message=f"子系统[{sub.name}] 组合{c_orm.combo_index} {label}最大压降 {module_dp} 应 < {head_budget:.1f}",
                         scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
                if conn == "direct" and count != c_orm.group_count:
                    if not pump_model_id:
                        continue
                    _add(issues, code=f"AC4_CONN_DIRECT_{label}", severity="error",
                         message=f"子系统[{sub.name}] 组合{c_orm.combo_index} {label}直连时, 水泵数量-备用={count} 必须等于风冷模块分组数={c_orm.group_count}",
                         scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)
                if conn == "parallel" and count < c_orm.group_count:
                    if not pump_model_id:
                        continue
                    _add(issues, code=f"AC4_CONN_PARALLEL_{label}", severity="error",
                         message=f"子系统[{sub.name}] 组合{c_orm.combo_index} {label}并联时, 水泵数量-备用 必须 ≥ 风冷模块分组数",
                         scheme_id=scheme.id, subsystem_id=sub.id, combo_id=c_orm.id)


async def validate_selection_scheme(db: AsyncSession, scheme: SystemScheme) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not scheme.subsystems:
        _add(issues, code="SCHEME_NO_SUB", severity="error",
             message="方案至少需要一个子系统",
             scheme_id=scheme.id)
    summary = await get_scheme_summary(db, scheme)
    if summary.cooling_load_peak is not None:
        if summary.cooling_capacity_total < summary.cooling_load_peak:
            _add(issues, code="CAP_COOL", severity="warning",
                 message=f"方案[{scheme.name}] 装机容量(制冷) {summary.cooling_capacity_total} kW < 冷负荷峰值 {summary.cooling_load_peak} kW，请补充设备",
                 scheme_id=scheme.id)
    if summary.heating_load_peak is not None and summary.heating_load_peak > 0:
        if summary.heating_capacity_total < summary.heating_load_peak:
            _add(issues, code="CAP_HEAT", severity="warning",
                 message=f"方案[{scheme.name}] 装机容量(制热) {summary.heating_capacity_total} kW < 热负荷峰值 {summary.heating_load_peak} kW，请补充设备",
                 scheme_id=scheme.id)
    for sub in scheme.subsystems:
        issues.extend(await validate_subsystem(db, scheme, sub))
    return issues


async def validate_strategy_scheme(db: AsyncSession, scheme: SystemScheme) -> list[ValidationIssue]:
    building = await db.get(Building, scheme.building_id)
    derived = await compute_scheme_derived(db, scheme)
    strategy = cs.rebuild_control_strategy(
        scheme.control_strategy,
        list(scheme.subsystems),
        scheme,
        building,
        derived,
    )
    return cs.validate_control_strategy(scheme, building, derived, strategy)


async def validate_scheme(db: AsyncSession, scheme: SystemScheme) -> list[ValidationIssue]:
    issues = await validate_selection_scheme(db, scheme)
    issues.extend(await validate_strategy_scheme(db, scheme))
    return issues


async def validate_project_schemes(
    db: AsyncSession, project_id: uuid.UUID
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    schemes = await list_schemes(db, project_id)
    if len(schemes) < 1:
        _add(issues, code="GLOBAL_MIN", severity="error", message="至少需要 1 个系统方案")
    if len(schemes) > 5:
        _add(issues, code="GLOBAL_MAX", severity="error", message="至多 5 个系统方案")
    for s in schemes:
        issues.extend(await validate_scheme(db, s))
    has_error = any(i.severity == "error" for i in issues)
    return ValidationReport(valid=not has_error, issues=issues)


async def validate_single_scheme(
    db: AsyncSession, scheme_id: uuid.UUID
) -> ValidationReport:
    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return ValidationReport(valid=False, issues=[])
    issues = await validate_scheme(db, scheme)
    has_error = any(i.severity == "error" for i in issues)
    return ValidationReport(valid=not has_error, issues=issues)


async def validate_scheme_payload(
    db: AsyncSession, scheme_id: uuid.UUID, data: SystemSchemeUpdate
) -> ValidationReport:
    """Dry-run validation: apply ``data`` to the scheme in-memory, run the
    same validators that ``validate_single_scheme`` would, then **rollback** so
    nothing is persisted. Used by the frontend to gate Save when there are
    unresolved errors in the user's edits.
    """
    from sqlalchemy.orm.attributes import set_committed_value

    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return ValidationReport(valid=False, issues=[])
    try:
        # Apply edits *purely in memory* — DO NOT flush to DB. Flushing would
        # detach old children and require a re-fetch (which is brittle in
        # async SQLAlchemy with selectinload), and would also expose the
        # validator to lazy-loaded relationships that can't issue async IO
        # mid-iteration. Since `_build_subsystem` already populates
        # `sub.combos` and `sub.tower_groups` collections in memory, we can
        # walk them directly without touching the DB for relationship loads.
        payload = data.model_dump(exclude_unset=True, exclude={"subsystems"})
        for k, v in payload.items():
            setattr(scheme, k, v)
        if data.subsystems is not None:
            new_subs: list[SystemSubsystem] = []
            for sub_data in data.subsystems:
                s = _build_subsystem_with_ids(sub_data)
                # Mark relationships as already-loaded so the lazyloader will
                # NOT try to issue a SQL query (which would fail in async
                # context) the next time .combos / .tower_groups is read.
                set_committed_value(s, "combos", list(s.combos))
                set_committed_value(s, "tower_groups", list(s.tower_groups))
                new_subs.append(s)
            # Replace the in-memory collection without going through cascade
            # delete-orphan flushing.
            set_committed_value(scheme, "subsystems", new_subs)
        async with db.begin_nested():
            issues = await validate_selection_scheme(db, scheme)
    finally:
        # Discard any in-memory mutations so the dry-run is side-effect free.
        await db.rollback()
    has_error = any(i.severity == "error" for i in issues)
    return ValidationReport(valid=not has_error, issues=issues)


async def validate_strategy_payload(
    db: AsyncSession, scheme_id: uuid.UUID, data: SystemSchemeUpdate
) -> ValidationReport:
    from sqlalchemy.orm.attributes import set_committed_value

    scheme = await get_scheme(db, scheme_id)
    if not scheme:
        return ValidationReport(valid=False, issues=[])
    old_subsystems = list(scheme.subsystems)
    try:
        payload = data.model_dump(exclude_unset=True, exclude={"subsystems"})
        for k, v in payload.items():
            setattr(scheme, k, v)
        if data.subsystems is not None:
            new_subs: list[SystemSubsystem] = []
            for sub_data in data.subsystems:
                s = _build_subsystem_with_ids(sub_data)
                set_committed_value(s, "combos", list(s.combos))
                set_committed_value(s, "tower_groups", list(s.tower_groups))
                new_subs.append(s)
            set_committed_value(scheme, "subsystems", new_subs)
        building = await db.get(Building, scheme.building_id)
        derived = await compute_scheme_derived(db, scheme)
        if data.control_strategy is not None or data.subsystems is not None or not scheme.control_strategy:
            scheme.control_strategy = cs.rebuild_control_strategy(
                data.control_strategy if data.control_strategy is not None else scheme.control_strategy,
                old_subsystems,
                scheme,
                building,
                derived,
            )
        async with db.begin_nested():
            issues = cs.validate_control_strategy(scheme, building, derived, scheme.control_strategy or {})
    finally:
        await db.rollback()
    has_error = any(i.severity == "error" for i in issues)
    return ValidationReport(valid=not has_error, issues=issues)


# ---------------------------------------------------------------------------
# List items for the project main page (scheme list cards)
# ---------------------------------------------------------------------------

async def list_scheme_items(
    db: AsyncSession, project_id: uuid.UUID
) -> list[dict[str, Any]]:
    schemes = await list_schemes(db, project_id)
    items: list[dict[str, Any]] = []
    bld_ids = {s.building_id for s in schemes}
    bld_map: dict[uuid.UUID, Building] = {}
    if bld_ids:
        rows = (await db.execute(select(Building).where(Building.id.in_(bld_ids)))).scalars().all()
        bld_map = {b.id: b for b in rows}

    energy_map: dict[uuid.UUID, SimulationResult] = {}
    scheme_ids = [scheme.id for scheme in schemes]
    if scheme_ids:
        energy_rows = (
            await db.execute(
                select(SimulationResult)
                .where(
                    SimulationResult.scheme_id.in_(scheme_ids),
                    SimulationResult.simulation_type == "scheme_energy",
                    SimulationResult.status == "completed",
                )
                .order_by(SimulationResult.created_at.desc())
            )
        ).scalars().all()
        for energy_result in energy_rows:
            if energy_result.scheme_id is not None:
                energy_map.setdefault(energy_result.scheme_id, energy_result)

    for s in schemes:
        summary = await get_scheme_summary(db, s)
        issues = await validate_scheme(db, s)
        has_err = any(i.severity == "error" for i in issues)
        energy_result = energy_map.get(s.id)
        delivered = float((energy_result.total_cooling_load or 0.0) + (energy_result.total_heating_load or 0.0)) if energy_result else 0.0
        consumed = float(energy_result.total_energy or 0.0) if energy_result else 0.0
        items.append({
            "id": s.id,
            "name": s.name,
            "scheme_index": s.scheme_index,
            "project_id": s.project_id,
            "building_id": s.building_id,
            "building_name": bld_map.get(s.building_id).name if bld_map.get(s.building_id) else None,
            "subsystem_count": len(s.subsystems),
            "safety_margin": s.safety_margin,
            "cooling_capacity_total": summary.cooling_capacity_total,
            "heating_capacity_total": summary.heating_capacity_total,
            "cooling_load_peak": summary.cooling_load_peak,
            "heating_load_peak": summary.heating_load_peak,
            "annual_cooling_total": energy_result.total_cooling_load if energy_result else None,
            "annual_heating_total": energy_result.total_heating_load if energy_result else None,
            "annual_energy_total": energy_result.total_energy if energy_result else None,
            "system_cop": round(delivered / consumed, 3) if consumed > 0 else None,
            "annual_cost": energy_result.total_cost if energy_result else None,
            "has_error": has_err,
            "updated_at": s.updated_at,
        })
    return items


# ---------------------------------------------------------------------------
# Default factories
# ---------------------------------------------------------------------------

def default_design_params(subsystem_type: str) -> dict[str, Any]:
    if subsystem_type == "chiller_plant":
        return {
            "chw_supply_temp": 7.0, "chw_delta_temp": 5.0,
            "chw_pump_head": 35.0, "header_pressure_drop": 21.0,
            "cw_supply_temp": 30.0, "cw_delta_temp": 5.0,
            "cw_pump_head": 30.0,
        }
    if subsystem_type == "air_cooled":
        return {
            "cooling_supply_temp": 7.0, "cooling_delta_temp": 5.0,
            "heating_supply_temp": 45.0, "heating_delta_temp": 5.0,
            "pipe_system": "two_pipe",
            "pump_head": 35.0, "header_pressure_drop": 21.0,
            "chw_pump_head": 35.0, "chw_header_pressure_drop": 21.0,
            "hw_pump_head": 35.0, "hw_header_pressure_drop": 21.0,
        }
    return {}


def default_control_strategy() -> dict[str, Any]:
    return cs.default_control_strategy()
