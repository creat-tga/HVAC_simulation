"""Library service: weather, equipment, building templates."""

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.library import (
    WeatherFile,
    EquipmentModel,
    EquipmentChiller,
    EquipmentAirCooledModule,
    EquipmentPump,
    EquipmentCoolingTower,
    EquipmentBoiler,
    BuildingTemplate,
)
from app.models.building import Building
from app.simulation.energyplus.weather_utils import parse_epw_header


# ---------- Weather ----------

WEATHER_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "weather"
USER_WEATHER_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "weather_user"


async def seed_preset_weather(db: AsyncSession) -> None:
    """Scan data/weather/*.epw and seed any not yet in DB."""
    if not WEATHER_DIR.exists():
        return
    existing = (await db.execute(select(WeatherFile.file_path))).scalars().all()
    existing_set = set(existing)
    for epw in WEATHER_DIR.glob("*.epw"):
        rel = str(epw.resolve())
        if rel in existing_set:
            continue
        meta = _safe_parse(epw)
        # Parse filename pattern: CHN_<prov>_<city>.<wmo>_<source>.epw
        name = epw.stem
        parts = name.split("_")
        country = parts[0] if len(parts) > 0 else "CHN"
        province = parts[1] if len(parts) > 1 else None
        city_part = parts[2] if len(parts) > 2 else name
        city = city_part.split(".")[0] if "." in city_part else city_part
        wmo = None
        source = None
        if "." in city_part:
            after = city_part.split(".", 1)[1]
            if "_" in after:
                wmo, source = after.split("_", 1)
            else:
                wmo = after
        elif len(parts) > 3:
            tail = parts[-1]
            if "_" in tail:
                wmo, source = tail.split("_", 1)

        wf = WeatherFile(
            name=name,
            province=province,
            city=city,
            country=country,
            source=source,
            wmo=wmo,
            file_path=rel,
            latitude=meta.get("latitude"),
            longitude=meta.get("longitude"),
            elevation=meta.get("elevation"),
            is_preset=True,
            owner_id=None,
        )
        db.add(wf)
    await db.commit()


def _safe_parse(epw: Path) -> dict[str, Any]:
    try:
        meta = parse_epw_header(epw)
        return {
            "latitude": meta.get("lat"),
            "longitude": meta.get("lon"),
            "elevation": meta.get("elev"),
        }
    except Exception:
        return {}


