"""EnergyPlus IDF 文件生成器。

用途：
  根据前端传入的 BuildingZone 数据，自动生成完整的 EnergyPlus IDF 输入文件，
  适用于区域级理想负荷（Ideal Loads）仿真。

设计思路：
  - 每个热区（zone）被建模为一个 "shoebox"（鞋盒）几何体，即一个简单的
    长方体空间，边长 = sqrt(面积)，高度 = floor_height。
  - 围护结构（墙、屋顶、地板）的传热系数（U值）由用户指定，程序自动计算
    材料热阻以匹配目标U值。采用"保温层+混凝土质量层"双层构造，提供热惯性。
  - 内部得热（人员、照明、设备）和温度设定支持两种模式：
    * fixed：恒定值，生成 Schedule:Constant
    * scheduled：按工作日/周末/自定义时段变化，生成 Schedule:Year 层级结构
  - 新风量（fresh_air_volume）在 scheduled 模式下会生成比例系数 schedule，
    并通过 DesignSpecification:OutdoorAir 的 schedule 字段控制风量。
  - 采用 ZoneHVAC:IdealLoadsAirSystem 作为空调系统，可计算理论冷/热负荷。

输出：
  完整的 IDF 文本字符串，可直接写入 .idf 文件并交给 EnergyPlus 执行。
"""

from __future__ import annotations

import math
from typing import Any

from app.simulation.energyplus.weather_utils import find_epw_for_location

# 冷热设定温度之间的死区宽度 [°C]
# 例：冷却设定26°C → 加热设定 = 26 - 6 = 20°C
SETPOINT_DEADBAND = 6.0

# 表面膜热阻 [m²·K/W]（GB 50176 标准参考值）
FILM_R_INT = 0.12   # 内表面膜热阻（对流+辐射）
FILM_R_EXT = 0.04   # 外表面膜热阻


# ---------------------------------------------------------------------------
# 参数校验
# ---------------------------------------------------------------------------

# 各字段的取值范围约束: (min, max)
_ZONE_FIELD_RANGES: dict[str, tuple[float, float]] = {
    "area":              (0.1,   1_000_000),   # m²
    "floor_height":      (1.0,   50.0),        # m
    "wall_u_value":      (0.01,  20.0),        # W/m²·K
    "window_u_value":    (0.1,   20.0),        # W/m²·K
    "window_wall_ratio": (0.0,   1.0),
    "roof_u_value":      (0.01,  20.0),        # W/m²·K
}


class ZoneValidationError(ValueError):
    """热区参数校验失败。"""


def _validate_param_config(
    zone_id: str, key: str, value: Any
) -> None:
    """校验 ParamConfig 类型字段（people_density, lighting_density 等）。"""
    if value is None:
        raise ZoneValidationError(
            f"zone '{zone_id}': 缺少必填字段 '{key}'"
        )
    if isinstance(value, (int, float)):
        return
    if not isinstance(value, dict):
        raise ZoneValidationError(
            f"zone '{zone_id}': 字段 '{key}' 类型错误，"
            f"期望 int/float/dict(ParamConfig)，实际为 {type(value).__name__}"
        )
    mode = value.get("mode")
    if mode not in ("fixed", "scheduled"):
        raise ZoneValidationError(
            f"zone '{zone_id}': 字段 '{key}' 的 mode 值无效，"
            f"期望 'fixed' 或 'scheduled'，实际为 {mode!r}"
        )
    if "fixed_value" not in value:
        raise ZoneValidationError(
            f"zone '{zone_id}': 字段 '{key}' 缺少 'fixed_value'"
        )
    if not isinstance(value["fixed_value"], (int, float)):
        raise ZoneValidationError(
            f"zone '{zone_id}': 字段 '{key}' 的 fixed_value 类型错误，"
            f"期望数值，实际为 {type(value['fixed_value']).__name__}"
        )
    if mode == "scheduled":
        schedules = value.get("schedules")
        if not isinstance(schedules, list):
            raise ZoneValidationError(
                f"zone '{zone_id}': 字段 '{key}' 的 schedules 类型错误，"
                f"期望 list，实际为 {type(schedules).__name__}"
            )


def _validate_zone(zone_id: str, zone: dict[str, Any]) -> None:
    """校验单个热区的所有必填字段。"""
    if not isinstance(zone, dict):
        raise ZoneValidationError(
            f"zone '{zone_id}': zone 数据类型错误，期望 dict，实际为 {type(zone).__name__}"
        )

    # 校验数值型必填字段
    for key, (lo, hi) in _ZONE_FIELD_RANGES.items():
        if key not in zone:
            raise ZoneValidationError(
                f"zone '{zone_id}': 缺少必填字段 '{key}'"
            )
        val = zone[key]
        if not isinstance(val, (int, float)):
            raise ZoneValidationError(
                f"zone '{zone_id}': 字段 '{key}' 类型错误，"
                f"期望 int/float，实际为 {type(val).__name__}"
            )
        if not (lo <= val <= hi):
            raise ZoneValidationError(
                f"zone '{zone_id}': 字段 '{key}' 值超限，"
                f"允许范围 [{lo}, {hi}]，实际值为 {val}"
            )

    # 校验 ParamConfig 型必填字段
    for key in ("people_density", "lighting_density", "equipment_density",
                "fresh_air_volume", "temperature"):
        _validate_param_config(zone_id, key, zone.get(key))

# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------


def _sn(name: str) -> str:
    """清理名称使其符合IDF字段要求。

    IDF字段名不允许包含逗号、分号、感叹号等特殊字符，
    空格替换为下划线，并截断至40个字符。
    """
    return name.replace(" ", "_").replace(",", "").replace(";", "").replace("!", "")[:40]


def _vstr(x: float, y: float, z: float) -> str:
    """将三维坐标点格式化为IDF顶点字符串。"""
    return f"  {x:.4f}, {y:.4f}, {z:.4f}"


# ---------------------------------------------------------------------------
# 公共入口函数
# ---------------------------------------------------------------------------


def generate_idf(
    zones: dict[str, dict[str, Any]],
    location: list[str],
) -> str:
    """根据热区字典和地理位置信息生成完整的 EnergyPlus IDF 字符串。

    参数:
        zones: 热区数据字典，键为 zone_id，值为包含以下字段的字典：
            - name: 热区名称（如 "Office"）
            - area: 建筑面积 [m²]
            - floor_height: 层高 [m]
            - wall_u_value: 外墙传热系数 [W/m²·K]
            - window_u_value: 外窗传热系数 [W/m²·K]
            - window_wall_ratio: 窗墙比 [0~1]
            - roof_u_value: 屋顶传热系数 [W/m²·K]
            - people_density: 人员密度 [人/m²]（ParamConfig 格式）
            - lighting_density: 照明功率密度 [W/m²]（ParamConfig 格式）
            - equipment_density: 设备功率密度 [W/m²]（ParamConfig 格式）
            - fresh_air_volume: 新风量 [m³/h·人]（ParamConfig 格式）
            - temperature: 温度设定 [°C]（ParamConfig 格式）
        location: 地理位置，格式 [省份, 城市]，如 ["广东", "广州"]。
            用于查找对应的 EPW 气象文件并提取位置和地温数据。

    返回:
        完整的 IDF 文本字符串

    ParamConfig 格式说明:
        可以是:
        - 标量值（int/float）：直接作为常数
        - 字典，包含 mode/fixed_value/schedules 字段：
          * mode="fixed": 使用 fixed_value 作为常数
          * mode="scheduled": 根据 schedules 列表生成时间变化的 schedule
            schedules 列表中每个元素包含:
              start_month, start_day, end_month, end_day（日期范围）
              days（星期几列表，1=周一...7=周日）
              hours（小时列表，0-23）
              value（该时段的值）
    """
    # ---- 第一部分：全局设置（版本、仿真控制、建筑、时间步长等）----
    if not isinstance(zones, dict) or not zones:
        raise ZoneValidationError("zones 不能为空且必须为 dict 类型")
    if not isinstance(location, list) or len(location) < 2:
        raise ZoneValidationError("location 必须为 [省份, 城市] 格式的列表")

    # 先校验所有热区参数，全部通过后再生成
    for zone_id, zone in zones.items():
        _validate_zone(zone_id, zone)

    parts: list[str] = [
        _global_version(),
        _global_sim_control(),
        _global_building(),
        _global_timestep(),
        _global_run_period(),
        _global_location(location),
        _global_geometry_rules(),
        _global_schedule_types(),
        _constant_schedules(),
    ]

    # ---- 第二部分：逐个热区生成对象 ----
    # 每个热区沿 X 轴依次排列，间距5m，互不遮挡
    x_offset = 0.0
    zone_names: list[str] = []
    # 重名检测计数器：同名 zone 自动追加序号（如 Office, Office_2, Office_3）
    # 避免 EnergyPlus 因重复对象名报 Severe Error
    name_counts: dict[str, int] = {}
    for zone_id, zone in zones.items():
        raw = _sn(zone.get("name", zone_id))
        name_counts[raw] = name_counts.get(raw, 0) + 1
        zn = raw if name_counts[raw] == 1 else f"{raw}_{name_counts[raw]}"
        zone_names.append(zn)
        area = zone["area"]
        fh = zone["floor_height"]
        side = math.sqrt(area)               # shoebox 正方形边长 [m]

        # 区域定义对象
        parts.append(_zone_object(zn, x_offset))
        # 围护结构材料和构造
        parts.append(_materials_constructions(zn, zone))
        # 几何体（地板、屋顶、4面墙 + 窗户）
        zone_pos = zone.get("zone_position", "single")
        wall_cfg = zone.get("wall_config", {})
        parts.append(_zone_geometry(zn, side, side, fh, zone["window_wall_ratio"], x_offset,
                                    zone_pos, wall_cfg))

        # ---- Schedule 生成（内部得热 + 温度设定）----
        # 注意：新风量(fresh_air_volume)单独处理，不在此循环中
        sched_map: dict[str, str] = {}  # 记录各参数对应的 schedule 名称
        for key in ("people_density", "lighting_density", "equipment_density",
                     "temperature"):
            sn = f"{zn}_{key}"  # schedule 命名：区域名_参数名
            val = zone[key]
            # 温度类 schedule 的非工作时段保持设定温度（而非 0）
            # 内部得热类 schedule 的非工作时段为 0（无人无灯无设备）
            off = None  # 默认 off_value=0
            if key == "temperature" and isinstance(val, dict):
                off = val["fixed_value"]
            parts.append(_param_config_schedule(sn, val, off_value=off))
            sched_map[key] = sn

        # ---- 供暖温度设定 = 供冷温度 - 死区 ----
        # 例：供冷 26°C → 供暖 20°C（死区 6°C）
        ht_sn = f"{zn}_heating_sp"
        temp_val = zone["temperature"]
        ht_off = None
        if isinstance(temp_val, dict):
            ht_off = temp_val["fixed_value"] - SETPOINT_DEADBAND
        parts.append(_offset_schedule(ht_sn, temp_val, -SETPOINT_DEADBAND, off_value=ht_off))
        sched_map["heating_sp"] = ht_sn

        # ---- 内部得热对象 ----
        parts.append(_people(zn, area, sched_map["people_density"]))       # 人员
        parts.append(_lights(zn, area, sched_map["lighting_density"]))     # 照明
        parts.append(_equipment(zn, area, sched_map["equipment_density"])) # 设备

        # ---- 室外新风 ----
        # 当新风量为 scheduled 模式时：
        #   1. 取所有 schedule 中的最大值作为设计新风量
        #   2. 生成 0~1 的比例 schedule（实际值/最大值）
        #   3. 通过 DSOA 的 schedule 字段控制新风量随时间变化
        fa_param = zone["fresh_air_volume"]
        if (isinstance(fa_param, dict)
                and fa_param.get("mode") == "scheduled"
                and fa_param.get("schedules")):
            # 找到所有时段中的最大新风量作为设计值
            all_vals = [s.get("value", 0) for s in fa_param["schedules"]]
            max_val = max(max(all_vals), fa_param["fixed_value"])
            oa_per_person = max_val / 3600.0  # m³/h → m³/s
            # 生成比例系数 schedule（非工作时段为 0，即无新风）
            oa_sched_name = f"{zn}_OA_Frac"
            oa_param = {
                "mode": "scheduled",
                "fixed_value": 0.0,  # 非工作时段默认无新风
                "schedules": [
                    {**s, "value": s.get("value", 0) / max_val}
                    for s in fa_param["schedules"]
                ],
            }
            parts.append(_param_config_schedule(oa_sched_name, oa_param))
        else:
            # 固定模式：使用 fixed_value 作为恒定新风量
            oa_per_person = _fixed_val(fa_param) / 3600.0
            oa_sched_name = "Always_On"  # 始终保持设计新风量
        parts.append(_outdoor_air_spec(zn, oa_per_person, oa_sched_name))

        # ---- HVAC 系统（温控器 + 理想负荷机组 + 设备连接）----
        parts.append(_thermostat(zn, sched_map["temperature"], sched_map["heating_sp"]))
        parts.append(_ideal_loads(zn))
        parts.append(_zone_equipment(zn))

        # 下一个热区沿 X 轴偏移（当前区域宽度 + 5m 间距）
        x_offset += side + 5.0

    # ---- 第三部分：输出变量定义 ----
    parts.append(_output_variables(zone_names))
    return "\n\n".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# 固定值提取器
