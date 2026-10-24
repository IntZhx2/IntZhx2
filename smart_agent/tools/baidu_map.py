"""
百度地图 WebService API 客户端 (Baidu Maps API Client)
提供经纬度地理编码 (Geocoding)、全国跨城/同城路线规划 (DirectionLite) 及 POI 深度检索 (Place API)。
凭据从环境或本地配置自动读取；兼容的旧版 XOR 混淆格式不提供安全存储。
"""

import os
import re
import json
import time
import threading
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple
from smart_agent.config import BAIDU_MAPS_AK_ENV, ENCRYPTED_BAIDU_AK, MAPS_CONFIG_FILE
from smart_agent.utils.security import decrypt_token

# 进程内地理编码与 POI 高速缓存（避免重复请求消耗 QPS 与配额）
_GEOCODE_CACHE: Dict[str, Tuple[float, float]] = {}
_POI_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_REQUEST_TIME: Optional[float] = None
_REQUEST_LOCK = threading.Lock()


def _rate_limit_pace(min_interval: float = 0.35):
    """串行分配进程内请求时隙，以单调时钟保持最小间隔。"""
    global _LAST_REQUEST_TIME
    with _REQUEST_LOCK:
        now = time.monotonic()
        if _LAST_REQUEST_TIME is not None:
            deadline = _LAST_REQUEST_TIME + min_interval
            remaining = deadline - now
            while remaining > 0:
                time.sleep(remaining)
                now = time.monotonic()
                remaining = deadline - now
        _LAST_REQUEST_TIME = now


def get_baidu_ak() -> str:
    """环境优先，再自动读取本地 AK；不请求网络，也不在错误中输出凭据。"""
    env_ak = os.environ.get("BAIDU_MAPS_AK", "").strip() or BAIDU_MAPS_AK_ENV.strip()
    if env_ak:
        return env_ak
    if ENCRYPTED_BAIDU_AK:
        decrypted = decrypt_token(ENCRYPTED_BAIDU_AK)
        if decrypted:
            return decrypted
    try:
        # 有界读取，损坏/缺失配置保持未配置状态，避免影响其他工具启动。
        with MAPS_CONFIG_FILE.open("r", encoding="utf-8") as stream:
            raw = stream.read(16385)
        if len(raw) > 16384:
            return ""
        data = json.loads(raw)
        value = data.get("baidu_maps_ak") if isinstance(data, dict) else None
        if isinstance(value, str):
            value = value.strip()
            if value and len(value) <= 1024 and not any(char.isspace() for char in value):
                return value
    except (OSError, ValueError, RecursionError):
        pass
    return ""


