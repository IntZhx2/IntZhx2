"""工具文件边界、数据诚实性和并发限速回归测试；禁止真实外部请求。"""

from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import runpy
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from smart_agent import config
from smart_agent.tools import baidu_map
from smart_agent.tools.attraction_tool import AttractionInfoTool
from smart_agent.tools.itinerary_tool import ItineraryListTool, ItinerarySaveTool
from smart_agent.tools.traffic_tool import TrafficTransitTool
from smart_agent.tools.weather_tool import WeatherQueryTool
from smart_agent.utils.security import encrypt_token, decrypt_token


class IsolatedToolsTestCase(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("urllib.request.urlopen", side_effect=AssertionError("禁止外部请求"))
        network = patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(network.assert_not_called)
        patcher = mock.patch("smart_agent.tools.baidu_map.get_baidu_ak", return_value="")
        patcher.start()
        self.addCleanup(patcher.stop)


class TestItinerarySafety(IsolatedToolsTestCase):
    def setUp(self):
        super().setUp()
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        patcher = mock.patch("smart_agent.tools.itinerary_tool.WORKSPACE_DIR", self.workspace)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tool = ItinerarySaveTool()

    def save(self, filename, content="original"):
        return self.tool.execute(title="行程", content=content, filename=filename)

    def test_rejects_non_basename_paths(self):
        invalid = ["../escape.md", "sub/travel.md", "./travel.md", "/tmp/escape.md",
                   "..\\escape.md", "C:\\escape.md", "C:escape.md", "\\\\host\\share.md",
                   ".", "..", "   ", "bad\x00.md", str(self.root / "escape.md")]
        for filename in invalid:
            with self.subTest(filename=filename):
                self.assertTrue(self.save(filename).is_error)
        self.assertEqual(list(self.workspace.iterdir()), [])
        self.assertFalse((self.root / "escape.md").exists())

    def test_rejects_non_string_inputs(self):
        for field in ("title", "content", "filename"):
            for value in (None, 123, [], {}):
                with self.subTest(field=field, value=value):
                    args = {"title": "行程", "content": "正文", "filename": "trip.md"}
                    args[field] = value
                    self.assertTrue(self.tool.execute(**args).is_error)

    def test_exclusive_save_preserves_existing_file(self):
        self.assertFalse(self.save("行程.txt").is_error)
        before = (self.workspace / "行程.txt").read_bytes()
        result = self.save("行程.txt", "replacement")
        self.assertTrue(result.is_error)
        self.assertIn("已存在", result.get_text())
        self.assertEqual((self.workspace / "行程.txt").read_bytes(), before)

    def test_rejects_live_and_dangling_symlinks(self):
        target = self.root / "outside.md"
        target.touch()
        for name, destination in (("live.md", target), ("dangling.md", self.root / "missing.md")):
            with self.subTest(name=name):
                (self.workspace / name).symlink_to(destination)
                self.assertTrue(self.save(name).is_error)
                self.assertTrue((self.workspace / name).is_symlink())
        self.assertEqual(target.read_bytes(), b"")
        self.assertFalse((self.root / "missing.md").exists())

    def test_rejects_symlink_workspace(self):
        linked = self.root / "linked"
        linked.symlink_to(self.workspace, target_is_directory=True)
        with mock.patch("smart_agent.tools.itinerary_tool.WORKSPACE_DIR", linked):
            self.assertTrue(self.save("escape.md").is_error)
        self.assertFalse((self.workspace / "escape.md").exists())

    def test_generated_name_collision_is_explicit(self):
        with mock.patch("smart_agent.tools.itinerary_tool.time.strftime", return_value="fixed"):
            first = self.tool.execute(title="../行程", content="first")
            second = self.tool.execute(title="../行程", content="second")
        self.assertFalse(first.is_error)
        self.assertTrue(second.is_error)
        files = list(self.workspace.iterdir())
        self.assertEqual(len(files), 1)
        self.assertIn("first", files[0].read_text(encoding="utf-8"))

    def test_parallel_saves_have_only_one_winner(self):
        workers = 8
        barrier = threading.Barrier(workers)

        def save(index):
            barrier.wait(timeout=5)
            return index, self.save("shared.md", f"payload-{index}")

        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(save, range(workers)))
        winners = [index for index, result in results if not result.is_error]
        self.assertEqual(len(winners), 1)
        text = (self.workspace / "shared.md").read_text(encoding="utf-8")
        self.assertIn(f"payload-{winners[0]}", text)
        self.assertEqual(sum(f"payload-{i}" in text for i in range(workers)), 1)

    def test_extension_and_listing_ignore_symlinks(self):
        self.assertFalse(self.save("trip").is_error)
        (self.workspace / "linked.md").symlink_to(self.workspace / "trip.md")
        result = ItineraryListTool().execute()
        self.assertFalse(result.is_error)
        self.assertIn("trip.md", result.get_text())
        self.assertNotIn("linked.md", result.get_text())