async def list_weather_files(
    db: AsyncSession, owner_id: uuid.UUID | None, search: str | None = None
) -> list[WeatherFile]:
    """List preset + user's own weather files."""
    stmt = select(WeatherFile)
    if owner_id is not None:
        stmt = stmt.where(or_(WeatherFile.is_preset == True, WeatherFile.owner_id == owner_id))  # noqa: E712
    else:
        stmt = stmt.where(WeatherFile.is_preset == True)  # noqa: E712
    if search:
        kw = f"%{search}%"
        stmt = stmt.where(or_(WeatherFile.name.ilike(kw), WeatherFile.city.ilike(kw), WeatherFile.province.ilike(kw)))
    stmt = stmt.order_by(WeatherFile.is_preset.desc(), WeatherFile.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


async def upload_weather_file(
    db: AsyncSession,
    owner_id: uuid.UUID,
    filename: str,
    content: bytes,
    name: str | None,
    province: str | None,
    city: str | None,
) -> WeatherFile:
    USER_WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = filename.replace("\\", "/").split("/")[-1]
    dest = USER_WEATHER_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    dest.write_bytes(content)
    meta = _safe_parse(dest)
    wf = WeatherFile(
        name=name or safe_name.removesuffix(".epw"),
        province=province,
        city=city,
        country="USR",
        file_path=str(dest.resolve()),
        latitude=meta.get("latitude"),
        longitude=meta.get("longitude"),
        elevation=meta.get("elevation"),
        is_preset=False,
        owner_id=owner_id,
    )
    db.add(wf)
    await db.commit()
    await db.refresh(wf)
    return wf


async def delete_weather_file(db: AsyncSession, wf_id: uuid.UUID, owner_id: uuid.UUID, is_admin: bool) -> None:
    wf = await db.get(WeatherFile, wf_id)
    if not wf:
        return
    if wf.is_preset and not is_admin:
        raise PermissionError("无权删除预置气象文件")
    if not wf.is_preset and wf.owner_id != owner_id and not is_admin:
        raise PermissionError("无权删除他人气象文件")
    # Delete physical file if user-uploaded
    if not wf.is_preset:
        try:
            Path(wf.file_path).unlink(missing_ok=True)
        except Exception:
            pass
    await db.delete(wf)
    await db.commit()


# ---------- Equipment ----------

EquipmentRecord = (
    EquipmentModel
    | EquipmentChiller
    | EquipmentAirCooledModule
    | EquipmentPump
    | EquipmentCoolingTower
    | EquipmentBoiler
)

_TYPED_EQUIPMENT_MODEL_MAP = {
    "chiller": EquipmentChiller,
    "air_cooled_module": EquipmentAirCooledModule,
    "pump": EquipmentPump,
    "cooling_tower": EquipmentCoolingTower,
    "boiler": EquipmentBoiler,
}
_TYPED_EQUIPMENT_MODELS = tuple(_TYPED_EQUIPMENT_MODEL_MAP.values())


def equipment_model_for_type(equipment_type: str):
    return _TYPED_EQUIPMENT_MODEL_MAP.get(equipment_type)


def _apply_equipment_scope(stmt, model, owner_id: uuid.UUID, scope: str):
    if scope == "public":
        return stmt.where(model.is_public == True)  # noqa: E712
    if scope == "mine":
        return stmt.where(model.owner_id == owner_id)
    return stmt.where(or_(model.is_public == True, model.owner_id == owner_id))  # noqa: E712


async def _fetch_equipment_rows(
    db: AsyncSession,
    model,
    owner_id: uuid.UUID,
    scope: str,
    equipment_type: str | None = None,
) -> list[EquipmentRecord]:
    stmt = select(model)
    stmt = _apply_equipment_scope(stmt, model, owner_id, scope)
    if model is EquipmentModel and equipment_type:
        stmt = stmt.where(EquipmentModel.equipment_type == equipment_type)
    rows = (await db.execute(stmt)).scalars().all()
    return list(rows)


def _equipment_dedupe_key(eq: EquipmentRecord) -> tuple[str, str, str]:
    return (
        eq.equipment_type,
        ((eq.model_no or eq.name or "").strip().lower()),
        str(eq.owner_id or ""),
    )


def _sort_equipment_rows(rows: list[EquipmentRecord]) -> list[EquipmentRecord]:
    return sorted(
        rows,
        key=lambda eq: (
            (eq.brand or "").strip().lower(),
            (eq.model_no or "").strip().lower(),
            (eq.name or "").strip().lower(),
        ),
    )


def _dedupe_equipment_rows(rows: list[EquipmentRecord]) -> list[EquipmentRecord]:
    grouped: dict[tuple[str, str, str], list[EquipmentRecord]] = {}
    for row in rows:
        grouped.setdefault(_equipment_dedupe_key(row), []).append(row)

    deduped: list[EquipmentRecord] = []
    for same_key_rows in grouped.values():
        typed_rows = [row for row in same_key_rows if not isinstance(row, EquipmentModel)]
        if typed_rows:
            # Only remove duplicates introduced by the legacy shared table.
            # Keep all per-device-table rows, even when the JSON source contains
            # multiple records with the same model number.
            deduped.extend(typed_rows)
            continue
        deduped.extend(same_key_rows)

    return _sort_equipment_rows(deduped)


def _match_equipment_filters(
    eq: EquipmentRecord,
    *,
    name: str | None = None,
    capacity_min: float | None = None,
    capacity_max: float | None = None,
    flow_min: float | None = None,
    flow_max: float | None = None,
    head_min: float | None = None,
    head_max: float | None = None,
    efficiency_min: float | None = None,
    efficiency_max: float | None = None,
) -> bool:
    params = eq.parameters or {}
    if name:
        kw = name.strip().lower()
        haystacks = [eq.name or "", eq.model_no or "", eq.brand or ""]
        if not any(kw in item.lower() for item in haystacks):
            return False
    if capacity_min is not None and float(eq.capacity or 0) < capacity_min:
        return False
    if capacity_max is not None and float(eq.capacity or 0) > capacity_max:
        return False
    if flow_min is not None and float(params.get("flow", 0) or 0) < flow_min:
        return False
    if flow_max is not None and float(params.get("flow", 0) or 0) > flow_max:
        return False
    if head_min is not None and float(params.get("head", 0) or 0) < head_min:
        return False
    if head_max is not None and float(params.get("head", 0) or 0) > head_max:
        return False
    if efficiency_min is not None and float(params.get("efficiency", 0) or 0) < efficiency_min:
        return False
    if efficiency_max is not None and float(params.get("efficiency", 0) or 0) > efficiency_max:
        return False
    return True

async def list_equipment(
    db: AsyncSession,
    owner_id: uuid.UUID,
    equipment_type: str | None = None,
    scope: str = "all",  # 'all' | 'public' | 'mine'
) -> list[EquipmentRecord]:
    """List equipment from the per-device typed tables only.

    The legacy shared `equipment_models` table is retained in the schema for
    `load_equipment_by_ids` (so existing scheme records can still resolve old
    references), but it is no longer surfaced through the picker / library UI.
    """
    rows: list[EquipmentRecord] = []
    if equipment_type:
        typed_model = equipment_model_for_type(equipment_type)
        if typed_model is not None:
            rows.extend(await _fetch_equipment_rows(db, typed_model, owner_id, scope, equipment_type))
        return _sort_equipment_rows(rows)

    for typed_model in _TYPED_EQUIPMENT_MODELS:
        rows.extend(await _fetch_equipment_rows(db, typed_model, owner_id, scope))
    return _sort_equipment_rows(rows)


async def search_equipment_records(
    db: AsyncSession,
    owner_id: uuid.UUID,
    equipment_type: str,
    *,
    scope: str = "all",
    name: str | None = None,
    capacity_min: float | None = None,
    capacity_max: float | None = None,
    flow_min: float | None = None,
    flow_max: float | None = None,
    head_min: float | None = None,
    head_max: float | None = None,
    efficiency_min: float | None = None,
    efficiency_max: float | None = None,
) -> list[EquipmentRecord]:
    rows = await list_equipment(db, owner_id, equipment_type, scope)
    return [
        row for row in rows
        if _match_equipment_filters(
            row,
            name=name,
            capacity_min=capacity_min,
            capacity_max=capacity_max,
            flow_min=flow_min,
            flow_max=flow_max,
            head_min=head_min,
            head_max=head_max,
            efficiency_min=efficiency_min,
            efficiency_max=efficiency_max,
        )
    ]


async def load_equipment_by_ids(
    db: AsyncSession,
    ids: list[uuid.UUID],
) -> dict[uuid.UUID, EquipmentRecord]:
    if not ids:
        return {}

    result: dict[uuid.UUID, EquipmentRecord] = {}
    unique_ids = list(dict.fromkeys(ids))
    for model in (*_TYPED_EQUIPMENT_MODELS, EquipmentModel):
        rows = (await db.execute(select(model).where(model.id.in_(unique_ids)))).scalars().all()
        for row in rows:
            result.setdefault(row.id, row)
    return result


async def create_equipment(db: AsyncSession, owner_id: uuid.UUID, is_admin: bool, data: dict) -> EquipmentModel:
    is_public = bool(data.get("is_public")) and is_admin
    eq = EquipmentModel(
        owner_id=owner_id,
        is_public=is_public,
        **{k: v for k, v in data.items() if k != "is_public"},
    )
    db.add(eq)
    await db.commit()
    await db.refresh(eq)
    return eq


async def update_equipment(
    db: AsyncSession, eq_id: uuid.UUID, owner_id: uuid.UUID, is_admin: bool, data: dict
) -> EquipmentModel | None:
    eq = await db.get(EquipmentModel, eq_id)
    if not eq:
        return None
    if eq.owner_id != owner_id and not is_admin:
        raise PermissionError("无权编辑他人设备模型")
    for k, v in data.items():
        if v is None:
            continue
        if k == "is_public" and not is_admin:
            continue
        setattr(eq, k, v)
    await db.commit()
    await db.refresh(eq)
    return eq


async def delete_equipment(db: AsyncSession, eq_id: uuid.UUID, owner_id: uuid.UUID, is_admin: bool) -> None:
    eq = await db.get(EquipmentModel, eq_id)
    if not eq:
        return
    if eq.owner_id != owner_id and not is_admin:
        raise PermissionError("无权删除他人设备模型")
    await db.delete(eq)
    await db.commit()


# ---------- Building Templates ----------

async def list_templates(
    db: AsyncSession, owner_id: uuid.UUID, scope: str = "all"
) -> list[BuildingTemplate]:
    stmt = select(BuildingTemplate)
    if scope == "public":
        stmt = stmt.where(BuildingTemplate.is_public == True)  # noqa: E712
    elif scope == "mine":
        stmt = stmt.where(BuildingTemplate.owner_id == owner_id)
    else:
        stmt = stmt.where(or_(BuildingTemplate.is_public == True, BuildingTemplate.owner_id == owner_id))  # noqa: E712
    stmt = stmt.order_by(BuildingTemplate.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


async def create_template(db: AsyncSession, owner_id: uuid.UUID, is_admin: bool, data: dict) -> BuildingTemplate:
    is_public = bool(data.get("is_public")) and is_admin
    payload = {k: v for k, v in data.items() if k != "is_public"}
    # Convert pydantic zones to plain dicts if needed
    zones = payload.get("zones")
    if zones is not None:
        payload["zones"] = [z.model_dump() if hasattr(z, "model_dump") else z for z in zones]
    tpl = BuildingTemplate(owner_id=owner_id, is_public=is_public, **payload)
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def update_template(
    db: AsyncSession, tpl_id: uuid.UUID, owner_id: uuid.UUID, is_admin: bool, data: dict
) -> BuildingTemplate | None:
    tpl = await db.get(BuildingTemplate, tpl_id)
    if not tpl:
        return None
    if tpl.owner_id != owner_id and not is_admin:
        raise PermissionError("无权编辑他人模板")
    for k, v in data.items():
        if v is None:
            continue
        if k == "is_public" and not is_admin:
            continue
        if k == "zones":
            v = [z.model_dump() if hasattr(z, "model_dump") else z for z in v]
        setattr(tpl, k, v)
    await db.commit()
    await db.refresh(tpl)
    return tpl


async def delete_template(db: AsyncSession, tpl_id: uuid.UUID, owner_id: uuid.UUID, is_admin: bool) -> None:
    tpl = await db.get(BuildingTemplate, tpl_id)
    if not tpl:
        return
    if tpl.owner_id != owner_id and not is_admin:
        raise PermissionError("无权删除他人模板")
    await db.delete(tpl)
    await db.commit()


async def clone_template_to_project(
    db: AsyncSession, tpl_id: uuid.UUID, project_id: uuid.UUID, override_name: str | None = None
) -> Building:
    tpl = await db.get(BuildingTemplate, tpl_id)
    if not tpl:
        raise ValueError("模板不存在")
    bld = Building(
        project_id=project_id,
        name=override_name or tpl.name,
        building_type=tpl.building_type,
        total_area=tpl.total_area,
        floor_count=tpl.floor_count,
        location=None,
        climate_zone=tpl.climate_zone,
        envelope_params=tpl.envelope_params,
        zones=tpl.zones,
    )
    db.add(bld)
    await db.commit()
    await db.refresh(bld)
    return bld


async def clone_building_to_template(
    db: AsyncSession, building_id: uuid.UUID, owner_id: uuid.UUID, is_admin: bool,
    name: str | None, description: str | None, is_public: bool,
) -> BuildingTemplate:
    bld = await db.get(Building, building_id)
    if not bld:
        raise ValueError("建筑不存在")
    tpl = BuildingTemplate(
        name=name or bld.name,
        description=description,
        building_type=bld.building_type,
        total_area=bld.total_area,
        floor_count=bld.floor_count,
        climate_zone=bld.climate_zone,
        envelope_params=bld.envelope_params,
        zones=bld.zones,
        is_public=bool(is_public) and is_admin,
        owner_id=owner_id,
    )
    db.add(tpl)
    await db.commit()
    await db.refresh(tpl)
    return tpl


# ---------- Equipment Seeding (preset public models) ----------

PRESET_EQUIPMENT: list[dict] = [
    # ----- Chillers -----
    {"name": "CE800离心式水冷冷水机组", "equipment_type": "chiller", "brand": "格力",
     "model_no": "CE800", "capacity": 800, "cop": 5.8,
     "parameters": {"series": "CE系列离心式", "power": 137.9, "evap_flow": 137.5, "cond_flow": 165.0,
                    "evap_dp": 6.5, "cond_dp": 7.0}},
    {"name": "CE1200离心式水冷冷水机组", "equipment_type": "chiller", "brand": "格力",
     "model_no": "CE1200", "capacity": 1200, "cop": 5.9,
     "parameters": {"series": "CE系列离心式", "power": 203.4, "evap_flow": 206.4, "cond_flow": 247.5,
                    "evap_dp": 7.0, "cond_dp": 7.5}},
    {"name": "CVE600永磁同步变频离心机", "equipment_type": "chiller", "brand": "格力",
     "model_no": "CVE600", "capacity": 600, "cop": 6.4,
     "parameters": {"series": "CVE系列永磁同步变频", "power": 93.8, "evap_flow": 103.2, "cond_flow": 123.8,
                    "evap_dp": 5.5, "cond_dp": 6.0}},
    {"name": "CVE1000永磁同步变频离心机", "equipment_type": "chiller", "brand": "格力",
     "model_no": "CVE1000", "capacity": 1000, "cop": 6.5,
     "parameters": {"series": "CVE系列永磁同步变频", "power": 153.8, "evap_flow": 172.0, "cond_flow": 206.4,
                    "evap_dp": 6.0, "cond_dp": 6.5}},
    # ----- Air-cooled modules -----
    {"name": "LSQWRF130风冷模块机组", "equipment_type": "air_cooled_module", "brand": "美的",
     "model_no": "LSQWRF130", "capacity": 130, "cop": 3.2,
     "parameters": {"series": "LSQWRF系列", "power": 40.6, "heating_capacity": 140.0, "heating_power": 42.0,
                    "cooling_flow": 22.4, "heating_flow": 24.1, "cooling_dp": 5.0, "heating_dp": 5.0}},
    {"name": "LSQWRF200风冷模块机组", "equipment_type": "air_cooled_module", "brand": "美的",
     "model_no": "LSQWRF200", "capacity": 200, "cop": 3.1,
     "parameters": {"series": "LSQWRF系列", "power": 64.5, "heating_capacity": 215.0, "heating_power": 67.2,
                    "cooling_flow": 34.4, "heating_flow": 37.0, "cooling_dp": 5.5, "heating_dp": 5.5}},
    # ----- Pumps -----
    {"name": "KQL150-200冷冻水泵", "equipment_type": "pump", "brand": "凯泉",
     "model_no": "KQL150-200/4-30", "capacity": None, "cop": None,
     "parameters": {"flow": 200, "head": 35, "power": 30, "efficiency": 0.78}},
    {"name": "KQL200-300冷冻水泵", "equipment_type": "pump", "brand": "凯泉",
     "model_no": "KQL200-300/4-45", "capacity": None, "cop": None,
     "parameters": {"flow": 300, "head": 32, "power": 37, "efficiency": 0.82}},
    {"name": "TPE100-200冷却水泵", "equipment_type": "pump", "brand": "格兰富",
     "model_no": "TPE100-200/2", "capacity": None, "cop": None,
     "parameters": {"flow": 240, "head": 30, "power": 30, "efficiency": 0.79}},
    {"name": "IRG65-160中央空调循环泵", "equipment_type": "pump", "brand": "威乐",
     "model_no": "IRG65-160", "capacity": None, "cop": None,
     "parameters": {"flow": 50, "head": 35, "power": 7.5, "efficiency": 0.72}},
    # ----- Cooling towers -----
    {"name": "BAC-3408方形横流冷却塔", "equipment_type": "cooling_tower", "brand": "BAC",
     "model_no": "BAC-3408", "capacity": None, "cop": None,
     "parameters": {"flow": 200, "head": 6, "power": 7.5, "inlet_temp": 35, "outlet_temp": 30, "wet_bulb": 28}},
    {"name": "LXT-300方形逆流冷却塔", "equipment_type": "cooling_tower", "brand": "良机",
     "model_no": "LXT-300", "capacity": None, "cop": None,
     "parameters": {"flow": 300, "head": 5, "power": 11, "inlet_temp": 37, "outlet_temp": 32, "wet_bulb": 28}},
    {"name": "LXT-500方形逆流冷却塔", "equipment_type": "cooling_tower", "brand": "良机",
     "model_no": "LXT-500", "capacity": None, "cop": None,
     "parameters": {"flow": 500, "head": 6, "power": 18.5, "inlet_temp": 37, "outlet_temp": 32, "wet_bulb": 28}},
]


async def seed_preset_equipment(db: AsyncSession) -> None:
    """Seed public preset equipment models if missing."""
    existing = (await db.execute(
        select(EquipmentModel.model_no).where(EquipmentModel.is_public == True)  # noqa: E712
    )).scalars().all()
    existing_set = {m for m in existing if m}
    for entry in PRESET_EQUIPMENT:
        if entry["model_no"] in existing_set:
            continue
        eq = EquipmentModel(
            name=entry["name"],
            equipment_type=entry["equipment_type"],
            brand=entry["brand"],
            model_no=entry["model_no"],
            capacity=entry["capacity"],
            cop=entry["cop"],
            parameters=entry["parameters"],
            is_public=True,
            owner_id=None,
        )
        db.add(eq)
    await db.commit()


# ---------- Equipment Seeding (from data/equipment/*.json) ----------

EQUIPMENT_DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "equipment"

# Map filename -> equipment_type
_EQ_FILE_TYPE_MAP: dict[str, str] = {
    "pump.json": "pump",
    "cooling_tower.json": "cooling_tower",
    "tower.json": "cooling_tower",  # accept alias since user-provided file is named tower.json
    "chiller.json": "chiller",
    "air_cooled_module.json": "air_cooled_module",
    "boiler.json": "boiler",
}


def _to_float(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return None
    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100.0
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def _normalize_equipment_entry(eq_type: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a raw JSON entry (using user-supplied camelCase fields) into the
    internal EquipmentModel shape: {name, equipment_type, brand, model_no,
    capacity, cop, parameters}. Returns None for entries that should be skipped
    (e.g. soft-deleted, missing model identifier).
    """
    if not isinstance(raw, dict):
        return None
    if int(raw.get("deleted") or 0) == 1:
        return None
    brand = (raw.get("factory") or raw.get("brand") or "").strip() or None
    model_no = (raw.get("model") or raw.get("model_no") or "").strip()
    if not model_no:
        return None

    params: dict[str, Any] = {}
    capacity: float | None = None
    cop: float | None = None
    name: str

    if eq_type == "pump":
        params = {
            "flow": _to_float(raw.get("deliveryDesign")),
            "head": _to_float(raw.get("deliveryHead")),
            "power": _to_float(raw.get("powerDesign")),
            "efficiency": _to_float(raw.get("efficiency")),
        }
        # Optional extras
        if raw.get("frequencyMax") is not None:
            params["frequency_max"] = _to_float(raw.get("frequencyMax"))
        if raw.get("frequencyMin") is not None:
            params["frequency_min"] = _to_float(raw.get("frequencyMin"))
        if raw.get("powerEm") is not None:
            params["power_em"] = _to_float(raw.get("powerEm"))
        name = f"{brand or ''}{model_no}".strip() or model_no
    elif eq_type == "cooling_tower":
        params = {
            "flow": _to_float(raw.get("delivery")),
            "head": _to_float(raw.get("deliveryHead")),
            "power": _to_float(raw.get("powerEm")),
            "inlet_temp": _to_float(raw.get("wit")),
            "outlet_temp": _to_float(raw.get("wot")),
            "wet_bulb": _to_float(raw.get("wt")),
        }
        if raw.get("dt") is not None:
            params["delta_t"] = _to_float(raw.get("dt"))
        name = f"{brand or ''}{model_no}".strip() or model_no
    elif eq_type == "chiller":
        capacity = _to_float(raw.get("capacity"))
        cop = _to_float(raw.get("cop"))
        params = {
            "series": raw.get("series") or "",
            "power": _to_float(raw.get("powerDesign")),
            "evap_flow": _to_float(raw.get("evapFlow")),
            "cond_flow": _to_float(raw.get("condFlow")),
            "evap_dp": _to_float(raw.get("evapDp")),
            "cond_dp": _to_float(raw.get("condDp")),
        }
        name = f"{brand or ''}{model_no}".strip() or model_no
    elif eq_type == "air_cooled_module":
        capacity = _to_float(raw.get("capacity"))
        cop = _to_float(raw.get("cop"))
        params = {
            "series": raw.get("series") or "",
            "power": _to_float(raw.get("powerDesign")),
            "heating_capacity": _to_float(raw.get("heatingCapacity")),
            "heating_power": _to_float(raw.get("heatingPower")),
            "cooling_flow": _to_float(raw.get("coolingFlow")),
            "heating_flow": _to_float(raw.get("heatingFlow")),
            "cooling_dp": _to_float(raw.get("coolingDp")),
            "heating_dp": _to_float(raw.get("heatingDp")),
        }
        name = f"{brand or ''}{model_no}".strip() or model_no
    else:
        # Unknown equipment_type: pass through raw as parameters.
        params = {k: v for k, v in raw.items() if k not in {"id", "factory", "model", "deleted"}}
        name = f"{brand or ''}{model_no}".strip() or model_no

    # Drop None-valued keys to keep parameters clean
    params = {k: v for k, v in params.items() if v is not None and v != ""}
    return {
        "name": name,
        "equipment_type": eq_type,
        "brand": brand,
        "model_no": model_no,
        "capacity": capacity,
        "cop": cop,
        "parameters": params,
    }


async def sync_equipment_from_data(db: AsyncSession, data_dir: Path | None = None) -> dict[str, int]:
    """Wipe the per-device equipment tables and rebuild them from
    data/equipment/*.json. Also clears legacy public rows from
    `equipment_models` for the matching types so the picker stays clean.
    User-owned (non-public) entries are preserved.
    """
    import json as _json
    import logging as _logging
    from sqlalchemy import delete as sa_delete
    log = _logging.getLogger(__name__)

    base = Path(data_dir) if data_dir else EQUIPMENT_DATA_DIR
    counts = {"inserted": 0, "updated": 0, "skipped": 0, "files": 0, "deleted": 0}
    if not base.exists():
        log.warning("Equipment data dir not found: %s", base)
        return counts

    for fname, eq_type in _EQ_FILE_TYPE_MAP.items():
        fp = base / fname
        if not fp.exists():
            continue
        counts["files"] += 1
        try:
            raw_list = _json.loads(fp.read_text(encoding="utf-8"))
        except Exception as exc:
            log.warning("Failed to parse %s: %s", fp, exc)
            continue
        if not isinstance(raw_list, list):
            log.warning("%s root must be a JSON array", fp)
            continue

        model_cls = equipment_model_for_type(eq_type)
        if model_cls is None:
            log.warning("No typed table registered for equipment_type=%s", eq_type)
            continue

        # Wipe typed table for this type, plus matching public rows in legacy table.
        del_typed = await db.execute(sa_delete(model_cls))
        del_legacy = await db.execute(
            sa_delete(EquipmentModel).where(
                EquipmentModel.equipment_type == eq_type,
                EquipmentModel.is_public == True,  # noqa: E712
            )
        )
        counts["deleted"] += int(del_typed.rowcount or 0) + int(del_legacy.rowcount or 0)

        for raw in raw_list:
            entry = _normalize_equipment_entry(eq_type, raw)
            if not entry:
                counts["skipped"] += 1
                continue
            eq = model_cls(
                name=entry["name"],
                equipment_type=entry["equipment_type"],
                brand=entry["brand"],
                model_no=entry["model_no"],
                capacity=entry["capacity"],
                cop=entry["cop"],
                parameters=entry["parameters"],
                is_public=True,
                owner_id=None,
            )
            db.add(eq)
            counts["inserted"] += 1
    await db.commit()
    return counts