class BaiduMapClient:
    """百度地图 WebService API 客户端封装"""

    BASE_URL = "https://api.map.baidu.com"

    def __init__(self, ak: Optional[str] = None):
        self.ak = (ak if ak is not None else get_baidu_ak()).strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.ak)

    def _request(self, endpoint: str, params: Dict[str, str], timeout: int = 6) -> Tuple[bool, Dict[str, Any], str]:
        """发起 HTTP GET 请求并解析 JSON 响应"""
        if not self.is_configured:
            return False, {}, "百度地图 AK 未配置或解密失败"

        _rate_limit_pace(0.35)
        params["ak"] = self.ak
        params["output"] = "json"
        url = f"{self.BASE_URL}{endpoint}?{urllib.parse.urlencode(params)}"

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "TravelAgent-BaiduMapClient/1.0"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            status = data.get("status", -1)
            if status == 0:
                return True, data, ""

            # 百度地图错误码细分友善提示
            error_msgs = {
                1: "百度地图内部服务错误",
                2: "请求参数非法或缺失",
                200: "百度地图 AK 不存在或非法，请检查密钥是否正确",
                210: "百度地图 AK 启用了 IP 白名单校验，当前请求 IP 未在白名单中",
                240: "服务未授权或未开通 WebService API 权限（APP 服务被禁用，请在百度控制台将 AK 设置为「服务端」类型并勾选对应接口）",
                301: "百度地图每日免费调用配额已用尽",
                302: "天级调用并发超限，请稍后重试",
            }
            msg = error_msgs.get(status, f"百度地图接口错误 (代码: {status}, 信息: {data.get('message', '未知')})")
            return False, data, msg

        except urllib.error.URLError as e:
            return False, {}, f"网络连接异常: {e.reason}"
        except Exception as e:
            return False, {}, f"请求解析异常: {str(e)}"

    def geocode(self, address: str, city: str = "") -> Tuple[Optional[Tuple[float, float]], str]:
        """
        地址编码：将地址名称转换为经纬度坐标 (lat, lng)
        """
        if not self.is_configured:
            return None, "未配置百度地图 AK"
        cache_key = f"{city}:{address}".strip()
        if cache_key in _GEOCODE_CACHE:
            return _GEOCODE_CACHE[cache_key], ""

        params = {"address": address}
        if city:
            params["city"] = city

        ok, data, err = self._request("/geocoding/v3/", params)
        if not ok:
            return None, err

        result = data.get("result", {})
        loc = result.get("location")
        if loc and "lat" in loc and "lng" in loc:
            coords = (float(loc["lat"]), float(loc["lng"]))
            _GEOCODE_CACHE[cache_key] = coords
            return coords, ""
        return None, f"未能在地图中定位地址 '{address}'"

    def route_plan(
        self,
        city: str,
        origin: str,
        destination: str,
        transit_mode: str = "",
    ) -> Tuple[bool, Optional[Dict[str, str]], str]:
        """
        全国/同城路线规划 (DirectionLite API)
        transit_mode: metro_bus (公交地铁), taxi/self_drive (驾车/打车), walk (步行)
        """
        for field, value in (("city", city), ("origin", origin), ("destination", destination)):
            if not isinstance(value, str) or not value.strip():
                return False, None, f"错误: {field} 必须为非空字符串"
        if not isinstance(transit_mode, str) or transit_mode not in ("metro_bus", "taxi", "self_drive", "walk"):
            return False, None, "错误: transit_mode 未配置或无效，须指定 metro_bus、taxi、self_drive 或 walk"
        city, origin, destination = city.strip(), origin.strip(), destination.strip()
        if not self.is_configured:
            return False, None, "未配置百度地图 AK"

        # 1. 地理编码起终点
        orig_coords, orig_err = self.geocode(origin, city)
        if not orig_coords:
            return False, None, orig_err or f"百度地理编码未能识别起点: '{origin}'"

        dest_coords, dest_err = self.geocode(destination, city)
        if not dest_coords:
            return False, None, dest_err or f"百度地理编码未能识别终点: '{destination}'"

        orig_str = f"{orig_coords[0]},{orig_coords[1]}"
        dest_str = f"{dest_coords[0]},{dest_coords[1]}"

        # 2. 根据出行方式调用对应路线规划接口
        if transit_mode == "metro_bus":
            ok, data, err = self._request(
                "/directionlite/v1/transit",
                {"origin": orig_str, "destination": dest_str},
            )
            if not ok:
                return False, None, err

            routes = data.get("result", {}).get("routes", [])
            if not routes:
                return False, None, f"未能检索到从 '{origin}' 到 '{destination}' 的公共交通换乘方案"

            best = routes[0]
            duration_min = round(best.get("duration", 0) / 60)
            cost_val = best.get("price", 0)
            cost_str = f"{cost_val} 元 / 人" if cost_val else "约 2~7 元 (以实际购票为准)"

            # 提取线路换乘关键节点与乘车指引
            steps_desc = []
            for step_group in best.get("steps", []):
                for step in step_group:
                    vehicle = step.get("vehicle_info") or {}
                    v_name = vehicle.get("detail", {}).get("name") if isinstance(vehicle, dict) else ""
                    raw_instr = step.get("instructions") or step.get("instruction") or (f"搭乘【{v_name}】" if v_name else "")
                    clean_instr = re.sub(r"<[^>]+>", "", raw_instr).strip()
                    if clean_instr:
                        steps_desc.append(clean_instr)

            # 优先筛选乘车、换乘线路，去除首尾无关痛痒的小距离步行
            ride_steps = [s for s in steps_desc if ("乘" in s or "换乘" in s or "线" in s or "搭乘" in s)]
            display_steps = ride_steps if ride_steps else steps_desc[:5]
            route_summary = " ➔ ".join(display_steps[:5]) if display_steps else "按照地铁/公交站内导向指引乘车"

            return True, {
                "duration": f"约 {duration_min} 分钟",
                "cost": cost_str,
                "route": route_summary,
                "tip": "高峰期换乘客流密集，请预留充裕候车进站时间。",
            }, ""

        elif transit_mode in ("taxi", "self_drive"):
            ok, data, err = self._request(
                "/directionlite/v1/driving",
                {"origin": orig_str, "destination": dest_str},
            )
            if not ok:
                return False, None, err

            routes = data.get("result", {}).get("routes", [])
            if not routes:
                return False, None, f"未能检索到从 '{origin}' 到 '{destination}' 的驾车方案"

            best = routes[0]
            duration_min = round(best.get("duration", 0) / 60)
            distance_km = round(best.get("distance", 0) / 1000, 1)

            if transit_mode == "taxi":
                # 估算打车费用 (起步 12 元/3km，超出部分约 2.6 元/km)
                est_taxi = 12 + max(0, distance_km - 3) * 2.6
                cost_str = f"约 {round(est_taxi)}~{round(est_taxi * 1.25)} 元 (网约车/出租车)"
            else:
                cost_str = f"油费/电费约 {round(distance_km * 0.7)} 元 (全程约 {distance_km} 公里)"

            # 提取主要路段行驶指引
            driving_steps = []
            for step in best.get("steps", []):
                raw_instr = step.get("instructions") or step.get("instruction") or ""
                clean_instr = re.sub(r"<[^>]+>", "", raw_instr).strip()
                if clean_instr and any(k in clean_instr for k in ["路", "高速", "大道", "高架", "快速路", "桥"]):
                    driving_steps.append(clean_instr)

            route_summary = " ➔ ".join(driving_steps[:4]) if driving_steps else f"沿主干道及城市快速路行驶，全程约 {distance_km} 公里"

            return True, {
                "duration": f"约 {duration_min} 分钟 (全程约 {distance_km} km)",
                "cost": cost_str,
                "route": route_summary,
                "tip": "早晚高峰主干道通行车流较大，建议提前留意实时导航避堵路线。",
            }, ""

        elif transit_mode == "walk":
            ok, data, err = self._request(
                "/directionlite/v1/walking",
                {"origin": orig_str, "destination": dest_str},
            )
            if not ok:
                return False, None, err

            routes = data.get("result", {}).get("routes", [])
            if not routes:
                return False, None, f"未能检索到从 '{origin}' 到 '{destination}' 的步行方案"

            best = routes[0]
            duration_min = round(best.get("duration", 0) / 60)
            distance_km = round(best.get("distance", 0) / 1000, 1)

            return True, {
                "duration": f"约 {duration_min} 分钟 (步行约 {distance_km} km)",
                "cost": "0 元 (绿色徒步)",
                "route": f"沿人行道及景观步道穿行，全程约 {distance_km} 公里",
                "tip": "长距离步行建议穿舒适运动鞋，晴雨天注意防晒与补水。",
            }, ""

    def search_place(self, attraction_name: str, city: str = "") -> Tuple[Optional[Dict[str, Any]], str]:
        """
        地点详情检索 (Place API POI 深度搜索)
        获取景点的真实地址、星级评分、开放营业时间、标签与咨询电话
        """
        if not self.is_configured:
            return None, "未配置百度地图 AK"

        cache_key = f"{city}:{attraction_name}".strip()
        if cache_key in _POI_CACHE:
            return _POI_CACHE[cache_key], ""

        params = {
            "query": attraction_name,
            "scope": "2",  # 详细信息模式
            "page_size": "1",
        }
        if city:
            params["region"] = city

        ok, data, err = self._request("/place/v2/search", params)
        if not ok:
            return None, err

        results = data.get("results", [])
        if not results:
            return None, f"未检索到与 '{attraction_name}' 匹配的地点"

        poi = results[0]
        detail = poi.get("detail_info", {})

        res_dict = {
            "name": poi.get("name", attraction_name),
            "address": poi.get("address", "详见地图标注"),
            "telephone": poi.get("telephone", "暂无官方公开电话"),
            "tag": detail.get("tag", "热门文旅地标"),
            "rating": detail.get("overall_rating") or detail.get("rating") or "4.6",
            "shop_hours": detail.get("shop_hours") or "以景区现场开放时间为准",
            "price": detail.get("price"),
        }
        _POI_CACHE[cache_key] = res_dict
        return res_dict, ""

    def get_weather(self, city: str) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        全国城市实时气象与出行生活指数检索 (Baidu Maps Weather API)
        """
        if not self.is_configured:
            return None, "未配置百度地图 AK"

        city_clean = city.replace("市", "").replace("特别行政区", "").strip()
        common_adcodes = {
            "广州": "440100", "深圳": "440300", "北京": "110100", "上海": "310100",
            "杭州": "330100", "成都": "510100", "重庆": "500100", "武汉": "420100",
            "南京": "320100", "西安": "610100", "珠海": "440400", "佛山": "440600",
            "东莞": "441900", "厦门": "350200", "长沙": "430100", "天津": "120100",
            "苏州": "320500", "青岛": "370200", "昆明": "530100", "三亚": "460200",
            "海口": "460100", "福州": "350100", "合肥": "340100", "南昌": "360100",
            "郑州": "410100", "济南": "370100", "沈阳": "210100", "大连": "210200",
            "哈尔滨": "230100", "长春": "220100", "贵阳": "520100", "南宁": "450100",
        }
        adcode = common_adcodes.get(city_clean)

        if not adcode:
            coords, _ = self.geocode(city, city)
            if coords:
                ok_rev, rev_data, _ = self._request(
                    "/reverse_geocoding/v3/",
                    {"location": f"{coords[0]},{coords[1]}"},
                )
                if ok_rev:
                    adcode = rev_data.get("result", {}).get("addressComponent", {}).get("adcode")

        if not adcode:
            return None, f"未匹配到城市 '{city}' 的行政区划代码"

        ok, data, err = self._request(
            "/weather/v1/",
            {"district_id": str(adcode), "data_type": "all"},
        )
        if not ok:
            return None, err

        result = data.get("result", {})
        now = result.get("now", {})
        if not now:
            return None, "百度气象接口未返回当前实时数据"

        indexes = result.get("indexes", [])
        tips = []
        for idx in indexes:
            iname = idx.get("name", "")
            idetail = idx.get("detail", "") or idx.get("brief", "")
            if any(k in iname for k in ("穿衣", "紫外线", "感冒", "舒适度")):
                tips.append(f"- 👔 {iname}: {idetail}")

        return {
            "city": city,
            "text": now.get("text", "晴"),
            "temp": now.get("temp", "--"),
            "feels_like": now.get("feels_like", "--"),
            "rh": now.get("rh", "--"),
            "wind_dir": now.get("wind_dir", "微风"),
            "wind_class": now.get("wind_class", "1~2级"),
            "aqi": now.get("aqi", "--"),
            "tips": "\n".join(tips) if tips else "",
        }, ""