class TestTrafficSafety(IsolatedToolsTestCase):
    def setUp(self):
        super().setUp()
        self.tool = TrafficTransitTool()

    def test_missing_and_invalid_inputs_do_not_call_map(self):
        valid = {"city": "广州", "origin": "广州南站", "destination": "广州塔", "transit_mode": "metro_bus"}
        with mock.patch.object(self.tool.baidu_client, "route_plan") as route:
            for field in valid:
                args = dict(valid)
                del args[field]
                with self.subTest(missing=field):
                    result = self.tool.execute(**args)
                    self.assertTrue(result.is_error)
                    self.assertIn(field, result.get_text())
                for value in (None, "", " ", 1, [], {}):
                    with self.subTest(field=field, value=value):
                        self.assertTrue(self.tool.execute(**{**valid, field: value}).is_error)
            self.assertTrue(self.tool.execute(**{**valid, "transit_mode": "fly"}).is_error)
            route.assert_not_called()
        self.assertIn("transit_mode", self.tool.input_schema["required"])
        self.assertNotIn("default", self.tool.input_schema["properties"]["transit_mode"])

    def test_known_routes_never_fall_back_without_configuration(self):
        for mode in ("metro_bus", "taxi", "self_drive", "walk"):
            for city in ("广州", "北京"):
                with self.subTest(mode=mode, city=city):
                    result = self.tool.execute(city=city, origin="沙面", destination="广州塔", transit_mode=mode)
                    self.assertTrue(result.is_error)
                    self.assertIn("未配置", result.get_text())
                    self.assertNotIn("本地已核验", result.get_text())

    def test_api_errors_are_preserved_without_local_fallback(self):
        self.tool.baidu_client.ak = "test-ak"
        for reason in ("网络超时", "配额已用尽", "未找到路线", ""):
            with self.subTest(reason=reason), mock.patch.object(
                self.tool.baidu_client, "route_plan", return_value=(False, None, reason)
            ):
                result = self.tool.execute(city="广州", origin="广州南站", destination="广州塔", transit_mode="metro_bus")
                self.assertTrue(result.is_error)
                self.assertIn(reason or "接口未返回可用路线", result.get_text())
                self.assertNotIn("约 35 分钟", result.get_text())

    def test_valid_modes_forward_exactly_and_use_only_mock_results(self):
        self.tool.baidu_client.ak = "test-ak"
        details = {"duration": "mock duration", "cost": "mock cost", "route": "mock route", "tip": "mock tip"}
        for mode in ("metro_bus", "taxi", "self_drive", "walk"):
            with self.subTest(mode=mode), mock.patch.object(
                self.tool.baidu_client, "route_plan", return_value=(True, details, "")
            ) as route:
                result = self.tool.execute(city=" 广州 ", origin=" 起点 ", destination=" 终点 ", transit_mode=mode)
                self.assertFalse(result.is_error)
                self.assertIn("mock route", result.get_text())
                route.assert_called_once_with("广州", "起点", "终点", mode)

    def test_map_client_rejects_invalid_mode_and_city_before_geocoding(self):
        client = baidu_map.BaiduMapClient(ak="test-ak")
        with mock.patch.object(client, "geocode") as geocode:
            for mode in ("", "fly", None, [], {}):
                ok, details, err = client.route_plan("广州", "A", "B", mode)
                self.assertFalse(ok)
                self.assertIsNone(details)
                self.assertIn("transit_mode", err)
            self.assertFalse(client.route_plan("广州", "A", "B")[0])
            for city in ("", " ", None, [], {}):
                ok, _, err = client.route_plan(city, "A", "B", "walk")
                self.assertFalse(ok)
                self.assertIn("city", err)
            geocode.assert_not_called()