# ---------------------------------------------------------------------------

def _fixed_val(param: dict[str, Any] | float | int) -> float:
    """从 ParamConfig 中提取固定值。

    - param 为数字 → 直接返回
    - param 为字典 → 返回 param["fixed_value"]
    """
    if isinstance(param, (int, float)):
        return float(param)
    return param["fixed_value"]


# ---------------------------------------------------------------------------
# 全局 IDF 对象生成函数
# 以下函数生成整个 IDF 文件中只出现一次的全局设置对象
# ---------------------------------------------------------------------------

def _global_version() -> str:
    """生成 Version 对象，必须与安装的 EnergyPlus 版本一致。"""
    return "Version, 25.2;"


def _global_sim_control() -> str:
    """生成 SimulationControl 对象。

    关闭所有 Sizing 计算（理想负荷不需要），仅运行气象文件全年仿真。
    """
    return (
        "SimulationControl,\n"
        "  No,   !- Do Zone Sizing Calculation\n"
        "  No,   !- Do System Sizing Calculation\n"
        "  No,   !- Do Plant Sizing Calculation\n"
        "  No,   !- Run Simulation for Sizing Periods\n"
        "  Yes;  !- Run Simulation for Weather File Run Periods"
    )


def _global_building() -> str:
    """生成 Building 对象。

    地形设为 City（城市），太阳分布采用 FullInteriorAndExterior（完整内外计算）。
    """
    return (
        "Building,\n"
        "  HVAC_Simulation_Building,  !- Name\n"
        "  0.0,  !- North Axis (deg)\n"
        "  City, !- Terrain\n"
        "  0.04, !- Loads Convergence Tolerance\n"
        "  0.4,  !- Temperature Convergence Tolerance\n"
        "  FullInteriorAndExterior, !- Solar Distribution\n"
        "  25,   !- Maximum Number of Warmup Days\n"
        "  6;    !- Minimum Number of Warmup Days"
    )


