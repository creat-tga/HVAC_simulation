from __future__ import annotations

import sys
import uuid
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.integrations.multisystem_adapter import MultiSystemPayloadError, _load_distribution, build_multisystem_payload
from app.services.library_service import _normalize_equipment_entry


def profile(value: float) -> dict:
    return {
        "mode": "fixed",
        "fixed_value": value,
        "month_values": [value] * 12,
        "load_values": [value] * 11,
        "dry_bulb_values": [value] * 10,
        "wet_bulb_values": [value] * 10,
        "constant_pressure": False,
    }


def equipment(equipment_id, name, model, **parameters):
    return NS(id=equipment_id, name=name, model_no=model, parameters=parameters)


def test_builds_chiller_contract_and_normalizes_humidity():
    sub_id, combo_id, tower_group_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    chiller_id, chw_id, cw_id, tower_id = (uuid.uuid4() for _ in range(4))
    combo = NS(
        id=combo_id, primary_model_id=chiller_id, chw_pump_model_id=chw_id, cw_pump_model_id=cw_id,
        primary_count=1, primary_factor=0.92, chw_connection="parallel", cw_connection="parallel",
        chw_pump_count=1, chw_pump_backup=0, cw_pump_count=1, cw_pump_backup=0,
        chw_pump_factor=0.77, cw_pump_factor=0.77,
    )
    tower_group = NS(id=tower_group_id, tower_model_id=tower_id, count=1, factor=0.85)
    subsystem = NS(
        id=sub_id, name="机房", subsystem_type="chiller_plant", combos=[combo], tower_groups=[tower_group],
        design_params={"chw_supply_temp": 7, "chw_delta_temp": 5, "chw_pump_head": 35, "header_pressure_drop": 21,
                       "cw_supply_temp": 30, "cw_delta_temp": 5, "cw_pump_head": 30},
    )
    strategy = {
        "run_schedules": [],
        "water_temp": {"chw_supply": profile(7), "chw_delta": profile(5), "approach": profile(3), "cw_delta": profile(5)},
        "equipment": {
            "chiller_stages": [{"combo_counts": {str(combo_id): 1}, "loading_down": None, "loading_up": None}],
            "chw_pump": {"min_freq": 30, "max_freq": 50}, "cw_pump": {"min_freq": 30, "max_freq": 50},
            "tower": {"min_freq": 30, "max_freq": 50, "m": 1, "k": 0},
        },
    }
    scheme = NS(
        safety_margin=1.0, subsystems=[subsystem],
        control_strategy={
            "system_strategies": {str(sub_id): strategy},
            "load_distribution": {
                "mode": "fixed_ratio", "groups": [{"id": "g1"}],
                "subsystem_group_map": {str(sub_id): "g1"},
                "group_settings": {"g1": {"mode": "fixed_ratio", "ratios": {str(sub_id): 100}}},
            },
        },
    )
    pump_params = {"coe_head": [0, 1], "coe_power": [0, 2], "frequency_min": 30, "frequency_max": 50, "flux_min": 0, "flux_max": 200}
    equipment_map = {
        chiller_id: equipment(chiller_id, "冷机", "CE800", machine_type="lxj", standby_power=1, evap_dp=6.5, cond_dp=7, evap_flow=137.5, cond_flow=165),
        chw_id: equipment(chw_id, "冷冻泵", "P1", **pump_params),
        cw_id: equipment(cw_id, "冷却泵", "P2", **pump_params),
        tower_id: equipment(tower_id, "冷却塔", "T1", head=3.7, coe0=2.36, coe1=0.6, flow=165, power=5.5,
                            frequency_min=30, frequency_max=50, wet_bulb=28, dry_bulb=32, inlet_temp=37, outlet_temp=32, rh_out_set=1),
    }
    load = NS(hourly_cooling_load=[100, 0], hourly_heating_load=[0, 0])
    payload = build_multisystem_payload(
        scheme=scheme, building=NS(), load_result=load, equipment_map=equipment_map,
        weather={"dry_bulb_temperature": [32, 30], "relative_humidity": [65, 0.5]}, altitude=12,
    )
    assert payload["meteorology"] == [{"Ta_db": 32.0, "RH": 0.65}, {"Ta_db": 30.0, "RH": 0.5}]
    config = payload["hvac_system"][0]["config"]
    assert config["chiller_pump"][0]["chiller"]["machine_type"] == "lxj"
    assert config["chiller_pump"][0]["evaporator"]["header"] == pytest.approx(7.5)
    assert config["strategy"]["equipment"]["chiller"][0]["min"] == 0.3
    assert payload["load_distribution"][0]["load"][0]["cooling_load"] == 100.0