class TestAttractionSafety(IsolatedToolsTestCase):
    def test_exact_normalized_alias_and_city(self):
        tool = AttractionInfoTool()
        for name in ("广州塔", " 小蛮腰 ", "广　州 塔"):
            with self.subTest(name=name):
                result = tool.execute(city=" 广州市 ", attraction_name=name)
                self.assertFalse(result.is_error)
                self.assertIn("广州塔", result.get_text())
                self.assertIn("静态", result.get_text())
                self.assertIn("非实时", result.get_text())
                self.assertIn("官方最新公告", result.get_text())
                self.assertNotIn("本地已核验", result.get_text())
        self.assertFalse(tool.execute(city="广州", attraction_name="沙面岛").is_error)
        self.assertFalse(tool.execute(city="广州", attraction_name="北京路").is_error)

    def test_partial_and_wrong_city_never_match_local_entry(self):
        tool = AttractionInfoTool()
        for city, name in (("北京", "广州塔"), ("深圳", "沙面岛"), ("广州", "塔"),
                           ("广州", "北京"), ("广州", "广州塔附近酒店"), ("广州", "不是广州塔")):
            with self.subTest(city=city, name=name):
                self.assertTrue(tool.execute(city=city, attraction_name=name).is_error)

    def test_missing_city_and_name_are_errors(self):
        tool = AttractionInfoTool()
        self.assertTrue(tool.execute(attraction_name="广州塔").is_error)
        for value in (None, "", " ", [], {}):
            self.assertTrue(tool.execute(city=value, attraction_name="广州塔").is_error)
            self.assertTrue(tool.execute(city="广州", attraction_name=value).is_error)

    def test_wrong_city_uses_poi_service_instead_of_static_data(self):
        tool = AttractionInfoTool()
        tool.baidu_client.ak = "test-ak"
        with mock.patch.object(tool.baidu_client, "search_place", return_value=(None, "未检索到")) as search:
            result = tool.execute(city="北京", attraction_name="广州塔")
            self.assertTrue(result.is_error)
            search.assert_called_once_with("广州塔", "北京")


class TestWeatherSafety(IsolatedToolsTestCase):
    def test_aqi_labels_follow_values_including_missing_data(self):
        tool = WeatherQueryTool()
        tool.baidu_client.ak = "test-ak"
        weather = {"temp": 30, "feels_like": 31, "text": "阴", "rh": 80,
                   "wind_dir": "北", "wind_class": "2级"}
        cases = [(0, "优"), (50, "优"), (51, "良"), (100, "良"), (101, "轻度污染"),
                 (150, "轻度污染"), (151, "中度污染"), (200, "中度污染"),
                 (201, "重度污染"), (300, "重度污染"), (301, "严重污染"), (500, "严重污染"),
                 ("220", "重度污染"), (None, "未知"), ("--", "未知"), (-1, "未知"),
                 (501, "未知"), (float("nan"), "未知"), (float("inf"), "未知"), (True, "未知")]
        with mock.patch.object(tool, "_fetch_online") as fallback:
            for value, label in cases:
                with self.subTest(aqi=value), mock.patch.object(
                    tool.baidu_client, "get_weather", return_value=({**weather, "aqi": value}, "")
                ):
                    result = tool.execute(city="广州")
                    self.assertFalse(result.is_error)
                    self.assertIn(f"({label})", result.get_text())
                    self.assertNotIn("优/良", result.get_text())
            with mock.patch.object(tool.baidu_client, "get_weather", return_value=(weather, "")):
                self.assertIn("AQI -- (未知)", tool.execute(city="广州").get_text())
            fallback.assert_not_called()

    def test_baidu_failure_uses_mocked_weather_fallback(self):
        tool = WeatherQueryTool()
        tool.baidu_client.ak = "test-ak"
        with mock.patch.object(tool.baidu_client, "get_weather", return_value=(None, "超时")), mock.patch.object(
            tool, "_fetch_online", return_value="mock wttr weather"
        ) as fallback:
            result = tool.execute(city="广州")
            self.assertEqual(result.get_text(), "mock wttr weather")
            fallback.assert_called_once_with("广州")

    def test_wttr_transport_is_mocked(self):
        payload = {"current_condition": [{"temp_C": "28", "FeelsLikeC": "29", "humidity": "80",
                                           "weatherDesc": [{"value": "Cloudy"}]}]}
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
        with mock.patch("urllib.request.urlopen", return_value=response) as request:
            text = WeatherQueryTool()._fetch_online("广州")
            self.assertIn("28℃", text)
            self.assertIn("Cloudy", text)
            self.assertIn("wttr.in", request.call_args.args[0].full_url)