def _global_timestep() -> str:
    """生成 Timestep 对象。

    每小时 4 步（15分钟间隔），EP 建议最小值为 4，
    可避免无热质量材料导致的数值不稳定。
    """
    return "Timestep, 4;"


def _global_run_period() -> str:
    """生成 RunPeriod 对象：全年仿真 (1/1 – 12/31)。

    Day of Week for Start Day 设为 Sunday，
    启用气象文件中的假日、夏令时、雨雪指示。
    """
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


def _global_location(location: list[str]) -> str:
    """生成 Site:Location 和 Site:GroundTemperature:BuildingSurface 对象。

    根据 location [省份, 城市] 查找对应的 EPW 气象文件，
    从中提取经纬度、时区、海拔以及 12 个月的 0.5m 深度地表温度。
    """
    _, loc_data = find_epw_for_location(location)
    if not loc_data:
        raise ValueError(
            f"找不到 location={location} 对应的 EPW 气象文件，"
            "请确认 data/weather/ 目录下包含该地区的天气数据。"
        )
    name = loc_data["name"]
    lat = loc_data["lat"]
    lon = loc_data["lon"]
    tz = loc_data["tz"]
    elev = loc_data["elev"]
    temps = loc_data.get("ground_temps", [15.0] * 12)
    temp_str = ", ".join(str(t) for t in temps)
    return (
        f"Site:Location,\n"
        f"  {name},  !- Name\n"
        f"  {lat},   !- Latitude\n"
        f"  {lon},   !- Longitude\n"
        f"  {tz},    !- Time Zone\n"
        f"  {elev};  !- Elevation\n\n"
        f"Site:GroundTemperature:BuildingSurface, {temp_str};"
    )


def _global_geometry_rules() -> str:
    """生成 GlobalGeometryRules：左上角起始、逆时针方向、世界坐标系。"""
    return "GlobalGeometryRules, UpperLeftCorner, Counterclockwise, World;"


def _global_schedule_types() -> str:
    """生成 ScheduleTypeLimits 定义。

    定义三种 schedule 类型：
    - Any Number：任意数值（用于功率密度、人员密度等）
    - Fractional：0~1 范围（用于开关、比例系数）
    - Temperature：-100~100°C（用于温度设定）
    """
    return (
        "ScheduleTypeLimits, Any Number;\n\n"
        "ScheduleTypeLimits, Fractional, 0, 1, Continuous;\n\n"
        "ScheduleTypeLimits, Temperature, -100, 100, Continuous;"
    )


def _constant_schedules() -> str:
    """生成全局常数 schedule。

    - Always_On: 始终为 1（用于启用开关等）
    - Always_4: 始终为 4，代表 DualSetpoint 温控模式
      （ThermostatSetpoint:DualSetpoint 对应 Control Type ID = 4）
    - Activity_Level_120: 办公活动代谢率 120 W/人（标准办公活动）
    """
    return (
        "Schedule:Constant, Always_On, Fractional, 1.0;\n\n"
        "Schedule:Constant, Always_4, Any Number, 4;\n\n"
        "Schedule:Constant, Activity_Level_120, Any Number, 120;"
    )


# ---------------------------------------------------------------------------
# 区域对象
# ---------------------------------------------------------------------------

def _zone_object(zn: str, x0: float) -> str:
    """生成 Zone 对象。

    每个热区是一个独立的空气节点，起始点在 (x0, 0, 0)。
    Multiplier 设为 1（单层），天花板高度和体积自动计算。
    """
    return (
        f"Zone,\n"
        f"  {zn},\n"
        f"  0.0,\n"
        f"  {x0:.4f}, 0.0, 0.0,\n"
        f"  1, 1,\n"
        f"  autocalculate, autocalculate;"
    )


# ---------------------------------------------------------------------------
# 围护结构材料和构造
# ---------------------------------------------------------------------------

