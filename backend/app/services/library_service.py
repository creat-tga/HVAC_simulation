"""Library service: weather, equipment, building templates."""

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.library import WeatherFile, EquipmentModel, BuildingTemplate
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

async def list_equipment(
    db: AsyncSession,
    owner_id: uuid.UUID,
    equipment_type: str | None = None,
    scope: str = "all",  # 'all' | 'public' | 'mine'
) -> list[EquipmentModel]:
    stmt = select(EquipmentModel)
    if scope == "public":
        stmt = stmt.where(EquipmentModel.is_public == True)  # noqa: E712
    elif scope == "mine":
        stmt = stmt.where(EquipmentModel.owner_id == owner_id)
    else:
        stmt = stmt.where(or_(EquipmentModel.is_public == True, EquipmentModel.owner_id == owner_id))  # noqa: E712
    if equipment_type:
        stmt = stmt.where(EquipmentModel.equipment_type == equipment_type)
    stmt = stmt.order_by(EquipmentModel.created_at.desc())
    return (await db.execute(stmt)).scalars().all()


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
