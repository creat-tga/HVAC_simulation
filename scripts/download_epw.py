#!/usr/bin/env python3
"""从 climate.onebuilding.org 下载缺失的 EPW 气象文件。

用法: python scripts/download_epw.py
"""

import io
import ssl
import sys
import zipfile
import urllib.request
from pathlib import Path

BASE_URL = "https://climate.onebuilding.org/WMO_Region_2_Asia/CHN_China"
WEATHER_DIR = Path(__file__).resolve().parent.parent / "data" / "weather"

# (province_folder, zip_filename) — 需要下载的 EPW 文件列表
# 优先使用 CSWD 格式，不可用时使用 TMYx（基础版，无年份后缀）
# 注意：climate.onebuilding.org 中 XJ/XZ 文件夹用于 TMYx 时有交换现象：
#   - 西藏 TMYx 文件用 CHN_XJ_ 前缀，放在 XJ_Xinjiang_Uyghur 文件夹
#   - 新疆 TMYx 文件用 CHN_XZ_ 前缀，放在 XZ_Tibet 文件夹
DOWNLOADS: list[tuple[str, str]] = [
    # === 安徽 AH ===
    ("AH_Anhui", "CHN_AH_Anqing.584240_TMYx.zip"),          # 安庆
    ("AH_Anhui", "CHN_AH_Bengbu.582210_CSWD.zip"),           # 蚌埠
    ("AH_Anhui", "CHN_AH_Wuhu.583340_TMYx.zip"),             # 芜湖
    ("AH_Anhui", "CHN_AH_Fuyang.AP.582030_TMYx.zip"),        # 阜阳
    ("AH_Anhui", "CHN_AH_Huoshan.583140_TMYx.zip"),          # 六安(霍山)

    # === 河北 HE ===
    ("HE_Hebei", "CHN_HE_Cangzhou.546160_TMYx.zip"),         # 沧州

    # === 山西 SX ===
    ("SX_Shanxi", "CHN_SX_Yangquan.537820_TMYx.zip"),        # 阳泉
    ("SX_Shanxi", "CHN_SX_Changzhi.538870_TMYx.zip"),        # 长治
    ("SX_Shanxi", "CHN_SX_Yangcheng.539750_TMYx.zip"),       # 晋城(阳城)
    ("SX_Shanxi", "CHN_SX_Jiexiu.538630_CSWD.zip"),          # 晋中(介休)
    ("SX_Shanxi", "CHN_SX_Lishi.537640_TMYx.zip"),           # 吕梁(离石)
    ("SX_Shanxi", "CHN_SX_Xinzhou.536640_TMYx.zip"),         # 忻州

    # === 辽宁 LN ===
    ("LN_Liaoning", "CHN_LN_Anshan.543390_TMYx.zip"),        # 鞍山
    ("LN_Liaoning", "CHN_LN_Fuxin.542370_TMYx.zip"),         # 阜新

    # === 吉林 JL ===
    ("JL_Jilin", "CHN_JL_Jilin.541720_TMYx.zip"),            # 吉林市
    ("JL_Jilin", "CHN_JL_Tonghua.543630_TMYx.zip"),          # 通化
    ("JL_Jilin", "CHN_JL_Baicheng.509360_CSWD.zip"),         # 白城

    # === 黑龙江 HL ===
    ("HL_Heilongjiang", "CHN_HL_Yichun.507740_TMYx.zip"),    # 伊春
    ("HL_Heilongjiang", "CHN_HL_Hegang.507750_TMYx.zip"),    # 鹤岗
    ("HL_Heilongjiang", "CHN_HL_Baoqing.508880_TMYx.zip"),   # 双鸭山(宝清)

    # === 江苏 JS ===
    ("JS_Jiangsu", "CHN_JS_Lusi.582650_CSWD.zip"),           # 南通(吕四)
    ("JS_Jiangsu", "CHN_JS_Suzhou.583580_TMYx.zip"),          # 苏州
    ("JS_Jiangsu", "CHN_JS_Sheyang.581500_TMYx.zip"),         # 盐城(射阳)

    # === 浙江 ZJ ===
    ("ZJ_Zhejiang", "CHN_ZJ_Ningbo.585620_TMYx.zip"),        # 宁波
    ("ZJ_Zhejiang", "CHN_ZJ_Jinhua.585490_TMYx.zip"),        # 金华
    ("ZJ_Zhejiang", "CHN_ZJ_Longquan.586470_TMYx.zip"),      # 丽水(龙泉)
    ("ZJ_Zhejiang", "CHN_ZJ_Shengxian.585560_TMYx.zip"),     # 绍兴(嵊县)

    # === 福建 FJ ===
    ("FJ_Fujian", "CHN_FJ_Longyan.589270_TMYx.zip"),         # 龙岩
    ("FJ_Fujian", "CHN_FJ_Zhangzhou.591260_TMYx.zip"),        # 漳州
    ("FJ_Fujian", "CHN_FJ_Fuding.587540_TMYx.zip"),           # 宁德(福鼎)

    # === 江西 JX ===
    ("JX_Jiangxi", "CHN_JX_Lushan.585060_TMYx.zip"),         # 九江(庐山)
    ("JX_Jiangxi", "CHN_JX_Yichun.577930_TMYx.zip"),         # 宜春
    ("JX_Jiangxi", "CHN_JX_Guangchang.588130_TMYx.zip"),     # 抚州(广昌)
    ("JX_Jiangxi", "CHN_JX_Xunwu.591020_TMYx.zip"),          # 赣州(寻乌)

    # === 山东 SD ===
    ("SD_Shandong", "CHN_SD_Yantai.547630_TMYx.zip"),        # 烟台
    ("SD_Shandong", "CHN_SD_Weihai.547740_TMYx.zip"),         # 威海
    ("SD_Shandong", "CHN_SD_Rizhao.549450_TMYx.zip"),         # 日照
    ("SD_Shandong", "CHN_SD_Linyi.549380_TMYx.zip"),          # 临沂
    ("SD_Shandong", "CHN_SD_Heze.Caozhou.549060_TMYx.zip"),   # 菏泽
    ("SD_Shandong", "CHN_SD_Lingxian.547150_TMYx.zip"),        # 德州(陵县)

    # === 河南 HA ===
    ("HA_Henan", "CHN_HA_Kaifeng.570910_TMYx.zip"),          # 开封
    ("HA_Henan", "CHN_HA_Luoyang.570730_TMYx.zip"),           # 洛阳
    ("HA_Henan", "CHN_HA_Xuchang.570890_TMYx.zip"),           # 许昌

    # === 湖北 HB ===
    ("HB_Hubei", "CHN_HB_Laohekou.572650_CSWD.zip"),         # 襄阳(老河口)
    ("HB_Hubei", "CHN_HB_Suizhou.573850_TMYx.zip"),           # 随州
    ("HB_Hubei", "CHN_HB_Jingzhou-Jiangling.574760_TMYx.zip"),# 荆州
    ("HB_Hubei", "CHN_HB_Zhongxiang.573780_TMYx.zip"),        # 荆门(钟祥)

    # === 湖南 HN ===
    ("HN_Hunan", "CHN_HN_Hengyang.578720_TMYx.zip"),         # 衡阳
    ("HN_Hunan", "CHN_HN_Shaoyang.577660_TMYx.zip"),          # 邵阳
    ("HN_Hunan", "CHN_HN_Yueyang.575840_TMYx.zip"),           # 岳阳
    ("HN_Hunan", "CHN_HN_Chenzhou.579720_TMYx.zip"),          # 郴州
    ("HN_Hunan", "CHN_HN_Lingling.578660_CSWD.zip"),          # 永州(零陵)
    ("HN_Hunan", "CHN_HN_Huaihua.577490_TMYx.zip"),           # 怀化
    ("HN_Hunan", "CHN_HN_Xiangtan.577730_TMYx.zip"),          # 湘潭
    ("HN_Hunan", "CHN_HN_Sangzhi.575540_TMYx.zip"),           # 张家界(桑植)

    # === 广东 GD ===
    ("GD_Guangdong", "CHN_GD_Shenzhen.594930_TMYx.zip"),     # 深圳
    ("GD_Guangdong", "CHN_GD_Zhanjiang.596580_TMYx.zip"),    # 湛江
    ("GD_Guangdong", "CHN_GD_Zhaoqing-Gaoyao.592780_TMYx.zip"), # 肇庆
    ("GD_Guangdong", "CHN_GD_Huiyang.592980_TMYx.zip"),      # 惠州(惠阳)
    ("GD_Guangdong", "CHN_GD_Lianzhou.590720_TMYx.zip"),     # 清远(连州)
    ("GD_Guangdong", "CHN_GD_Xinyi.594560_TMYx.zip"),        # 茂名(信宜)
    ("GD_Guangdong", "CHN_GD_Huilai.593170_TMYx.zip"),       # 揭阳(惠来)
    ("GD_Guangdong", "CHN_GD_Nanxiong.579960_CSWD.zip"),     # 韶关北部补充

    # === 广西 GX ===
    ("GX_Guangxi_ZHuang", "CHN_GX_Liuzhou.590460_TMYx.zip"), # 柳州
    ("GX_Guangxi_ZHuang", "CHN_GX_Beihai.596440_TMYx.zip"),  # 北海
    ("GX_Guangxi_ZHuang", "CHN_GX_Longzhou.594170_TMYx.zip"),# 崇左(龙州)
    ("GX_Guangxi_ZHuang", "CHN_GX_Bobai.594460_TMYx.zip"),   # 玉林(博白)
    ("GX_Guangxi_ZHuang", "CHN_GX_Hexian-Babu.590650_TMYx.zip"), # 贺州

    # === 海南 HI ===
    ("HI_Hainan", "CHN_HI_Sanya.599480_TMYx.zip"),           # 三亚
    ("HI_Hainan", "CHN_HI_Danxian.598450_TMYx.zip"),         # 儋州(儋县)
    ("HI_Hainan", "CHN_HI_Dongfang.598380_CSWD.zip"),        # 东方
    ("HI_Hainan", "CHN_HI_Qionghai.598550_CSWD.zip"),        # 琼海

    # === 四川 SC ===
    ("SC_Sichuan", "CHN_SC_Ya-an.562870_TMYx.zip"),           # 雅安
    ("SC_Sichuan", "CHN_SC_Dachuan.573280_TMYx.zip"),         # 达州(达川)
    ("SC_Sichuan", "CHN_SC_Bazhong.573130_TMYx.zip"),         # 巴中
    ("SC_Sichuan", "CHN_SC_Suining.574050_TMYx.zip"),         # 遂宁

    # === 贵州 GZ ===
    ("GZ_Guizhou", "CHN_GZ_Anshun.578060_TMYx.zip"),         # 安顺
    ("GZ_Guizhou", "CHN_GZ_Sinan.577310_TMYx.zip"),           # 铜仁(思南)
    ("GZ_Guizhou", "CHN_GZ_Xingren.579020_TMYx.zip"),         # 黔西南(兴仁)
    ("GZ_Guizhou", "CHN_GZ_Sansui.578320_TMYx.zip"),          # 黔东南(三穗)
    ("GZ_Guizhou", "CHN_GZ_Dushan.579220_TMYx.zip"),          # 黔南(独山)

    # === 云南 YN ===
    ("YN_Yunnan", "CHN_YN_Zhaotong.565860_TMYx.zip"),        # 昭通
    ("YN_Yunnan", "CHN_YN_Lijiang.566510_CSWD.zip"),          # 丽江
    ("YN_Yunnan", "CHN_YN_Lincang.569510_CSWD.zip"),          # 临沧
    ("YN_Yunnan", "CHN_YN_Dali.567510_TMYx.zip"),             # 大理
    ("YN_Yunnan", "CHN_YN_Zhanyi.567860_TMYx.zip"),           # 曲靖(沾益)
    ("YN_Yunnan", "CHN_YN_Yuxi.568750_TMYx.zip"),             # 玉溪
    ("YN_Yunnan", "CHN_YN_Honghe-Mengzi.569850_TMYx.zip"),   # 红河(蒙自)
    ("YN_Yunnan", "CHN_YN_Wenshan.569940_TMYx.zip"),          # 文山
    ("YN_Yunnan", "CHN_YN_Xishuangbanna-Jinghong.569590_TMYx.zip"), # 西双版纳
    ("YN_Yunnan", "CHN_YN_Ruili.568380_TMYx.zip"),            # 德宏(瑞丽)

    # === 西藏 XZ (TMYx 文件在 XJ 文件夹中！) ===
    ("XJ_Xinjiang_Uyghur", "CHN_XJ_Nagqu.552990_TMYx.zip"),  # 那曲
    ("XJ_Xinjiang_Uyghur", "CHN_XJ_Xigaze.555780_TMYx.zip"), # 日喀则
    ("XJ_Xinjiang_Uyghur", "CHN_XJ_Nedong.555980_TMYx.zip"), # 山南(乃东)
    ("XJ_Xinjiang_Uyghur", "CHN_XJ_Ngari.552280_TMYx.zip"),  # 阿里

    # === 新疆 XJ (TMYx 文件在 XZ 文件夹中！) ===
    ("XZ_Tibet", "CHN_XZ_Korla.516560_TMYx.zip"),            # 巴音郭楞(库尔勒)
    ("XZ_Tibet", "CHN_XZ_Altay.AP.510760_TMYx.zip"),         # 阿勒泰
    ("XZ_Tibet", "CHN_XZ_Bortala.513300_TMYx.zip"),           # 博尔塔拉

    # === 陕西 SN ===
    ("SN_Shaanxi", "CHN_SN_Baoji.570160_TMYx.zip"),          # 宝鸡
    ("SN_Shaanxi", "CHN_SN_Tongchuan.539470_TMYx.zip"),      # 铜川

    # === 甘肃 GS ===
    ("GS_Gansu", "CHN_GS_Zhangye.526520_TMYx.zip"),          # 张掖
    ("GS_Gansu", "CHN_GS_Longnan-Wudu.560960_TMYx.zip"),     # 陇南(武都)

    # === 青海 QH ===
    ("QH_Qinghai", "CHN_QH_Minhe.528760_CSWD.zip"),          # 海东(民和)

    # === 宁夏 NX ===
    ("NX_Ningxia_Hui", "CHN_NX_Zhongning.537050_TMYx.zip"),  # 中卫(中宁)
]