def _materials_constructions(zn: str, zone: dict[str, Any]) -> str:
    """根据用户设定的U值生成围护结构材料和构造对象。

    采用双层构造：保温层(NoMass) + 150mm混凝土质量层(Material)。
    这样既能精确匹配目标U值，又提供足够的热惯性避免仿真不稳定。
    """
    wall_u = zone["wall_u_value"]
    roof_u = zone["roof_u_value"]
    win_u = zone["window_u_value"]

    # 质量层参数: 150mm 混凝土 (k=1.0 W/m·K, ρ=2000 kg/m³, cp=900 J/kg·K)
    MASS_THICK = 0.15   # 厚度 [m]
    MASS_K = 1.0        # 导热系数 [W/m·K]
    MASS_RHO = 2000     # 密度 [kg/m³]
    MASS_CP = 900       # 比热容 [J/kg·K]
    R_MASS = MASS_THICK / MASS_K  # 质量层热阻 = 0.15 m²·K/W

    # 扣除表面膜热阻和质量层热阻后，剩余部分由保温层(NoMass)承担
    wall_r_ins = max(0.01, 1.0 / wall_u - FILM_R_INT - FILM_R_EXT - R_MASS)
    roof_r_ins = max(0.01, 1.0 / roof_u - 0.10 - FILM_R_EXT - R_MASS)
    floor_r_ins = max(0.01, 1.0 / 1.0 - 0.17 - FILM_R_EXT - R_MASS)  # 地板按 U=1.0 估算

    lines = [
        # 质量层（提供热惯性，消除EP "no thermal mass" 警告）
        f"Material, {zn}_WallMass, MediumRough, {MASS_THICK}, {MASS_K}, {MASS_RHO}, {MASS_CP}, 0.9, 0.7, 0.7;",
        f"Material, {zn}_RoofMass, MediumRough, {MASS_THICK}, {MASS_K}, {MASS_RHO}, {MASS_CP}, 0.9, 0.7, 0.7;",
        f"Material, {zn}_FloorMass, MediumRough, {MASS_THICK}, {MASS_K}, {MASS_RHO}, {MASS_CP}, 0.9, 0.7, 0.7;",
        # 保温层（调整R值以达到目标U值）
        f"Material:NoMass, {zn}_WallIns, MediumRough, {wall_r_ins:.4f}, 0.9, 0.7, 0.7;",
        f"Material:NoMass, {zn}_RoofIns, MediumRough, {roof_r_ins:.4f}, 0.9, 0.7, 0.7;",
        f"Material:NoMass, {zn}_FloorIns, MediumRough, {floor_r_ins:.4f}, 0.9, 0.7, 0.7;",
        # 玻璃（简化模型）
        f"WindowMaterial:SimpleGlazingSystem, {zn}_WinMat, {win_u}, 0.40;",
        # 构造定义：外层保温 + 内层混凝土
        f"Construction, {zn}_WallC, {zn}_WallIns, {zn}_WallMass;",
        f"Construction, {zn}_IntWallC, {zn}_WallMass;",  # 内墙：仅混凝土层（无保温）
        f"Construction, {zn}_RoofC, {zn}_RoofIns, {zn}_RoofMass;",
        f"Construction, {zn}_IntRoofC, {zn}_RoofMass;",  # 层间楼板
        f"Construction, {zn}_FloorC, {zn}_FloorMass, {zn}_FloorIns;",
        f"Construction, {zn}_IntFloorC, {zn}_FloorMass;",  # 层间楼板
        f"Construction, {zn}_WinC, {zn}_WinMat;",
    ]
    return "\n\n".join(lines)


# ---------------------------------------------------------------------------
# 几何体生成（Shoebox 模型）
# 每个热区被建模为一个简单的长方体（鞋盒模型），
# 包含：1个地板 + 1个屋顶 + 4面墙 + 方向窗户
# 根据 zone_position 和 wall_config 设置边界条件
# ---------------------------------------------------------------------------

def _zone_geometry(zn: str, w: float, d: float, h: float,
                   wwr: float, x0: float,
                   zone_position: str = "single",
                   wall_config: dict[str, Any] | None = None) -> str:
    """生成区域的所有几何表面（地板、屋顶、4面墙和窗户）。

    参数:
        zn: 区域名称
        w: 宽度 [m]
        d: 深度 [m]（正方形时 d=w）
        h: 高度 [m]
        wwr: 窗墙比 [0~1]
        x0: X轴偏移量 [m]
        zone_position: "single"|"top"|"middle"|"bottom"
            - single: 独立层 → 地板Ground, 屋顶Outdoors
            - top: 顶层 → 地板Adiabatic(层间楼板), 屋顶Outdoors
            - bottom: 底层 → 地板Ground, 屋顶Adiabatic(层间楼板)
            - middle: 中间层 → 地板Adiabatic, 屋顶Adiabatic
        wall_config: 各方向墙体是否为外墙
            {south_exterior, north_exterior, east_exterior, west_exterior}
    """
    if wall_config is None:
        wall_config = {}
    parts: list[str] = []

    # Floor boundary condition based on zone_position
    if zone_position in ("top", "middle"):
        floor_bc, floor_exposed = "Adiabatic", False
        floor_constr = f"{zn}_IntFloorC"
    else:  # single, bottom
        floor_bc, floor_exposed = "Ground", False
        floor_constr = f"{zn}_FloorC"

    parts.append(_surface(
        f"{zn}_Floor", "Floor", floor_constr, zn,
        floor_bc, floor_exposed,
        [(x0 + w, d, 0), (x0 + w, 0, 0), (x0, 0, 0), (x0, d, 0)],
    ))

    # Roof boundary condition based on zone_position
    if zone_position in ("bottom", "middle"):
        roof_bc, roof_exposed = "Adiabatic", False
        roof_constr = f"{zn}_IntRoofC"
    else:  # single, top
        roof_bc, roof_exposed = "Outdoors", True
        roof_constr = f"{zn}_RoofC"

    parts.append(_surface(
        f"{zn}_Roof", "Roof", roof_constr, zn,
        roof_bc, roof_exposed,
        [(x0, d, h), (x0, 0, h), (x0 + w, 0, h), (x0 + w, d, h)],
    ))

    # Walls  (name, width_for_windows, 4 vertices, exterior_key)
    wall_defs = [
        ("South", w,
         [(x0, 0, h), (x0, 0, 0), (x0 + w, 0, 0), (x0 + w, 0, h)],
         "south_exterior"),
        ("North", w,
         [(x0 + w, d, h), (x0 + w, d, 0), (x0, d, 0), (x0, d, h)],
         "north_exterior"),
        ("East", d,
         [(x0 + w, 0, h), (x0 + w, 0, 0), (x0 + w, d, 0), (x0 + w, d, h)],
         "east_exterior"),
        ("West", d,
         [(x0, d, h), (x0, d, 0), (x0, 0, 0), (x0, 0, h)],
         "west_exterior"),
    ]

    for orient, ww, verts, ext_key in wall_defs:
        wn = f"{zn}_Wall_{orient}"
        is_exterior = wall_config.get(ext_key, True)
        if is_exterior:
            bc, exposed = "Outdoors", True
            constr = f"{zn}_WallC"
        else:
            bc, exposed = "Adiabatic", False
            constr = f"{zn}_IntWallC"
        parts.append(_surface(wn, "Wall", constr, zn, bc, exposed, verts))
        # Only add windows to exterior walls
        if is_exterior and wwr > 0.01:
            wv = _window_verts(orient, ww, h, wwr, w, d, x0)
            if wv:
                parts.append(_fenestration(f"{zn}_Win_{orient}", f"{zn}_WinC", wn, wv))

    return "\n\n".join(parts)