class TestMapPacingAndConfiguration(IsolatedToolsTestCase):
    def test_no_embedded_credential_defaults(self):
        with mock.patch.dict(os.environ):
            os.environ.pop("BAIDU_MAPS_AK", None)
            os.environ.pop("ENCRYPTED_BAIDU_AK", None)
            settings = runpy.run_path(config.__file__)
            self.assertEqual(settings["BAIDU_MAPS_AK_ENV"], "")
            self.assertEqual(settings["ENCRYPTED_BAIDU_AK"], "")

    def test_explicit_environment_and_legacy_compatibility(self):
        token = "test-only-ak"
        encoded = encrypt_token(token)
        self.assertEqual(decrypt_token(encoded), token)
        with mock.patch("smart_agent.tools.baidu_map.get_baidu_ak", wraps=original_get_baidu_ak):
            with mock.patch.dict(os.environ, {"BAIDU_MAPS_AK": " direct-ak "}), mock.patch.object(
                baidu_map, "ENCRYPTED_BAIDU_AK", encoded
            ):
                self.assertEqual(baidu_map.get_baidu_ak(), "direct-ak")
            with mock.patch.dict(os.environ, {"BAIDU_MAPS_AK": ""}), mock.patch.object(
                baidu_map, "BAIDU_MAPS_AK_ENV", ""
            ), mock.patch.object(baidu_map, "ENCRYPTED_BAIDU_AK", encoded):
                self.assertEqual(baidu_map.get_baidu_ak(), token)

    def test_concurrent_pacing_uses_monotonic_clock_and_lock(self):
        workers = 12
        interval = 0.35
        clock = [100.0]
        sleeps = []
        clock_lock = threading.Lock()
        barrier = threading.Barrier(workers)
        real_sleep = time.sleep

        def monotonic():
            with clock_lock:
                return clock[0]

        def sleep(delay):
            self.assertTrue(baidu_map._REQUEST_LOCK.locked())
            # 短暂让出执行权，让其他线程实际争用限速锁。
            real_sleep(0.001)
            with clock_lock:
                # 浮点残差可能小于当前时刻的精度；保证前进，并限制重试次数。
                # 限速实现回归时应明确失败，不能把整套测试挂在工作线程退出上。
                self.assertLess(len(sleeps), workers * 2, "假时钟等待未能收敛")
                self.assertGreater(delay, 0)
                clock[0] = math.nextafter(clock[0] + delay, math.inf)
                sleeps.append(delay)

        def pace(_):
            barrier.wait(timeout=5)
            baidu_map._rate_limit_pace(interval)

        fake_time = SimpleNamespace(
            monotonic=monotonic, sleep=sleep,
            time=mock.Mock(side_effect=AssertionError("不能使用系统时间")),
        )
        # 替换客户端的 time 引用，避免修改进程共享模块而影响 Barrier/测试运行器。
        with mock.patch.object(baidu_map, "_LAST_REQUEST_TIME", None), mock.patch.object(
            baidu_map, "_REQUEST_LOCK", threading.Lock()
        ), mock.patch.object(baidu_map, "time", fake_time):
            with ThreadPoolExecutor(max_workers=workers) as pool:
                list(pool.map(pace, range(workers)))
            self.assertAlmostEqual(baidu_map._LAST_REQUEST_TIME, 100 + interval * (workers - 1))
        self.assertEqual(len(sleeps), workers - 1)
        for delay in sleeps:
            self.assertAlmostEqual(delay, interval)

    def test_early_sleep_wakeup_rechecks_remaining_interval(self):
        fake_time = SimpleNamespace(
            monotonic=mock.Mock(side_effect=[10.1, 10.2, 10.35]), sleep=mock.Mock(),
        )
        with mock.patch.object(baidu_map, "_LAST_REQUEST_TIME", 10.0), mock.patch.object(
            baidu_map, "time", fake_time
        ):
            baidu_map._rate_limit_pace(0.35)
            self.assertEqual(fake_time.sleep.call_count, 2)
            self.assertAlmostEqual(fake_time.sleep.call_args_list[0].args[0], 0.25)
            self.assertAlmostEqual(fake_time.sleep.call_args_list[1].args[0], 0.15)


