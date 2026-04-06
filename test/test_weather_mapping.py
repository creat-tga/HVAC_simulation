"""Test weather_utils city mapping coverage."""
import sys
sys.path.insert(0, "backend")

from app.simulation.energyplus.weather_utils import _CITY_CN_TO_EN, find_epw_for_location

print(f"Total cities mapped: {len(_CITY_CN_TO_EN)}")

# Taiwan cities have empty mapping
missing = [c for c, e in _CITY_CN_TO_EN.items() if not e]
print(f"Cities with empty mapping (Taiwan): {missing}")

# Test specific mappings
test_cases = [
    (["安徽", "淮南"], "Shouxian"),
    (["安徽", "安庆"], "Anqing"),
    (["广东", "深圳"], "Shenzhen"),
    (["湖北", "襄阳"], "Laohekou"),
    (["北京", "北京"], "Beijing"),
    (["河南", "郑州"], "Zhengzhou"),
    (["四川", "成都"], "Chengdu"),
    (["新疆", "乌鲁木齐"], "Urumqi"),
    (["黑龙江", "齐齐哈尔"], "Fuyu"),
    (["江苏", "苏州"], "Suzhou"),
    (["浙江", "宁波"], "Ningbo"),
    (["海南", "三亚"], "Sanya"),
    (["安徽", "蚌埠"], "Bengbu"),
    (["安徽", "芜湖"], "Wuhu"),
]

print("\n--- EPW Lookup Tests ---")
all_pass = True
for location, expected_en in test_cases:
    epw, hdr = find_epw_for_location(location)
    city_name = hdr.get("name", "NOT_FOUND")
    found = expected_en.lower() in city_name.lower() if epw else False
    status = "PASS" if found else "FAIL"
    if not found:
        all_pass = False
    print(f"  {status}: {location[0]}-{location[1]} -> EPW: {epw.name if epw else 'NONE'}, City: {city_name}")

# Test all region.ts cities can resolve (at least via province fallback)
print("\n--- Full Coverage Test ---")
no_match = []
for city, en_name in _CITY_CN_TO_EN.items():
    if not en_name:  # Taiwan - skip
        continue
    # Try to find EPW using a dummy province (the find function uses _CITY_CN_TO_EN directly)
    epw, hdr = find_epw_for_location(["", city])
    if not epw:
        no_match.append(city)

if no_match:
    print(f"  WARNING: {len(no_match)} cities could not resolve EPW: {no_match}")
else:
    print(f"  All {len(_CITY_CN_TO_EN) - len(missing)} non-Taiwan cities resolve to an EPW file")

if all_pass and not no_match:
    print("\nAll tests PASSED!")
else:
    print(f"\nSome tests failed: lookup={all_pass}, coverage={'PASS' if not no_match else 'FAIL'}")