def _surface(name: str, stype: str, constr: str, zone: str,
             bc: str, exposed: bool,
             verts: list[tuple[float, float, float]]) -> str:
    """生成 BuildingSurface:Detailed 对象（不透明表面）。

    参数:
        name: 表面名称
        stype: 类型（Floor/Wall/Roof）
        constr: 构造名称
        zone: 所属区域
        bc: 边界条件（Outdoors/Ground）
        exposed: 是否暴露于太阳和风
        verts: 顶点坐标列表（逆时针顺序）
    """
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
    """生成 FenestrationSurface:Detailed 对象（窗户）。

    窗户必须依附在某个墙面（base）上，顶点必须在墙面内。
    """
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
    """根据窗墙比(wwr)计算窗户的 4 个顶点坐标。

    窗户在墙面中心居中放置，窗高取墙高的70%，
    窗宽根据窗墙比反算（最大不超过墙宽的95%）。

    参数:
        orient: 方向 ("South"/"North"/"East"/"West")
        wall_w: 墙面宽度 [m]
        wall_h: 墙面高度 [m]
        wwr: 窗墙比
        W, D: 区域的宽度和深度 [m]
        x0: X轴偏移

    返回:
        4个顶点坐标列表，或 None（窗户太小时）
    """
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
# Schedule 生成（从 ParamConfig 转换为 EnergyPlus Schedule 对象）
#
# 生成层级结构：
#   Schedule:Day:Hourly   → 定义每天 24 小时的值
#   Schedule:Week:Daily   → 将一周 7 天映射到 Day 对象
#   Schedule:Year         → 将日期范围映射到 Week 对象
# ---------------------------------------------------------------------------