class TestLocalMapConfiguration(unittest.TestCase):
    """始终使用临时文件，不能读取开发者真实 AK 或访问地图接口。"""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "maps_config.json"
        patches = [
            mock.patch.object(baidu_map, "MAPS_CONFIG_FILE", self.path),
            mock.patch.object(baidu_map, "BAIDU_MAPS_AK_ENV", ""),
            mock.patch.object(baidu_map, "ENCRYPTED_BAIDU_AK", ""),
            mock.patch.dict(os.environ, {"BAIDU_MAPS_AK": ""}),
            mock.patch("urllib.request.urlopen", side_effect=AssertionError("禁止外部请求")),
        ]
        for patcher in patches:
            started = patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(started.assert_not_called)

    def write_config(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_local_key_is_used_by_default_client(self):
        self.write_config({"baidu_maps_ak": " local-test-ak "})
        self.assertEqual(baidu_map.get_baidu_ak(), "local-test-ak")
        self.assertEqual(baidu_map.BaiduMapClient().ak, "local-test-ak")

    def test_environment_overrides_local_without_opening_file(self):
        with mock.patch.dict(os.environ, {"BAIDU_MAPS_AK": "env-test-ak"}), mock.patch.object(
            Path, "open", side_effect=AssertionError("环境配置应优先")
        ):
            self.assertEqual(baidu_map.get_baidu_ak(), "env-test-ak")
        with mock.patch.object(baidu_map, "BAIDU_MAPS_AK_ENV", "startup-test-ak"):
            self.assertEqual(baidu_map.get_baidu_ak(), "startup-test-ak")

    def test_explicit_and_legacy_keys_keep_precedence(self):
        self.write_config({"baidu_maps_ak": "local-test-ak"})
        with mock.patch.object(baidu_map, "ENCRYPTED_BAIDU_AK", encrypt_token("legacy-test-ak")):
            self.assertEqual(baidu_map.get_baidu_ak(), "legacy-test-ak")
        self.assertEqual(baidu_map.BaiduMapClient(ak="explicit-test-ak").ak, "explicit-test-ak")

    def test_invalid_legacy_value_falls_back_to_local(self):
        self.write_config({"baidu_maps_ak": "local-test-ak"})
        with mock.patch.object(baidu_map, "ENCRYPTED_BAIDU_AK", "invalid"):
            self.assertEqual(baidu_map.get_baidu_ak(), "local-test-ak")

    def test_missing_unreadable_and_malformed_files_are_unconfigured(self):
        self.assertEqual(baidu_map.get_baidu_ak(), "")
        with mock.patch.object(Path, "open", side_effect=PermissionError("not readable")):
            self.assertEqual(baidu_map.get_baidu_ak(), "")
        for raw in ("{", "", "[" * 2000, '{"baidu_maps_ak": "' + "x" * 16384 + '"}'):
            with self.subTest(length=len(raw)):
                self.path.write_text(raw, encoding="utf-8")
                self.assertEqual(baidu_map.get_baidu_ak(), "")
        self.path.write_bytes(b"\xff")
        self.assertEqual(baidu_map.get_baidu_ak(), "")

    def test_invalid_shapes_and_values_are_unconfigured(self):
        for data in (None, [], "text", 42, {}, {"other": "value"}):
            with self.subTest(data=data):
                self.write_config(data)
                self.assertEqual(baidu_map.get_baidu_ak(), "")
        for value in (None, True, 12, [], {}, "", "  ", "a b", "a\nb", "x" * 1025):
            with self.subTest(value_type=type(value).__name__):
                self.write_config({"baidu_maps_ak": value})
                self.assertEqual(baidu_map.get_baidu_ak(), "")

    def test_configuration_is_reloaded_for_new_clients(self):
        self.write_config({"baidu_maps_ak": "first-test-ak"})
        first = baidu_map.BaiduMapClient()
        self.write_config({"baidu_maps_ak": "second-test-ak"})
        second = baidu_map.BaiduMapClient()
        self.assertEqual(first.ak, "first-test-ak")
        self.assertEqual(second.ak, "second-test-ak")


original_get_baidu_ak = baidu_map.get_baidu_ak


if __name__ == "__main__":
    unittest.main()