def download_and_extract(province_folder: str, zip_filename: str) -> bool:
    """下载 ZIP 并解压 EPW 文件到 WEATHER_DIR。"""
    # 检查是否已有同名 EPW
    epw_stem = zip_filename.replace(".zip", "")
    existing = list(WEATHER_DIR.glob(f"{epw_stem}.epw"))
    if existing:
        print(f"  [SKIP] {epw_stem}.epw already exists")
        return True

    url = f"{BASE_URL}/{province_folder}/{zip_filename}"
    print(f"  [GET]  {url}")

    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={"User-Agent": "HVAC-Sim/1.0"})
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            data = resp.read()
    except Exception as e:
        print(f"  [FAIL] Download error: {e}")
        return False

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            epw_names = [n for n in zf.namelist() if n.lower().endswith(".epw")]
            if not epw_names:
                print(f"  [FAIL] No .epw file found in zip")
                return False
            for name in epw_names:
                target = WEATHER_DIR / Path(name).name
                target.write_bytes(zf.read(name))
                print(f"  [OK]   → {target.name}")
        return True
    except Exception as e:
        print(f"  [FAIL] Extract error: {e}")
        return False


def main() -> None:
    WEATHER_DIR.mkdir(parents=True, exist_ok=True)
    total = len(DOWNLOADS)
    ok = 0
    fail = 0

    print(f"=== EPW Download: {total} files from climate.onebuilding.org ===\n")

    for i, (folder, zipname) in enumerate(DOWNLOADS, 1):
        print(f"[{i}/{total}] {zipname}")
        if download_and_extract(folder, zipname):
            ok += 1
        else:
            fail += 1

    print(f"\n=== Done: {ok} succeeded, {fail} failed, {total} total ===")
    if fail > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
