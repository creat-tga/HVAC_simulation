"""EPW 气象文件查找与解析工具。

根据中文 [省份, 城市] 定位对应的 EPW 文件，
并从文件头提取 Site:Location 和 Site:GroundTemperature 所需数据。
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

# 项目级天气数据目录
_DEFAULT_WEATHER_DIR = Path(__file__).resolve().parents[4] / "data" / "weather"

# ---------------------------------------------------------------------------
# 中文省份 → EPW 文件名中的省份前缀
# EPW 文件命名规则: CHN_{prefix}_{city}.{WMO}_{source}.epw
# ---------------------------------------------------------------------------

_PROVINCE_PREFIXES: dict[str, list[str]] = {
    "北京": ["Beijing"],
    "天津": ["TJ"],
    "上海": ["Shanghai"],
    "重庆": ["CQ"],
    "河北": ["HE"],
    "山西": ["SX"],
    "内蒙古": ["NM"],
    "辽宁": ["LN"],
    "吉林": ["JL"],
    "黑龙江": ["HL", "Heilongjiang"],
    "江苏": ["JS"],
    "浙江": ["ZJ"],
    "安徽": ["AH"],
    "福建": ["FJ"],
    "江西": ["JX"],
    "山东": ["SD"],
    "河南": ["HA"],
    "湖北": ["HB"],
    "湖南": ["HN"],
    "广东": ["GD", "Guangdong"],
    "广西": ["GX"],
    "海南": ["HI"],
    "四川": ["SC"],
    "贵州": ["GZ"],
    "云南": ["YN", "Yunnan"],
    "西藏": ["XZ"],
    "陕西": ["SN"],
    "甘肃": ["GS"],
    "青海": ["QH"],
    "宁夏": ["NX"],
    "新疆": ["XJ"],
    "台湾": [],
    "香港": ["Guangdong", "GD"],
    "澳门": ["Guangdong", "GD"],
}

# ---------------------------------------------------------------------------
# 中文城市名 → EPW LOCATION 头部的英文城市名
# 仅包含有对应 EPW 文件的城市
# ---------------------------------------------------------------------------

_CITY_CN_TO_EN: dict[str, str] = {
    # ---- 直辖市 ----
    "北京": "Beijing", "天津": "Tianjin", "上海": "Shanghai",
    "重庆": "Chongqing",
    # ---- 河北 (HE) ----
    "石家庄": "Shijiazhuang", "唐山": "Tangshan", "秦皇岛": "Shanhaiguan",
    "邯郸": "Xingtai", "邢台": "Xingtai", "保定": "Baoding",
    "张家口": "Zhangjiakou", "承德": "Chengde", "沧州": "Cangzhou",
    "廊坊": "Baoding", "衡水": "Raoyang",
    # ---- 山西 (SX) ----
    "太原": "Taiyuan", "大同": "Datong", "阳泉": "Yangquan",
    "长治": "Changzhi", "晋城": "Yangcheng", "朔州": "Datong",
    "晋中": "Jiexiu", "运城": "Yuncheng", "忻州": "Xinzhou",
    "临汾": "Houma", "吕梁": "Lishi",
    # ---- 内蒙古 (NM) ----
    "呼和浩特": "Hohhot", "包头": "Hohhot", "乌海": "Dongsheng",
    "赤峰": "Chifeng", "通辽": "Tongliao", "鄂尔多斯": "Dongsheng",
    "呼伦贝尔": "Hailar", "巴彦淖尔": "Linhe", "乌兰察布": "Hohhot",
    "兴安盟": "Arxan", "锡林郭勒盟": "Xilinhot", "阿拉善盟": "Ejin",
    # ---- 辽宁 (LN) ----
    "沈阳": "Shenyang", "大连": "Dalian", "鞍山": "Anshan",
    "抚顺": "Shenyang", "本溪": "Benxi", "丹东": "Dandong",
    "锦州": "Jinzhou", "营口": "Yingkou", "阜新": "Fuxin",
    "辽阳": "Shenyang", "盘锦": "Yingkou", "铁岭": "Shenyang",
    "朝阳": "Chaoyang", "葫芦岛": "Xingcheng",
    # ---- 吉林 (JL) ----
    "长春": "Changchun", "吉林": "Jilin", "四平": "Siping",
    "辽源": "Siping", "通化": "Tonghua", "白山": "Linjiang",
    "松原": "Changchun", "白城": "Baicheng", "延边": "Yanji",
    # ---- 黑龙江 (HL) ----
    "哈尔滨": "Harbin", "齐齐哈尔": "Fuyu", "鸡西": "Jixi",
    "鹤岗": "Hegang", "双鸭山": "Baoqing", "大庆": "Anda",
    "伊春": "Yichun", "佳木斯": "Jiamusi", "七台河": "Jixi",
    "牡丹江": "Mudanjiang", "黑河": "Sunwu", "绥化": "Hailun",
    "大兴安岭": "Mohe",
    # ---- 江苏 (JS) ----
    "南京": "Nanjing", "无锡": "Changzhou", "徐州": "Ganyu",
    "常州": "Changzhou", "苏州": "Suzhou", "南通": "Lusi",
    "连云港": "Ganyu", "淮安": "Huaiyang", "盐城": "Sheyang",
    "扬州": "Nanjing", "镇江": "Nanjing", "泰州": "Changzhou",
    "宿迁": "Ganyu",
    # ---- 浙江 (ZJ) ----
    "杭州": "Hangzhou", "宁波": "Ningbo", "温州": "Wenzhou",
    "嘉兴": "Hangzhou", "湖州": "Hangzhou", "绍兴": "Shengxian",
    "金华": "Jinhua", "衢州": "Quxian", "舟山": "Dinghai",
    "台州": "Hongjia", "丽水": "Longquan",
    # ---- 安徽 (AH) ----
    "合肥": "Hefei", "芜湖": "Wuhu", "蚌埠": "Bengbu",
    "淮南": "Shouxian", "马鞍山": "Hefei", "淮北": "Boxian",
    "铜陵": "Anqing", "安庆": "Anqing", "黄山": "Tunxi",
    "滁州": "Hefei", "阜阳": "Fuyang", "宿州": "Boxian",
    "六安": "Huoshan", "亳州": "Boxian", "池州": "Anqing",
    "宣城": "Hefei",
    # ---- 福建 (FJ) ----
    "福州": "Fuzhou", "厦门": "Xiamen", "莆田": "Fuzhou",
    "三明": "Yongan", "泉州": "Xiamen", "漳州": "Zhangzhou",
    "南平": "Nanping", "龙岩": "Longyan", "宁德": "Fuding",
    # ---- 江西 (JX) ----
    "南昌": "Nanchang", "景德镇": "Jingdezhen", "萍乡": "Nanchang",
    "九江": "Lushan", "新余": "Nanchang", "鹰潭": "Yushan",
    "赣州": "Xunwu", "吉安": "Jian", "宜春": "Yichun",
    "抚州": "Guangchang", "上饶": "Yushan",
    # ---- 山东 (SD) ----
    "济南": "Jinan", "青岛": "Qingdao", "淄博": "Jinan",
    "枣庄": "Yanzhou", "东营": "Huimin", "烟台": "Yantai",
    "潍坊": "Weifang", "济宁": "Yanzhou", "泰安": "Jinan",
    "威海": "Weihai", "日照": "Rizhao", "临沂": "Linyi",
    "德州": "Lingxian", "聊城": "Jinan", "滨州": "Huimin",
    "菏泽": "Heze",
    # ---- 河南 (HA) ----
    "郑州": "Zhengzhou", "开封": "Kaifeng", "洛阳": "Luoyang",
    "平顶山": "Nanyang", "安阳": "Anyang", "鹤壁": "Anyang",
    "新乡": "Zhengzhou", "焦作": "Zhengzhou", "濮阳": "Anyang",
    "许昌": "Xuchang", "漯河": "Zhumadian", "三门峡": "Lushi",
    "南阳": "Nanyang", "商丘": "Shangqiu", "信阳": "Xinyang",
    "周口": "Zhumadian", "驻马店": "Zhumadian", "济源": "Zhengzhou",
    # ---- 湖北 (HB) ----
    "武汉": "Wuhan", "黄石": "Wuhan", "十堰": "Yunxi",
    "宜昌": "Yichang", "襄阳": "Laohekou", "鄂州": "Wuhan",
    "荆门": "Zhongxiang", "孝感": "Wuhan", "荆州": "Jingzhou",
    "黄冈": "Macheng", "咸宁": "Wuhan", "随州": "Suizhou",
    "恩施": "Exi", "仙桃": "Wuhan", "潜江": "Wuhan",
    "天门": "Wuhan", "神农架": "Exi",
    # ---- 湖南 (HN) ----
    "长沙": "Changsha", "株洲": "Zhuzhou", "湘潭": "Xiangtan",
    "衡阳": "Hengyang", "邵阳": "Shaoyang", "岳阳": "Yueyang",
    "常德": "Changde", "张家界": "Sangzhi", "益阳": "Changde",
    "郴州": "Chenzhou", "永州": "Lingling", "怀化": "Huaihua",
    "娄底": "Changsha", "湘西": "Jishou",
    # ---- 广东 (GD) ----
    "广州": "Guangzhou", "韶关": "Shaoguan", "深圳": "Shenzhen",
    "珠海": "Guangzhou", "汕头": "Shantou", "佛山": "Guangzhou",
    "江门": "Guangzhou", "湛江": "Zhanjiang", "茂名": "Xinyi",
    "肇庆": "Zhaoqing", "惠州": "Huiyang", "梅州": "Heyuan",
    "汕尾": "Shanwei", "河源": "Heyuan", "阳江": "Yangjiang",
    "清远": "Lianzhou", "东莞": "Guangzhou", "中山": "Guangzhou",
    "潮州": "Shantou", "揭阳": "Huilai", "云浮": "Guangzhou",
    # ---- 广西 (GX) ----
    "南宁": "Nanning", "柳州": "Liuzhou", "桂林": "Guilin",
    "梧州": "Wuzhou", "北海": "Beihai", "防城港": "Qinzhou",
    "钦州": "Qinzhou", "贵港": "Guiping", "玉林": "Bobai",
    "百色": "Baise", "贺州": "Hexian", "河池": "Hechi",
    "来宾": "Nanning", "崇左": "Longzhou",
    # ---- 海南 (HI) ----
    "海口": "Haikou", "三亚": "Sanya", "三沙": "Haikou",
    "儋州": "Danxian", "五指山": "Qionghai", "琼海": "Qionghai",
    "文昌": "Haikou", "万宁": "Qionghai", "东方": "Dongfang",
    # ---- 四川 (SC) ----
    "成都": "Chengdu", "自贡": "Leshan", "攀枝花": "Xichang",
    "泸州": "Luzhou", "德阳": "Mianyang", "绵阳": "Mianyang",
    "广元": "Mianyang", "遂宁": "Suining", "内江": "Leshan",
    "乐山": "Leshan", "南充": "Nanchong", "眉山": "Chengdu",
    "宜宾": "Yibin", "广安": "Nanchong", "达州": "Dachuan",
    "雅安": "Ya", "巴中": "Bazhong", "资阳": "Chengdu",
    "阿坝": "Barkam", "甘孜": "Garze", "凉山": "Xichang",
    # ---- 贵州 (GZ) ----
    "贵阳": "Guiyang", "六盘水": "Weining", "遵义": "Zunyi",
    "安顺": "Anshun", "毕节": "Bijie", "铜仁": "Sinan",
    "黔西南": "Xingren", "黔东南": "Sansui", "黔南": "Dushan",
    # ---- 云南 (YN) ----
    "昆明": "Kunming", "曲靖": "Zhanyi", "玉溪": "Yuxi",
    "保山": "Baoshan", "昭通": "Zhaotong", "丽江": "Lijiang",
    "普洱": "Simao", "临沧": "Lincang", "楚雄": "Chuxiong",
    "红河": "Honghe", "文山": "Wenshan", "西双版纳": "Xishuangbanna",
    "大理": "Dali", "德宏": "Ruili", "怒江": "Deqen",
    "迪庆": "Deqen",
    # ---- 西藏 (XZ / XJ for TMYx) ----
    "拉萨": "Lhasa", "日喀则": "Xigaze", "昌都": "Qamdo",
    "林芝": "Nyingchi", "山南": "Nedong", "那曲": "Nagqu",
    "阿里": "Ngari",
    # ---- 陕西 (SN) ----
    "西安": "Xian", "铜川": "Tongchuan", "宝鸡": "Baoji",
    "咸阳": "Xian", "渭南": "Xian", "延安": "Yanan",
    "汉中": "Hanzhong", "榆林": "Yulin", "安康": "Ankangan",
    "商洛": "Xian",
    # ---- 甘肃 (GS) ----
    "兰州": "Lanzhou", "嘉峪关": "Jiuquan", "金昌": "Jiuquan",
    "白银": "Lanzhou", "天水": "Tianshui", "武威": "Lanzhou",
    "张掖": "Zhangye", "平凉": "Pingliang", "酒泉": "Jiuquan",
    "庆阳": "Xifengzhen", "定西": "Lanzhou", "陇南": "Longnan",
    "临夏": "Lanzhou", "甘南": "Hezuo",
    # ---- 青海 (QH) ----
    "西宁": "Xining", "海东": "Minhe", "海北": "Gangca",
    "黄南": "Xining", "海南州": "Xining", "果洛": "Darlag",
    "玉树": "Yushu", "海西": "Golmud",
    # ---- 宁夏 (NX) ----
    "银川": "Yinchuan", "石嘴山": "Yinchuan", "吴忠": "Yinchuan",
    "固原": "Guyuan", "中卫": "Zhongning",
    # ---- 新疆 (XJ / XZ for TMYx) ----
    "乌鲁木齐": "Urumqi", "克拉玛依": "Karamay", "吐鲁番": "Turpan",
    "哈密": "Hami", "昌吉": "Urumqi", "博尔塔拉": "Bortala",
    "巴音郭楞": "Korla", "阿克苏": "Kuqa", "克孜勒苏": "Kashi",
    "喀什": "Kashi", "和田": "Hotan", "伊犁": "Jinghe",
    "塔城": "Tacheng", "阿勒泰": "Altay",
    # ---- 台湾 (无EPW，留空使用省会回退) ----
    "台北": "", "高雄": "", "台中": "", "台南": "", "新北": "", "桃园": "",
    # ---- 港澳（使用广州数据） ----
    "香港": "Guangzhou", "澳门": "Guangzhou",
}

# 省会城市英文名（找不到精确匹配时的回退）
_PROVINCE_CAPITAL_EN: dict[str, str] = {
    "北京": "Beijing", "天津": "Tianjin", "上海": "Shanghai",
    "重庆": "Chongqing",
    "河北": "Shijiazhuang", "山西": "Taiyuan", "内蒙古": "Hohhot",
    "辽宁": "Shenyang", "吉林": "Changchun", "黑龙江": "Harbin",
    "江苏": "Nanjing", "浙江": "Hangzhou", "安徽": "Hefei",
    "福建": "Fuzhou", "江西": "Nanchang", "山东": "Jinan",
    "河南": "Zhengzhou", "湖北": "Wuhan", "湖南": "Changsha",
    "广东": "Guangzhou", "广西": "Nanning", "海南": "Haikou",
    "四川": "Chengdu", "贵州": "Guiyang", "云南": "Kunming",
    "西藏": "Lhasa", "陕西": "Xian", "甘肃": "Lanzhou",
    "青海": "Xining", "宁夏": "Yinchuan", "新疆": "Urumqi",
    "台湾": "", "香港": "Guangzhou", "澳门": "Guangzhou",
}


# ---------------------------------------------------------------------------
# EPW 文件解析
# ---------------------------------------------------------------------------

def parse_epw_header(epw_path: Path) -> dict[str, Any]:
    """从 EPW 文件头部提取位置信息和地温数据。

    返回:
        {
            "name": 城市英文名,
            "lat": 纬度, "lon": 经度,
            "tz": 时区, "elev": 海拔 [m],
            "ground_temps": [12 个月均地表温度 (0.5m 深度)]
        }
    """
    result: dict[str, Any] = {}
    with open(epw_path, "r", encoding="utf-8", errors="replace") as f:
        for _ in range(8):
            line = f.readline()
            if not line:
                break
            parts = line.strip().split(",")
            if parts[0] == "LOCATION":
                result["name"] = parts[1]
                result["lat"] = float(parts[6])
                result["lon"] = float(parts[7])
                result["tz"] = float(parts[8])
                result["elev"] = float(parts[9])
            elif parts[0] == "GROUND TEMPERATURES" and len(parts) > 17:
                # 格式: GROUND TEMPERATURES,count,depth,cond,dens,cp,T1..T12,...
                # 0.5m 深度数据从 index 6 开始，共 12 个值
                result["ground_temps"] = [float(parts[i]) for i in range(6, 18)]
    return result


# ---------------------------------------------------------------------------
# EPW 文件索引（懒加载缓存）
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4)
def _build_epw_index(weather_dir: str) -> dict[str, tuple[Path, dict[str, Any]]]:
    """构建 EPW 文件索引：英文城市名(小写) → (文件路径, 解析数据)。"""
    index: dict[str, tuple[Path, dict[str, Any]]] = {}
    d = Path(weather_dir)
    if not d.is_dir():
        return index
    for epw in d.glob("*.epw"):
        header = parse_epw_header(epw)
        city = header.get("name", "")
        if city:
            # 索引键使用小写城市名的第一个词（处理 "Chongqing Shapingba" 等情况）
            # 同时处理连字符和点号分隔 ("Huaiyang-Qingjiang", "Qingdao.Intl.AP")
            parts = re.split(r"[\s\-.]", city.lower())
            key = parts[0]
            index[key] = (epw, header)
            # 同时用完整名作为备选键
            full_key = city.lower().replace(" ", "")
            if full_key != key:
                index[full_key] = (epw, header)
    return index


# ---------------------------------------------------------------------------
# 公开接口
# ---------------------------------------------------------------------------

def find_epw_for_location(
    location: list[str],
    weather_dirs: list[Path] | None = None,
) -> tuple[Path | None, dict[str, Any]]:
    """根据中文 [省份, 城市] 查找最匹配的 EPW 文件。

    查找优先级：
    1. 城市精确匹配
    2. 省会城市回退
    3. 该省任意 EPW 文件

    参数:
        location: [省份, 城市]，如 ["广东", "广州"]
        weather_dirs: EPW 文件搜索目录列表

    返回:
        (epw_file_path, parsed_header_data) 或 (None, {})
    """
    if weather_dirs is None:
        weather_dirs = [_DEFAULT_WEATHER_DIR]

    province = location[0] if len(location) > 0 else ""
    city = location[1] if len(location) > 1 else province

    # 构建索引
    for d in weather_dirs:
        index = _build_epw_index(str(d))
        if index:
            break
    else:
        return None, {}

    # 1) 精确城市匹配
    target_en = _CITY_CN_TO_EN.get(city, "")
    if target_en:
        key = target_en.lower().split()[0]
        if key in index:
            return index[key]

    # 2) 省会回退
    capital_en = _PROVINCE_CAPITAL_EN.get(province, "")
    if capital_en:
        key = capital_en.lower().split()[0]
        if key in index:
            return index[key]

    # 3) 该省任意 EPW
    prefixes = _PROVINCE_PREFIXES.get(province, [])
    for d in weather_dirs:
        d_path = Path(d) if not isinstance(d, Path) else d
        for epw in d_path.glob("*.epw"):
            stem = epw.stem
            for pfx in prefixes:
                if f"CHN_{pfx}_" in stem or f"CHN_{pfx}." in stem:
                    return epw, parse_epw_header(epw)

    return None, {}
