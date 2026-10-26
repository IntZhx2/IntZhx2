"""Real loopback HTTP tests, including a local mock model provider (no paid API)."""
import http.client
import http.server
import json
import tempfile
import threading
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch
from smart_agent.web.server import SmartAgentHTTPRequestHandler, AgentServiceHolder


class ModelHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(payload)
        if payload.get('tools') and payload['messages'][-1]['role'] == 'user':
            message = {'role': 'assistant', 'content': '', 'tool_calls': [{
                'id': 'local-test-call', 'type': 'function', 'function': {
                    'name': 'attraction_info', 'arguments': json.dumps({'city': '广州', 'attraction_name': '广州塔'})}}]}
        else:
            message = {'role': 'assistant', 'content': '本地测试模型：已根据工具结果整理行程。'}
        body = json.dumps({'choices': [{'message': message}]}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestLoopbackIntegration(unittest.TestCase):
    def test_http_bootstrap_tool_cycle_stream_and_download(self):
        with tempfile.TemporaryDirectory() as directory, ExitStack() as stack:
            root = Path(directory)
            for target, value in [
                ('smart_agent.web.server.CONFIG_FILE', root/'config.json'),
                ('smart_agent.agent.session_manager.SESSIONS_DIR', root),
                ('smart_agent.web.server.WORKSPACE_DIR', root),
                ('smart_agent.tools.itinerary_tool.WORKSPACE_DIR', root),
            ]:
                stack.enter_context(patch(target, value))
            AgentServiceHolder.initialize()
            web = http.server.ThreadingHTTPServer(('127.0.0.1', 0), SmartAgentHTTPRequestHandler)
            model = http.server.ThreadingHTTPServer(('127.0.0.1', 0), ModelHandler)
            model.requests = []
            for server in (web, model):
                worker = threading.Thread(target=server.serve_forever, daemon=True)
                worker.start()
                stack.callback(server.server_close)
                stack.callback(server.shutdown)

            cookie = ''
            def call(method, path, payload=None, auth=True, extra=None):
                connection = http.client.HTTPConnection('127.0.0.1', web.server_port, timeout=5)
                headers = {'Content-Type': 'application/json'}
                if auth:
                    headers['Cookie'] = cookie
                headers.update(extra or {})
                connection.request(method, path, None if payload is None else json.dumps(payload), headers)
                response = connection.getresponse()
                result = response.status, dict(response.getheaders()), response.read()
                connection.close()
                return result

            self.assertEqual(call('GET', '/api/status', auth=False)[0], 401)
            status, headers, _ = call('GET', '/', auth=False)
            self.assertEqual(status, 200)
            cookie = headers['Set-Cookie'].split(';')[0]
            self.assertEqual(call('GET', '/api/status')[0], 200)
            self.assertEqual(call('GET', '/api/status', extra={'Origin':'https://foreign.invalid'})[0], 403)
            self.assertEqual(call('POST', '/api/config', {
                'api_base': 'http://127.0.0.1:%s/v1' % model.server_port,
                'api_key': 'dummy-loopback-key', 'model': 'local-fixture-model'})[0], 200)
            self.assertEqual(call('POST', '/api/config/test', {})[0], 200)
            sid = json.loads(call('POST', '/api/session/new', {})[2])['session_id']
            status, _, body = call('POST', '/api/chat', {'message':'广州塔游览', 'session_id':sid, 'stream':True})
            self.assertEqual(status, 200)
            events = [json.loads(line[6:]) for line in body.decode().splitlines() if line.startswith('data: ')]
            self.assertIn('tool_call', [event['type'] for event in events])
            self.assertIn('tool_result', [event['type'] for event in events])
            self.assertEqual(events[-1]['type'], 'done')
            self.assertTrue(any(msg['role'] == 'tool' for request in model.requests for msg in request['messages']))
            status, _, body = call('GET', '/api/session/download?id=' + sid)
            self.assertEqual(status, 200)
            self.assertIn('广州塔', body.decode())
            status, _, body = call('POST', '/api/chat', {'message':'继续规划', 'session_id':sid, 'stream':False})
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)['session_id'], sid)

