"""idf_generator.py 单元测试。

覆盖：
- 参数校验（缺失字段、类型错误、范围越界）
- generate_idf 正常生成（单/多 zone、dict zones、location 参数）
- weather_utils（EPW 查找、解析、回退逻辑）
"""

from __future__ import annotations

import sys
import os
from pathlib import Path
import pytest

# 确保 backend 目录在 sys.path 中，便于直接 pytest 运行
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.simulation.energyplus.idf_generator import (
    generate_idf,
    ZoneValidationError,
    _validate_zone,
    _validate_param_config,
    _fixed_val,
)
from app.simulation.energyplus.weather_utils import (
    find_epw_for_location,
    parse_epw_header,
    _DEFAULT_WEATHER_DIR,
)

# ---------------------------------------------------------------------------
# 测试 fixture
# ---------------------------------------------------------------------------

def _make_zone(**overrides) -> dict:
    """生成一个包含所有必填字段的合法 zone 字典。"""
    base = {
        "area": 120.0,
        "floor_height": 3.5,
        "wall_u_value": 0.8,
        "window_u_value": 2.5,
        "window_wall_ratio": 0.35,
        "roof_u_value": 0.6,
        "people_density": 10.0,
        "lighting_density": 12.0,
        "equipment_density": 15.0,
        "fresh_air_volume": 30.0,
        "temperature": 26.0,
    }
    base.update(overrides)
    return base


# 默认使用广州作为测试 location
DEFAULT_LOCATION = ["广东", "广州"]


# ===================================================================
# weather_utils 测试
# ===================================================================

class TestWeatherUtils:
    """EPW 文件查找与解析。"""

    def test_parse_epw_header_basic(self):
        """能从真实 EPW 文件解析出必要字段。"""
        epw_path, header = find_epw_for_location(["广东", "广州"])
        assert epw_path is not None, "应能找到广州的 EPW 文件"
        assert "lat" in header and "lon" in header
        assert "ground_temps" in header
        assert len(header["ground_temps"]) == 12

    def test_find_exact_city(self):
        """精确城市名匹配。"""
        path, data = find_epw_for_location(["广东", "广州"])
        assert path is not None
        assert "guangzhou" in data["name"].lower()

    def test_find_city_fallback_to_capital(self):
        """城市无独立 EPW → 回退到省会或就近站点。"""
        # 珠海没有独立 EPW，应回退到广州
        path, data = find_epw_for_location(["广东", "珠海"])
        assert path is not None
        assert "guangzhou" in data["name"].lower()

    def test_find_province_any_epw(self):
        """省会也匹配不到时，返回该省任意 EPW。"""
        # 用一个在映射表中不存在的假城市测试
        path, data = find_epw_for_location(["黑龙江", "不存在的城市"])
        # 黑龙江省应该有 EPW 文件
        assert path is not None

    def test_find_not_found(self):
        """完全不存在的地区 → 返回 (None, {})。"""
        path, data = find_epw_for_location(["台湾", "台北"])
        assert path is None
        assert data == {}

    def test_hongkong_macau_fallback(self):
        """港澳映射到广东广州。"""
        for city in ["香港", "澳门"]:
            path, data = find_epw_for_location(["广东", city])
            assert path is not None

    def test_direct_municipality(self):
        """直辖市（北京/上海/天津/重庆）。"""
        for prov, city in [("北京", "北京"), ("上海", "上海")]:
            path, data = find_epw_for_location([prov, city])
            assert path is not None, f"应能找到 {city} 的 EPW 文件"


# ===================================================================
# 参数校验测试
# ===================================================================