def test_rejects_multiple_groups_without_zone_hourly_loads():
    scheme = NS(
        subsystems=[NS(id=uuid.uuid4())],
        control_strategy={"load_distribution": {"groups": [{"id": "a"}, {"id": "b"}]}},
    )
    with pytest.raises(MultiSystemPayloadError, match="只支持一个负荷分组"):
        _load_distribution(scheme, [1.0], [0.0])

def test_equipment_normalization_preserves_engine_parameters():
    pump = _normalize_equipment_entry("pump", {
        "factory": "厂商", "model": "P1", "deliveryDesign": "10", "deliveryMin": "18",
        "deliveryHead": "20", "powerDesign": "3", "efficiency": "80%",
        "frequencyMin": "30", "frequencyMax": "50",
        "dhFcList": [0, 0.1, 2, 0, 0], "dpFcList": [0, 0.2, 3, 0],
    })
    assert pump is not None
    assert pump["parameters"]["coe_head"] == [0.0, 0.1, 2.0]
    assert pump["parameters"]["coe_power"] == [0.0, 0.2, 3.0]
    assert pump["parameters"]["flux_max"] == 18.0

    tower = _normalize_equipment_entry("cooling_tower", {
        "factory": "厂商", "model": "T1", "delivery": "100", "powerEm": "5.5",
        "deliveryHead": "3.7", "wit": "37", "wot": "32", "wt": "28",
        "fdfMin": "30", "fdfMax": "50", "rh": "1", "graphList": ["2.36", "0.6"],
    })
    assert tower is not None
    assert tower["parameters"]["coe0"] == 2.36
    assert tower["parameters"]["frequency_min"] == 30.0

def test_builds_two_pipe_module_contract():
    sub_id, combo_id = uuid.uuid4(), uuid.uuid4()
    module_id, pump_id = uuid.uuid4(), uuid.uuid4()
    combo = NS(
        id=combo_id, primary_model_id=module_id, chw_pump_model_id=pump_id, cw_pump_model_id=None,
        primary_count=2, group_count=3, primary_factor=0.95, chw_connection="parallel", cw_connection="parallel",
        chw_pump_count=2, chw_pump_backup=1, cw_pump_count=1, cw_pump_backup=0,
        chw_pump_factor=0.9, cw_pump_factor=1.0,
    )
    subsystem = NS(
        id=sub_id, name="模块机", subsystem_type="air_cooled", combos=[combo], tower_groups=[],
        design_params={"pipe_system": "two_pipe", "cooling_supply_temp": 7, "cooling_delta_temp": 5,
                       "heating_supply_temp": 45, "heating_delta_temp": 5, "pump_head": 35, "header_pressure_drop": 21},
    )
    strategy = {
        "run_schedules": [],
        "water_temp": {"cooling_supply": profile(7), "cooling_delta": profile(5),
                       "heating_supply": profile(45), "heating_delta": profile(5)},
        "equipment": {
            "module_stages": [{"combo_counts": {str(combo_id): 1}, "loading_down": None, "loading_up": None}],
            "pump": {"min_freq": 30, "max_freq": 50},
        },
    }
    scheme = NS(
        safety_margin=1.0, subsystems=[subsystem],
        control_strategy={
            "system_strategies": {str(sub_id): strategy},
            "load_distribution": {
                "mode": "by_priority", "groups": [{"id": "g1"}],
                "subsystem_group_map": {str(sub_id): "g1"},
                "group_settings": {"g1": {"mode": "by_priority", "priorities": {str(sub_id): 1}}},
            },
        },
    )
    equipment_map = {
        module_id: equipment(module_id, "模块机", "LSQWRF130", frequency_mode="variable", standby_power=0,
                             cooling_dp=5, heating_dp=5, cooling_flow=22.4, heating_flow=24.1),
        pump_id: equipment(pump_id, "水泵", "P1", coe_head=[0, 1], coe_power=[0, 2],
                           frequency_min=30, frequency_max=50, flux_min=0, flux_max=100),
    }
    payload = build_multisystem_payload(
        scheme=scheme, building=NS(), load_result=NS(hourly_cooling_load=[100], hourly_heating_load=[0]),
        equipment_map=equipment_map,
        weather={"dry_bulb_temperature": [32], "relative_humidity": [65]}, altitude=20,
    )
    system = payload["hvac_system"][0]
    assert system["type"] == "module_plant"
    assert system["config"]["module_pump"][0]["number_group"] == 3
    assert system["config"]["module_pump"][0]["water"]["flux"] == pytest.approx(48.2)
    assert payload["load_distribution"][0]["mode"] == "priority"