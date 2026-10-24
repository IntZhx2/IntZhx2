"""
SmartAgent 核心模块基准性能与开销剖析 (Benchmark & Profiling)
测试内容：
1. MCP JSON-RPC 2.0 序列化与反序列化吞吐量
2. 旧版可逆混淆转换吞吐量（不代表密码安全）
3. 百度地图客户端本地高速缓存 (Cache Hit) 检索吞吐量
4. 上下文滑动窗口修剪与 compact_last_turn 压缩性能
"""

import time
import json
import sys
from pathlib import Path

# 确保项目根路径进入 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from smart_agent.mcp.protocol import JSONRPCRequest, JSONRPCResponse
from smart_agent.utils.security import encrypt_token, decrypt_token
from smart_agent.tools.baidu_map import BaiduMapClient, _GEOCODE_CACHE, _POI_CACHE
from smart_agent.agent.memory import ConversationMemory


def benchmark_mcp_protocol(iterations: int = 10000):
    start = time.perf_counter()
    sample_dict = {
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {"name": "traffic_transit", "arguments": {"city": "广州", "origin": "沙面", "destination": "广州塔"}},
        "id": "bench-12345"
    }
    for _ in range(iterations):
        req = JSONRPCRequest.from_dict(sample_dict)
        _ = req.to_dict()
    elapsed = time.perf_counter() - start
    qps = iterations / elapsed
    print(f"✅ [MCP 协议序列化] {iterations} 次迭代: 耗时 {elapsed:.4f}s | 吞吐量: {qps:,.0f} ops/s")


def benchmark_key_vault(iterations: int = 10000):
    start = time.perf_counter()
    raw_key = "sk-bench-key-test-security-0123456789abcdef"
    cipher = encrypt_token(raw_key)
    for _ in range(iterations):
        decrypted = decrypt_token(cipher)
        assert decrypted == raw_key
    elapsed = time.perf_counter() - start
    qps = iterations / elapsed
    print(f"✅ [旧版混淆转换] {iterations} 次迭代: 耗时 {elapsed:.4f}s | 吞吐量: {qps:,.0f} ops/s")


def benchmark_cache_speed(iterations: int = 10000):
    # 预热缓存
    _GEOCODE_CACHE["广州"] = (23.1291, 113.2644)
    start = time.perf_counter()
    for _ in range(iterations):
        res = _GEOCODE_CACHE.get("广州")
        assert res is not None
    elapsed = time.perf_counter() - start
    qps = iterations / elapsed
    print(f"✅ [百度地图内存缓存检索] {iterations} 次迭代: 耗时 {elapsed:.4f}s | 吞吐量: {qps:,.0f} ops/s")


def benchmark_memory_compact(iterations: int = 1000):
    start = time.perf_counter()
    for _ in range(iterations):
        mem = ConversationMemory(session_id="bench_mem")
        mem.add_user_message("用户提问广州行程规划")
        mem.add_assistant_message("思考中", tool_calls=[{"id": "c1", "type": "function"}])
        mem.add_tool_message("c1", "weather_query", "晴朗 28℃")
        mem.compact_last_turn("用户提问广州行程规划", "广州2日游完整一条龙攻略生成完毕。")
        msgs = mem.get_messages()
        assert len(msgs) == 3
    elapsed = time.perf_counter() - start
    qps = iterations / elapsed
    print(f"✅ [上下文自愈压缩] {iterations} 次迭代: 耗时 {elapsed:.4f}s | 吞吐量: {qps:,.0f} ops/s")


if __name__ == "__main__":
    print("=" * 70)
    print("🚀 开始执行 SmartAgent 核心组件微基准性能测试...")
    print("=" * 70)
    benchmark_mcp_protocol(10000)
    benchmark_key_vault(10000)
    benchmark_cache_speed(10000)
    benchmark_memory_compact(1000)
    print("=" * 70)
    print("🎉 基准测试全部执行完毕！")