def _param_config_schedule(name: str, param: dict[str, Any] | float | int | None,
                           *, off_value: float | None = None) -> str:
    """将 ParamConfig 转换为 EnergyPlus schedule 对象。

    支持两种模式：
    - fixed 或 标量值：生成 Schedule:Constant
    - scheduled：生成 Schedule:Year 层级结构

    内部逻辑：
    1. 按日期范围分组（相同 start/end 的合并）
    2. 每组生成 7×24 矩阵（周一~周日 × 0~23时）
    3. 非工作时段初始化为 off_value（默认 0）
    4. 按 schedule 条目填充矩阵中指定的小时和星期
    5. 合并相同的 Day 对象以减少冗余

    参数:
        name: Schedule 名称
        param: ParamConfig 数据（可为 None/数字/字典）
        off_value: 非工作时段的默认值。
            - 内部得热（人员、照明、设备）：默认 0（无人无灯）
            - 温度设定：传入 fixed_value（维持设定温度）
    """
    # 空值：返回常数 0
    if param is None:
        return f"Schedule:Constant, {name}, Any Number, 0;"
    # 标量值：直接返回常数
    if isinstance(param, (int, float)):
        return f"Schedule:Constant, {name}, Any Number, {param};"

    fv = param["fixed_value"]  # 固定值（mode=fixed 时使用）
    # 固定模式或无 schedule 条目：返回常数
    if param.get("mode", "fixed") == "fixed" or not param.get("schedules"):
        return f"Schedule:Constant, {name}, Any Number, {fv};"

    # ---- scheduled 模式：生成多层 schedule ----
    default = off_value if off_value is not None else 0.0  # 非工作时段默认值
    schedules = param["schedules"]
    # 按日期范围分组：相同 start/end 的合并到一个 period
    periods: dict[tuple[int, int, int, int], list[dict]] = {}
    for s in schedules:
        key = (s["start_month"], s["start_day"], s["end_month"], s["end_day"])
        periods.setdefault(key, []).append(s)

    parts: list[str] = []
    year_entries: list[str] = []

    for pi, ((sm, sd, em, ed), entries) in enumerate(sorted(periods.items())):
        # 创建 7×24 矩阵：索引 0=周一 .. 6=周日，初始化为 off_value
        matrix = [[default] * 24 for _ in range(7)]
        # 根据 schedule 条目填充矩阵
        for entry in entries:
            for dow in entry.get("days", list(range(1, 8))):  # days: 1=周一..7=周日
                for hr in entry.get("hours", list(range(24))): # hours: 0-23
                    if 0 <= dow - 1 < 7 and 0 <= hr < 24:
                        matrix[dow - 1][hr] = entry.get("value", fv)

        # 合并相同的日型以减少对象数量
        unique: dict[tuple[float, ...], str] = {}
        dow_names: list[str] = [""] * 7
        for dow in range(7):
            key = tuple(matrix[dow])
            if key not in unique:
                dn = f"{name}_P{pi}_D{len(unique)}"  # 命名：参数名_P日期组_D日型
                unique[key] = dn
                vals = ", ".join(str(v) for v in key)  # 24 个小时值
                parts.append(f"Schedule:Day:Hourly, {dn}, Any Number, {vals};")
            dow_names[dow] = unique[key]

        # 周 schedule：定义每周 7 天 + 5 个特殊日类型的引用
        # EP 顺序：周日 周一 周二 周三 周四 周五 周六 假日 SDD WDD CD1 CD2
        wk = f"{name}_W{pi}"
        week = [
            dow_names[6],  # Sunday  (周日)
            dow_names[0],  # Monday  (周一)
            dow_names[1],  # Tuesday
            dow_names[2],  # Wednesday
            dow_names[3],  # Thursday
            dow_names[4],  # Friday
            dow_names[5],  # Saturday (周六)
        ]
        week += [dow_names[6]] * 5  # 假日和特殊日按周日处理
        parts.append(f"Schedule:Week:Daily, {wk}, " + ", ".join(week) + ";")
        year_entries.append(f"  {wk}, {sm}, {sd}, {em}, {ed}")

    # 年 schedule：将所有日期范围与周 schedule 关联
    parts.append(f"Schedule:Year, {name}, Any Number,\n" + ",\n".join(year_entries) + ";")
    return "\n\n".join(parts)


def _offset_schedule(name: str, param: dict[str, Any] | float | int | None,
                     offset: float, *, off_value: float | None = None) -> str:
    """创建一个与 param 相同但所有值偏移 offset 的 schedule。

    主要用于从供冷温度设定生成供暖温度设定：
    例：供冷 26°C + offset(-6) = 供暖 20°C
    """
    if param is None:
        return f"Schedule:Constant, {name}, Temperature, {0 + offset};"
    if isinstance(param, (int, float)):
        return f"Schedule:Constant, {name}, Temperature, {float(param) + offset};"

    fv = param["fixed_value"] + offset
    if param.get("mode", "fixed") == "fixed" or not param.get("schedules"):
        return f"Schedule:Constant, {name}, Temperature, {fv};"

    shifted = dict(param)
    shifted["fixed_value"] = fv
    shifted["schedules"] = [
        {**s, "value": s.get("value", param["fixed_value"]) + offset}
        for s in param.get("schedules", [])
    ]
    return _param_config_schedule(name, shifted, off_value=off_value)


# ---------------------------------------------------------------------------
# 内部得热对象（People / Lights / ElectricEquipment）
#
# 三种内部得热均采用 "密度法"（xxx/Area = 1.0 W/m²），
# 实际瓦数完全由 schedule 中的值控制。
# 例如：照明 schedule 值=10 → 实际照明功率=10×1.0=10 W/m²
# ---------------------------------------------------------------------------

def _people(zn: str, area: float, sched: str) -> str:
    """生成 People 对象。

    - 方法: People/Area，设计密度 1.0 人/m²
    - 实际人员密度由 schedule 值决定（如 schedule=0.1 → 0.1人/m²）
    - 辐射分数: 0.3（30%辐射，70%对流）
    - 活动水平: 120 W/人（办公活动等级）
    """
    return (
        f"People,\n"
        f"  {zn}_People, {zn}, {sched},\n"
        f"  People/Area, , 1.0, ,\n"
        f"  0.3, autocalculate, Activity_Level_120;"
    )


def _lights(zn: str, area: float, sched: str) -> str:
    """生成 Lights 对象。

    - 方法: Watts/Area，设计密度 1.0 W/m²
    - 实际照明功率由 schedule 值决定（如 schedule=12 → 12 W/m²）
    - Return Air 分数: 0.0（无回风带热）
    - 辐射分数: 0.7（70%长波辐射）
    - 可见光分数: 0.2（20%可见光）
    - 替换系数: 1.0
    """
    return (
        f"Lights,\n"
        f"  {zn}_Lights, {zn}, {sched},\n"
        f"  Watts/Area, , 1.0, ,\n"
        f"  0.0, 0.7, 0.2, 1.0;"
    )