class TestValidation:
    """_validate_zone 和 _validate_param_config 校验逻辑。"""

    def test_valid_zone_passes(self):
        """完整合法数据不抛异常。"""
        _validate_zone("z1", _make_zone())

    # --- 缺失字段 ---

    @pytest.mark.parametrize("field", [
        "area", "floor_height", "wall_u_value", "window_u_value",
        "window_wall_ratio", "roof_u_value",
        "people_density", "lighting_density", "equipment_density",
        "fresh_air_volume", "temperature",
    ])
    def test_missing_field_raises(self, field):
        """缺少任一必填字段 → ZoneValidationError。"""
        zone = _make_zone()
        del zone[field]
        with pytest.raises(ZoneValidationError, match=field):
            _validate_zone("z1", zone)

    # --- 类型错误 ---

    @pytest.mark.parametrize("field", [
        "area", "floor_height", "wall_u_value", "window_u_value",
        "window_wall_ratio", "roof_u_value",
    ])
    def test_numeric_field_wrong_type(self, field):
        """数值字段传入字符串 → ZoneValidationError。"""
        zone = _make_zone(**{field: "abc"})
        with pytest.raises(ZoneValidationError, match="类型错误"):
            _validate_zone("z1", zone)

    # --- 范围越界 ---

    def test_area_too_small(self):
        zone = _make_zone(area=0.0)
        with pytest.raises(ZoneValidationError, match="值超限"):
            _validate_zone("z1", zone)

    def test_area_negative(self):
        zone = _make_zone(area=-10.0)
        with pytest.raises(ZoneValidationError, match="值超限"):
            _validate_zone("z1", zone)

    def test_wwr_out_of_range(self):
        zone = _make_zone(window_wall_ratio=1.5)
        with pytest.raises(ZoneValidationError, match="值超限"):
            _validate_zone("z1", zone)

    def test_floor_height_too_large(self):
        zone = _make_zone(floor_height=100.0)
        with pytest.raises(ZoneValidationError, match="值超限"):
            _validate_zone("z1", zone)

    # --- ParamConfig 校验 ---

    def test_param_config_dict_valid(self):
        """dict 格式 ParamConfig 正常通过。"""
        _validate_param_config("z1", "temperature", {
            "mode": "fixed",
            "fixed_value": 26.0,
        })

    def test_param_config_dict_missing_fixed_value(self):
        with pytest.raises(ZoneValidationError, match="fixed_value"):
            _validate_param_config("z1", "temperature", {
                "mode": "fixed",
            })

    def test_param_config_dict_invalid_mode(self):
        with pytest.raises(ZoneValidationError, match="mode"):
            _validate_param_config("z1", "temperature", {
                "mode": "unknown",
                "fixed_value": 26.0,
            })

    def test_param_config_scheduled_missing_schedules(self):
        with pytest.raises(ZoneValidationError, match="schedules"):
            _validate_param_config("z1", "temperature", {
                "mode": "scheduled",
                "fixed_value": 26.0,
                "schedules": "not_a_list",
            })

    def test_param_config_wrong_type(self):
        with pytest.raises(ZoneValidationError, match="类型错误"):
            _validate_param_config("z1", "temperature", "26")

    # --- zone 非 dict ---

    def test_zone_not_dict(self):
        with pytest.raises(ZoneValidationError, match="类型错误"):
            _validate_zone("z1", [1, 2, 3])


# ===================================================================
# _fixed_val 测试
# ===================================================================

class TestFixedVal:
    def test_int_input(self):
        assert _fixed_val(42) == 42.0

    def test_float_input(self):
        assert _fixed_val(3.14) == 3.14

    def test_dict_input(self):
        assert _fixed_val({"fixed_value": 26.5, "mode": "fixed"}) == 26.5


# ===================================================================
# generate_idf 集成测试
# ===================================================================

