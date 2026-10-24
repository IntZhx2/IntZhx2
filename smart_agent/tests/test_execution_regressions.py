"""Execution boundaries: active memory, rollback and the in-process MCP subset."""

from copy import deepcopy
import json
import unittest
from unittest.mock import Mock

from smart_agent.agent.core import SmartAgent
from smart_agent.agent.memory import ConversationMemory
from smart_agent.mcp.client import MCPClient
from smart_agent.mcp.protocol import ToolCallResult
from smart_agent.mcp.server import MCPServer
from smart_agent.tools.base import BaseTool, FunctionTool


def tool_call(call_id, arguments=None):
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": "echo",
            "arguments": json.dumps({"msg": call_id} if arguments is None else arguments),
        },
    }


class RecordingTool(BaseTool):
    name = "echo"
    description = "Record validated inputs without network or filesystem effects."
    input_schema = {
        "type": "object",
        "properties": {
            "msg": {"type": "string"},
            "mode": {"type": "string", "enum": ["walk", "taxi"]},
            "count": {"type": "integer"},
            "price": {"type": "number"},
            "enabled": {"type": "boolean"},
            "nullable": {"type": ["string", "null"]},
            "stops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
            "labels": {"type": "object", "additionalProperties": {"type": "string"}},
        },
        "required": ["msg"],
        "additionalProperties": False,
    }

    def __init__(self):
        self.calls = []

    def execute(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        return ToolCallResult.text("result:" + kwargs["msg"])


class TestExecutionMemoryRegressions(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer()
        self.tool = RecordingTool()
        self.server.register_tool(self.tool)
        self.client = MCPClient(self.server)

    def assert_tool_pairs(self, messages):
        pending = set()
        for message in messages:
            if message["role"] in ("assistant", "user"):
                self.assertFalse(pending, "missing results before next conversation message")
            if message.get("tool_calls"):
                pending.update(call["id"] for call in message["tool_calls"])
            if message["role"] == "tool":
                self.assertIn(message["tool_call_id"], pending)
                pending.remove(message["tool_call_id"])
        self.assertFalse(pending)

    def test_six_tool_rounds_preserve_original_and_all_results_for_synthesis(self):
        memory = ConversationMemory(window_size=4)
        memory.load_from_turns([{"user_prompt": "history", "assistant_response": "old answer"}])
        snapshots = []
        original = "周六15点到广州塔，只坐地铁，保留这个硬约束"

        def complete(messages, tools=None):
            snapshots.append(deepcopy(messages))
            self.assertIn({"role": "user", "content": original}, messages)
            self.assert_tool_pairs(messages[:-1] if tools is None else messages)
            round_number = len(snapshots)
            results = [m for m in messages if m["role"] == "tool"]
            self.assertEqual(len(results), min(round_number - 1, 6) * 2)
            if tools is None:
                self.assertEqual(round_number, 7)
                self.assertEqual(
                    [m["content"] for m in results],
                    [f"result:{i}-{j}" for i in range(1, 7) for j in range(2)],
                )
                return {"content": "最终攻略"}
            return {"content": "查询", "tool_calls": [
                tool_call(f"{round_number}-{j}") for j in range(2)
            ]}

        llm = Mock()
        llm.chat_completion.side_effect = complete
        result = SmartAgent(memory, self.client, llm, max_turns=6).run(original)
        self.assertEqual(result.answer, "最终攻略")
        self.assertEqual(len(self.tool.calls), 12)
        self.assertGreater(len(snapshots[-1]), memory.window_size + 1)
        self.assertEqual(memory.get_messages()[-2:], [
            {"role": "user", "content": original},
            {"role": "assistant", "content": "最终攻略"},
        ])
        self.assertTrue(all("tool_calls" not in m and m["role"] != "tool"
                            for m in memory.get_messages()))
        self.assertLessEqual(result.memory_length, memory.window_size + 1)

    def test_direct_memory_keeps_active_cycle_until_final_answer(self):
        memory = ConversationMemory(window_size=2)
        memory.add_user_message("original")
        for index in range(6):
            memory.add_assistant_message("", [tool_call(str(index))])
            memory.add_tool_message(str(index), "echo", str(index))
        self.assertEqual(len(memory.get_messages()), 14)
        memory.add_assistant_message("done")
        self.assertEqual(len(memory.get_messages()), 15)
        self.assert_tool_pairs(memory.get_messages())

    def test_trim_evicts_whole_historical_turns_and_keeps_tool_pairs(self):
        memory = ConversationMemory(window_size=7)
        for index in range(3):
            memory.add_user_message(f"user {index}")
            memory.add_assistant_message("", [tool_call(str(index))])
            memory.add_tool_message(str(index), "echo", "result")
            memory.add_assistant_message(f"answer {index}")
        messages = memory.get_messages()
        self.assertEqual([m["content"] for m in messages if m["role"] == "user"], ["user 2"])
        self.assertEqual(len(messages), 5)
        self.assert_tool_pairs(messages)

    def test_compaction_preserves_historical_tool_pairs(self):
        memory = ConversationMemory(window_size=20)
        memory.add_user_message("same input")
        memory.add_assistant_message("", [tool_call("historical")])
        memory.add_tool_message("historical", "echo", "historical result")
        memory.add_assistant_message("first answer")
        history = memory.export_messages()
        memory.begin_turn("same input")
        memory.add_assistant_message("", [tool_call("current")])
        memory.add_tool_message("current", "echo", "current result")
        memory.compact_last_turn("same input", "second answer")
        self.assertEqual(memory.export_messages()[:len(history)], history)
        self.assertEqual(memory.get_messages()[-2:], [
            {"role": "user", "content": "same input"},
            {"role": "assistant", "content": "second answer"},
        ])
        self.assert_tool_pairs(memory.get_messages())

    def test_failure_restores_exact_history_and_retry_has_no_partial_turn(self):
        for stage in ("schema", "first_llm", "after_tools", "synthesis"):
            with self.subTest(stage=stage):
                memory = ConversationMemory(window_size=2)
                memory.load_from_turns([{"user_prompt": "history", "assistant_response": "answer"}])
                before = memory.export_messages()
                llm = Mock()
                error = RuntimeError("injected failure")
                if stage == "first_llm":
                    llm.chat_completion.side_effect = error
                else:
                    llm.chat_completion.side_effect = [
                        {"content": "", "tool_calls": [tool_call("partial")]}, error,
                    ]
                client = Mock(wraps=self.client) if stage == "schema" else self.client
                if stage == "schema":
                    client.get_llm_tools_schema.side_effect = error
                agent = SmartAgent(memory, client, llm, max_turns=1 if stage == "synthesis" else 6)
                with self.assertRaisesRegex(RuntimeError, "injected failure"):
                    agent.run("retry input")
                self.assertEqual(memory.export_messages(), before)

                def retry(messages, tools=None):
                    self.assertEqual(messages, [m for m in memory.get_messages()])
                    self.assertEqual(messages[1:-1], [
                        {"role": "user", "content": "history"},
                        {"role": "assistant", "content": "answer"},
                    ])
                    self.assertEqual(messages[-1], {"role": "user", "content": "retry input"})
                    return {"content": "retry succeeds"}

                llm.chat_completion.side_effect = retry
                agent.mcp_client = self.client
                self.assertEqual(agent.run("retry input").answer, "retry succeeds")
                self.assertEqual(memory.get_messages()[1:], [
                    {"role": "user", "content": "retry input"},
                    {"role": "assistant", "content": "retry succeeds"},
                ])

    def test_cancelled_run_also_rolls_back(self):
        memory = ConversationMemory()
        before = memory.export_messages()
        llm = Mock()
        llm.chat_completion.side_effect = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            SmartAgent(memory, self.client, llm).run("cancelled")
        self.assertEqual(memory.export_messages(), before)

    def test_malformed_llm_arguments_produce_result_and_allow_recovery(self):
        memory = ConversationMemory(window_size=2)
        llm = Mock()
        bad = tool_call("bad")
        bad["function"]["arguments"] = "{invalid JSON"
        llm.chat_completion.side_effect = [
            {"content": "", "tool_calls": [bad]}, {"content": "recovered"},
        ]
        result = SmartAgent(memory, self.client, llm).run("request")
        self.assertEqual(result.answer, "recovered")
        self.assertEqual(self.tool.calls, [])
        tool_result = next(trace for trace in result.traces if trace.step_type == "tool_result")
        self.assertTrue(tool_result.details["is_error"])
        self.assert_tool_pairs(llm.chat_completion.call_args_list[1].args[0])

    def test_synthesis_uses_actual_observations_and_reports_failed_calls(self):
        memory = ConversationMemory(window_size=2)
        llm = Mock()
        llm.chat_completion.side_effect = [
            {"content": "", "tool_calls": [tool_call("failed", {"msg": None})]},
            {"content": "无法核实，时间仅为估算"},
        ]
        SmartAgent(memory, self.client, llm, max_turns=1).run("15点到达")
        synthesis = llm.chat_completion.call_args_list[1]
        self.assertIsNone(synthesis.kwargs["tools"])
        prompt = synthesis.args[0][-1]["content"]
        for text in ("实际工具观察", "尚未查询", "不可用或待核实", "本地静态资料",
                     "不得表述为实时", "估算", "不得保证准时到达", "is_error=True"):
            self.assertIn(text, prompt)
        self.assertIn('{"tool": "echo", "call_id": "failed"}', prompt)
        self.assertIn("工具参数无效", synthesis.args[0][-2]["content"])
        self.assertEqual(self.tool.calls, [])

    def test_malformed_model_frames_roll_back_before_any_tool_executes(self):
        valid = tool_call("valid")
        bad_id = tool_call("bad")
        bad_id["id"] = []
        bad_function = tool_call("bad")
        bad_function["function"] = None
        bad_name = tool_call("bad")
        bad_name["function"]["name"] = None
        malformed = [
            None, [], "answer", {"content": []}, {"tool_calls": {}},
            {"tool_calls": "echo"}, {"tool_calls": [valid, None]},
            {"tool_calls": [valid, bad_id]}, {"tool_calls": [valid, bad_function]},
            {"tool_calls": [valid, bad_name]}, {"tool_calls": [valid, valid]},
        ]
        for response in malformed:
            with self.subTest(response=response):
                memory = ConversationMemory()
                before = memory.export_messages()
                llm = Mock()
                llm.chat_completion.side_effect = [response, {"content": "retry works"}]
                agent = SmartAgent(memory, self.client, llm)
                with self.assertRaisesRegex(ValueError, "[Mm]odel"):
                    agent.run("request")
                self.assertEqual(memory.export_messages(), before)
                self.assertEqual(self.tool.calls, [])
                self.assertEqual(agent.run("request").answer, "retry works")

    def test_malformed_synthesis_rolls_back_tool_cycle(self):
        for response in ([], {"content": {}}, {"tool_calls": [tool_call("unexpected")]}):
            with self.subTest(response=response):
                memory = ConversationMemory()
                before = memory.export_messages()
                llm = Mock()
                llm.chat_completion.side_effect = [
                    {"tool_calls": [tool_call("observation")]}, response,
                ]
                with self.assertLogs("agent.core", level="WARNING"):
                    with self.assertRaises(ValueError):
                        SmartAgent(memory, self.client, llm, max_turns=1).run("request")
                self.assertEqual(memory.export_messages(), before)


class TestMCPExecutionRegressions(unittest.TestCase):
    def setUp(self):
        self.server = MCPServer()
        self.tool = RecordingTool()
        self.server.register_tool(self.tool)

    def request(self, arguments):
        return self.server.handle_request({
            "jsonrpc": "2.0", "id": 1, "method": "tools/call",
            "params": {"name": "echo", "arguments": arguments},
        })

    def test_malformed_arguments_rejected_before_execution_on_all_paths(self):
        bad_arguments = [
            None, False, 0, "", [], ["x"], "{}", {}, {"msg": None},
            {"msg": 7}, {"msg": []}, {"msg": "x", "mode": "fly"},
            {"msg": "x", "extra": 1}, {"msg": "x", "count": True},
            {"msg": "x", "count": 1.2}, {"msg": "x", "price": False},
            {"msg": "x", "enabled": 1}, {"msg": "x", "stops": "a"},
            {"msg": "x", "stops": [None]}, {"msg": "x", "stops": [{}]},
            {"msg": "x", "stops": [{"name": None}]},
            {"msg": "x", "stops": [{"name": "a", "extra": 1}]},
            {"msg": "x", "labels": {"a": 1}}, {"msg": "x", 1: "bad key"},
        ]
        client = MCPClient(self.server)
        for arguments in bad_arguments:
            with self.subTest(arguments=arguments):
                self.assertTrue(self.server.call_tool("echo", arguments).is_error)
                response = self.request(arguments)
                self.assertNotIn("error", response)
                self.assertTrue(response["result"]["isError"])
                self.assertTrue(client.call_tool("echo", arguments).is_error)
        self.assertEqual(self.tool.calls, [])

    def test_valid_schema_types_nullable_and_nested_values(self):
        arguments = {
            "msg": "ok", "mode": "walk", "count": 2, "price": 2.5,
            "enabled": True, "nullable": None, "stops": [{"name": "广州"}],
            "labels": {"tag": "value"},
        }
        self.assertFalse(self.server.call_tool("echo", arguments).is_error)
        self.assertEqual(self.tool.calls, [arguments])

    def test_optional_field_null_is_not_omission(self):
        self.assertFalse(self.server.call_tool("echo", {"msg": "ok"}).is_error)
        self.assertTrue(self.server.call_tool("echo", {"msg": "ok", "mode": None}).is_error)
        self.assertEqual(len(self.tool.calls), 1)

    def test_additional_properties_default_is_allowed(self):
        self.tool.input_schema = {"type": "object", "properties": {"msg": {"type": "string"}}}
        self.assertFalse(self.server.call_tool("echo", {"msg": "ok", "extra": 1}).is_error)

    def test_enum_distinguishes_booleans_and_numbers(self):
        self.tool.input_schema = {"type": "object", "properties": {"msg": {"enum": [1]}}}
        self.assertTrue(self.server.call_tool("echo", {"msg": True}).is_error)
        self.assertEqual(self.tool.calls, [])

    def test_invalid_tool_names_are_safe(self):
        for name in (None, False, 3, [], {}, "", "missing"):
            with self.subTest(name=name):
                self.assertTrue(self.server.call_tool(name, {}).is_error)
        self.assertEqual(self.tool.calls, [])

    def test_omitted_arguments_are_empty_object_but_explicit_null_is_invalid(self):
        self.server.register_tool(FunctionTool(lambda: "ok", name="empty"))
        self.assertFalse(self.server.call_tool("empty").is_error)
        response = self.server.handle_request({
            "jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "empty"},
        })
        self.assertFalse(response["result"]["isError"])
        self.assertTrue(self.server.call_tool("empty", None).is_error)

    def test_custom_tool_exception_is_caught_centrally(self):
        self.tool.execute = Mock(side_effect=RuntimeError("boom secret-token"))
        with self.assertLogs("mcp.server", level="WARNING") as logs:
            results = (self.server.call_tool("echo", {"msg": "ok"}),
                       MCPClient(self.server).call_tool("echo", {"msg": "ok"}))
        for result in results:
            self.assertTrue(result.is_error)
            self.assertIn("RuntimeError", result.get_text())
            self.assertIn("boom", result.get_text())
        self.assertTrue(all(record.exc_info is None for record in logs.records))
        self.assertNotIn("secret-token", "\n".join(logs.output))

    def test_invalid_tool_return_is_a_tool_error(self):
        self.tool.execute = Mock(return_value=None)
        self.assertTrue(self.server.call_tool("echo", {"msg": "ok"}).is_error)

    def test_function_tool_inferred_schema_validates_before_execution(self):
        called = []

        def function(count: int, enabled: bool = False):
            called.append((count, enabled))
            return "ok"

        self.server.register_tool(FunctionTool(function))
        for arguments in ({}, {"count": True}, {"count": 2, "enabled": None},
                          {"count": 2, "extra": "x"}):
            self.assertTrue(self.server.call_tool("function", arguments).is_error)
        self.assertEqual(called, [])
        self.assertFalse(self.server.call_tool("function", {"count": 2}).is_error)
        self.assertEqual(called, [(2, False)])

    def test_function_tool_kwargs_allows_extra_arguments(self):
        self.server.register_tool(FunctionTool(lambda **kwargs: kwargs, name="kwargs"))
        result = self.server.call_tool("kwargs", {"extra": True})
        self.assertFalse(result.is_error)
        self.assertEqual(json.loads(result.get_text()), {"extra": True})

    def test_invalid_jsonrpc_top_level_and_envelopes_are_safe(self):
        for payload in (None, False, 0, "request", [], [1], {},
                        {"jsonrpc": "1.0", "method": "ping"},
                        {"jsonrpc": "2.0", "method": []},
                        {"jsonrpc": "2.0", "method": "ping", "id": []},
                        {"jsonrpc": "2.0", "method": "ping", "id": True}):
            with self.subTest(payload=payload):
                response = self.server.handle_request(payload)
                self.assertEqual(response["error"]["code"], -32600)
                self.assertIsNone(response["id"])

    def test_invalid_rpc_params_return_invalid_params(self):
        for params in (None, False, 0, "", [], ["x"]):
            with self.subTest(params=params):
                response = self.server.handle_request({
                    "jsonrpc": "2.0", "id": 0, "method": "tools/call", "params": params,
                })
                self.assertEqual(response["error"]["code"], -32602)
                self.assertEqual(response["id"], 0)

    def test_invalid_rpc_tool_name_returns_invalid_params(self):
        for name in (None, False, [], {}, 1, ""):
            with self.subTest(name=name):
                response = self.server.handle_request({
                    "jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name},
                })
                self.assertEqual(response["error"]["code"], -32602)

    def test_notifications_never_return_responses(self):
        for method, params in (("notifications/initialized", {}), ("ping", {}),
                               ("unknown", {}), ("tools/call", {"name": []}),
                               ("tools/call", {"name": "echo", "arguments": None}),
                               ("tools/call", None)):
            with self.subTest(method=method, params=params):
                self.assertIsNone(self.server.handle_request({
                    "jsonrpc": "2.0", "method": method, "params": params,
                }))
        self.assertIsNone(self.server.handle_request({
            "jsonrpc": "2.0", "method": "tools/call",
            "params": {"name": "echo", "arguments": {"msg": "notification"}},
        }))
        self.assertEqual(self.tool.calls, [{"msg": "notification"}])

    def test_explicit_null_id_is_a_request(self):
        response = self.server.handle_request({"jsonrpc": "2.0", "method": "ping", "id": None})
        self.assertIsNone(response["id"])
        self.assertEqual(response["result"]["status"], "pong")

    def test_dispatch_exception_is_internal_error_and_notifications_stay_silent(self):
        self.server.list_tools = Mock(side_effect=RuntimeError("broken registry"))
        response = self.server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(response["error"]["code"], -32603)
        self.assertIsNone(self.server.handle_request({"jsonrpc": "2.0", "method": "tools/list"}))

    def test_client_handshake_precedes_list_and_call_and_runs_once(self):
        for first_operation in ("list", "call"):
            with self.subTest(first_operation=first_operation):
                server = Mock(wraps=self.server)
                client = MCPClient(server)
                if first_operation == "list":
                    client.get_tools()
                else:
                    client.call_tool("echo", {"msg": "ok"})
                client.refresh_tools()
                client.call_tool("echo", {"msg": "again"})
                client.initialize()
                requests = [call.args[0] for call in server.handle_request.call_args_list]
                methods = [request["method"] for request in requests]
                self.assertEqual(methods[:2], ["initialize", "notifications/initialized"])
                self.assertEqual(methods.count("initialize"), 1)
                self.assertNotIn("id", requests[1])
                self.assertEqual(requests[0]["params"]["protocolVersion"], "2024-11-05")
                self.assertIn("clientInfo", requests[0]["params"])
                self.assertEqual(client.server_info["name"], self.server.name)

    def test_failed_handshake_can_retry_without_sending_initialized_early(self):
        server = Mock(wraps=self.server)
        server.handle_request.side_effect = [
            {"jsonrpc": "2.0", "id": "client-initialize", "error": {"code": -32603}},
        ]
        client = MCPClient(server)
        with self.assertRaisesRegex(RuntimeError, "initialize failed"):
            client.get_tools()
        self.assertEqual(server.handle_request.call_count, 1)
        self.assertIsNone(client.server_info)
        server.handle_request.side_effect = None
        self.assertEqual(len(client.get_tools()), 1)

    def test_invalid_initialize_results_fail_cleanly(self):
        for result in (None, [], {}, {"protocolVersion": "unsupported"},
                       {"protocolVersion": "2024-11-05", "serverInfo": {}, "capabilities": None}):
            with self.subTest(result=result):
                server = Mock()
                server.handle_request.return_value = {"result": result}
                with self.assertRaisesRegex(RuntimeError, "unsupported server response"):
                    MCPClient(server).get_tools()
                self.assertEqual(server.handle_request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