def _equipment(zn: str, area: float, sched: str) -> str:
    """生成 ElectricEquipment 对象。

    - 方法: Watts/Area，设计密度 1.0 W/m²
    - 实际设备功率由 schedule 值决定（如 schedule=20 → 20 W/m²）
    - 辐射分数: 0.3（30%辐射）
    - 潜热分数: 0.0（纯显热负荷）
    """
    return (
        f"ElectricEquipment,\n"
        f"  {zn}_Equip, {zn}, {sched},\n"
        f"  Watts/Area, , 1.0, ,\n"
        f"  0.0, 0.3, 0.0;"
    )


# ---------------------------------------------------------------------------
# 室外新风规格
# ---------------------------------------------------------------------------

def _outdoor_air_spec(zn: str, oa_per_person: float, sched: str) -> str:
    """生成 DesignSpecification:OutdoorAir 对象。

    - 方法: Flow/Person（按人均新风量）
    - oa_per_person: 人均新风量 [m³/s·人]（由 fresh_air_volume 换算而来）
    - sched: 新风比例 schedule（1.0=全量，0.0=关闭，0.5=50%）
    """
    return (
        f"DesignSpecification:OutdoorAir,\n"
        f"  {zn}_DSOA,\n"
        f"  Flow/Person,\n"
        f"  {oa_per_person:.6f}, , , ,\n"
        f"  {sched};"
    )


# ---------------------------------------------------------------------------
# 温控器 + 理想负荷空调系统
# ---------------------------------------------------------------------------

def _thermostat(zn: str, cool_sched: str, heat_sched: str) -> str:
    """生成温控器对象：DualSetpoint + ZoneControl:Thermostat。

    - DualSetpoint: 定义供暖/供冷温度设定值 schedule
    - ZoneControl:Thermostat: 将温控器绑定到区域
    - Always_4: 控制类型=4（双设定点控制）
    """
    return (
        f"ThermostatSetpoint:DualSetpoint,\n"
        f"  {zn}_DualSP, {heat_sched}, {cool_sched};\n\n"
        f"ZoneControl:Thermostat,\n"
        f"  {zn}_Thermostat, {zn}, Always_4,\n"
        f"  ThermostatSetpoint:DualSetpoint, {zn}_DualSP;"
    )


def _ideal_loads(zn: str) -> str:
    """生成 ZoneHVAC:IdealLoadsAirSystem 对象（理想负荷空调系统）。

    这不是物理设备模型，而是 EnergyPlus 提供的理想系统，
    可以精确满足区域的冷/热负荷需求，用于纯负荷计算。

    关键参数说明：
    - 最高供暖送风温度: 50°C
    - 最低供冷送风温度: 13°C
    - 最大供暖含湿量: 0.0156 kg/kg
    - 最小供冷含湿量: 0.0077 kg/kg
    - 供冷/供暖能力: NoLimit（不限制，完全满足负荷）
    - 显热比: 0.7（固定值）
    - 新风规格: 引用同区域的 DSOA 对象
    - 热回收效率: 显热0.70 / 全热0.65
    - DCV: OccupancySchedule（按实际人员 schedule 计算新风量）
    """
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
        f"  OccupancySchedule,\n"            # DCV type: 按实际人数计算新风量
        f"  NoEconomizer,\n"
        f"  None,\n"                         # Heat Recovery
        f"  0.70, 0.65;"
    )


def _zone_equipment(zn: str) -> str:
    """生成区域设备连接对象：EquipmentList + EquipmentConnections + NodeList。

    将 IdealLoadsAirSystem 连接到区域的空气节点网络：
    - EquipmentList: 设备清单，定义设备优先级
    - EquipmentConnections: 将区域与设备清单和空气节点关联
    - NodeList: 定义区域送风入口节点列表

    空气节点拓扑：
    IdealLoads → SupplyInlet → 区域 → ReturnNode → (排出)
    """
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
# 输出变量设置
# ---------------------------------------------------------------------------

def _output_variables(zone_names: list[str]) -> str:
    """生成 EnergyPlus 输出变量定义。

    输出内容：
    - 逐时供冷能耗 [J]：Zone Ideal Loads Supply Air Total Cooling Energy
    - 逐时供暖能耗 [J]：Zone Ideal Loads Supply Air Total Heating Energy
    - 逐时区域平均温度 [°C]：Zone Mean Air Temperature
    - HTML 格式的汇总报告表
    - 所有摘要报告（AllSummary）
    """
    lines = [
        "Output:Variable, *, Zone Ideal Loads Supply Air Total Cooling Energy, Hourly;",
        "Output:Variable, *, Zone Ideal Loads Supply Air Total Heating Energy, Hourly;",
        "Output:Variable, *, Zone Mean Air Temperature, Hourly;",
        "OutputControl:Table:Style, HTML;",
        "Output:Table:SummaryReports, AllSummary;",
    ]
    return "\n\n".join(lines)