class TestGenerateIdf:
    """generate_idf 正常生成与异常处理。"""

    def test_single_zone_generates_idf(self):
        """单 zone 正常生成 IDF 文本。"""
        zones = {"zone_1": _make_zone(name="Office")}
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert isinstance(idf, str)
        assert len(idf) > 100
        assert "Version" in idf
        assert "Office" in idf

    def test_multi_zone(self):
        """多 zone 生成。"""
        zones = {
            "z1": _make_zone(name="OfficeA", area=100),
            "z2": _make_zone(name="OfficeB", area=200),
        }
        idf = generate_idf(zones, DEFAULT_LOCATION)
        print(idf)
        assert "OfficeA" in idf
        assert "OfficeB" in idf

    def test_zone_id_as_fallback_name(self):
        """zone 无 name 时使用 zone_id。"""
        zones = {"my_zone": _make_zone()}  # 没有显式 name
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert "my_zone" in idf

    def test_dict_zones_required(self):
        """zones 为列表 → 报错。"""
        with pytest.raises(ZoneValidationError, match="dict"):
            generate_idf([_make_zone()], DEFAULT_LOCATION)

    def test_empty_zones_raises(self):
        """zones 为空 → 报错。"""
        with pytest.raises(ZoneValidationError):
            generate_idf({}, DEFAULT_LOCATION)

    def test_invalid_location_raises(self):
        """location 格式错误 → 报错。"""
        zones = {"z1": _make_zone()}
        with pytest.raises(ZoneValidationError, match="location"):
            generate_idf(zones, ["广东"])  # 缺少城市

    def test_location_guangzhou(self):
        """广州 location 能正确注入 Site:Location。"""
        zones = {"z1": _make_zone()}
        idf = generate_idf(zones, ["广东", "广州"])
        assert "Site:Location" in idf

    def test_location_beijing(self):
        """北京 location 测试。"""
        zones = {"z1": _make_zone()}
        idf = generate_idf(zones, ["北京", "北京"])
        assert "Site:Location" in idf

    def test_scheduled_temperature(self):
        """temperature 为 scheduled ParamConfig。"""
        zones = {
            "z1": _make_zone(temperature={
                "mode": "scheduled",
                "fixed_value": 26.0,
                "schedules": [
                    {
                        "start_month": 1, "start_day": 1,
                        "end_month": 12, "end_day": 31,
                        "start_hour": 8, "end_hour": 18,
                        "value": 26.0,
                    },
                ],
            }),
        }
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert "Schedule:Compact" in idf or "Schedule:Constant" in idf

    def test_scheduled_fresh_air(self):
        """fresh_air_volume 为 scheduled ParamConfig。"""
        zones = {
            "z1": _make_zone(fresh_air_volume={
                "mode": "scheduled",
                "fixed_value": 30.0,
                "schedules": [
                    {
                        "start_month": 1, "start_day": 1,
                        "end_month": 6, "end_day": 30,
                        "start_hour": 8, "end_hour": 18,
                        "value": 30.0,
                    },
                    {
                        "start_month": 7, "start_day": 1,
                        "end_month": 12, "end_day": 31,
                        "start_hour": 8, "end_hour": 18,
                        "value": 50.0,
                    },
                ],
            }),
        }
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert "DesignSpecification:OutdoorAir" in idf

    def test_missing_zone_field_raises(self):
        """zone 缺少 area → ZoneValidationError（集成级别）。"""
        zone = _make_zone()
        del zone["area"]
        with pytest.raises(ZoneValidationError, match="area"):
            generate_idf({"z1": zone}, DEFAULT_LOCATION)

    def test_global_building_fixed(self):
        """_global_building 输出固定名称。"""
        zones = {"z1": _make_zone()}
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert "HVAC_Simulation_Building" in idf

    def test_ground_temperature_in_idf(self):
        """IDF 中包含地温数据。"""
        zones = {"z1": _make_zone()}
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert "Site:GroundTemperature:BuildingSurface" in idf

    def test_zone_position_middle(self):
        """中间层: 地板和屋顶均为 Adiabatic。"""
        zones = {"z1": _make_zone(zone_position="middle")}
        idf = generate_idf(zones, DEFAULT_LOCATION)
        # Floor should be Adiabatic, not Ground
        assert "z1_Floor, Floor, z1_IntFloorC, z1," in idf
        assert "Adiabatic" in idf
        # Roof should be Adiabatic, not Outdoors
        assert "z1_Roof, Roof, z1_IntRoofC, z1," in idf

    def test_zone_position_top(self):
        """顶层: 屋顶为 Outdoors, 地板为 Adiabatic。"""
        zones = {"z1": _make_zone(zone_position="top")}
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert "z1_Floor, Floor, z1_IntFloorC, z1," in idf
        assert "z1_Roof, Roof, z1_RoofC, z1," in idf

    def test_zone_position_bottom(self):
        """底层: 地板为 Ground, 屋顶为 Adiabatic。"""
        zones = {"z1": _make_zone(zone_position="bottom")}
        idf = generate_idf(zones, DEFAULT_LOCATION)
        assert "z1_Floor, Floor, z1_FloorC, z1," in idf
        assert "z1_Roof, Roof, z1_IntRoofC, z1," in idf

    def test_interior_wall(self):
        """内墙应使用 Adiabatic 边界条件且无窗户。"""
        zones = {"z1": _make_zone(
            wall_config={"south_exterior": False, "north_exterior": True,
                         "east_exterior": True, "west_exterior": False}
        )}
        idf = generate_idf(zones, DEFAULT_LOCATION)
        # South wall: interior → Adiabatic, IntWallC
        assert "z1_Wall_South, Wall, z1_IntWallC, z1," in idf
        # North wall: exterior → Outdoors
        assert "z1_Wall_North, Wall, z1_WallC, z1," in idf
        # No south window (interior wall)
        assert "z1_Win_South" not in idf
        # North window should exist (exterior wall with wwr > 0)
        assert "z1_Win_North" in idf

if __name__ == "__main__":
    TestGenerateIdf().test_multi_zone()