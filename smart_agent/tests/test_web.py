"""In-memory HTTP acceptance tests: no external model or real user directories."""
import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
from smart_agent.web.server import SmartAgentHTTPRequestHandler, AgentServiceHolder
from smart_agent.agent.session_manager import SessionManager


class MockHTTPConnection:
    def __init__(self, data):
        self.rfile, self.wfile = BytesIO(data), BytesIO()

    def makefile(self, mode, *args, **kwargs):
        return self.rfile if 'r' in mode else self.wfile

    def sendall(self, data):
        self.wfile.write(data)


def request(method, path, body=None, authenticated=True, headers=None, raw=None):
    data = raw if raw is not None else json.dumps(body).encode() if body is not None else b''
    supplied = {'Host': 'localhost', 'Content-Length': str(len(data)), 'Content-Type': 'application/json'}
    if authenticated:
        supplied['Cookie'] = 'travel_access=' + AgentServiceHolder.access_token
    supplied.update(headers or {})
    head = method + ' ' + path + ' HTTP/1.1\r\n' + ''.join(k + ': ' + v + '\r\n' for k, v in supplied.items()) + '\r\n'
    conn = MockHTTPConnection(head.encode() + data)
    SmartAgentHTTPRequestHandler(conn, ('127.0.0.1', 12345), None)
    head, _, response = conn.wfile.getvalue().partition(b'\r\n\r\n')
    status = int(head.split(b' ')[1])
    return status, head.decode(), response


def simulate_http_request(method, path, body=None):
    status, _, data = request(method, path, body)
    return status, json.loads(data) if data else {}


class TestTravelWebServer(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for target, value in [
            ('smart_agent.web.server.CONFIG_FILE', self.root / 'config.json'),
            ('smart_agent.agent.session_manager.SESSIONS_DIR', self.root),
            ('smart_agent.web.server.WORKSPACE_DIR', self.root),
        ]:
            p = patch(target, value)
            p.start()
            self.addCleanup(p.stop)
        AgentServiceHolder.initialize()
        AgentServiceHolder.llm_client.api_key = ''

    def configure(self):
        return simulate_http_request('POST', '/api/config', {
            'api_key': 'dummy-not-a-real-key', 'api_base': 'https://example.invalid/v1', 'model': 'test-model'})

    def test_status_requires_authentication(self):
        self.assertEqual(request('GET', '/api/status', authenticated=False)[0], 401)
        status, data = simulate_http_request('GET', '/api/status')
        self.assertEqual(status, 200)
        self.assertEqual(len(data['team']), 3)

    def test_browser_bootstrap_is_http_only_and_strict(self):
        status, headers, _ = request('GET', '/', authenticated=False)
        self.assertEqual(status, 200)
        self.assertIn('HttpOnly; SameSite=Strict', headers)
        self.assertIn('Content-Security-Policy:', headers)

    def test_foreign_origin_and_host_are_rejected(self):
        for headers in [{'Origin': 'https://other.invalid'}, {'Host': 'other.invalid'},
                        {'Sec-Fetch-Site': 'cross-site'}]:
            self.assertEqual(request('POST', '/api/config', {}, headers=headers)[0], 403)
        self.assertEqual(request('OPTIONS', '/api/config', headers={'Origin': 'https://other.invalid'})[0], 403)

    def test_config_saved_is_not_connected(self):
        status, data = self.configure()
        self.assertEqual(status, 200)
        self.assertFalse(data['verified'])
        self.assertIn('尚未验证', data['message'])
        self.assertEqual((self.root / 'config.json').stat().st_mode & 0o777, 0o600)

    def test_endpoint_change_requires_new_key_and_does_not_mutate(self):
        self.configure()
        old = AgentServiceHolder.llm_client
        status, _ = simulate_http_request('POST', '/api/config', {'api_base': 'https://new.invalid/v1'})
        self.assertEqual(status, 400)
        self.assertIs(AgentServiceHolder.llm_client, old)

    def test_explicit_connection_test(self):
        self.configure()
        with patch('smart_agent.agent.llm_client.LLMClient.chat_completion', return_value={'content': 'OK'}):
            status, result = simulate_http_request('POST', '/api/config/test', {})
        self.assertEqual(status, 200)
        self.assertTrue(result['verified'])

    def test_invalid_json_and_types_are_errors(self):
        for body in [[], {'message': 123}, {'message': 'hello', 'stream': 'yes'}]:
            self.assertEqual(request('POST', '/api/chat', body)[0], 400)
        self.assertEqual(request('POST', '/api/chat', raw=b'{')[0], 400)
        self.assertEqual(request('POST', '/api/chat', {}, headers={'Content-Length': '-1'})[0], 400)
        self.assertEqual(request('POST', '/api/chat', {}, headers={'Content-Length': '1048577'})[0], 400)

    def test_chat_without_key(self):
        status, data = simulate_http_request('POST', '/api/chat', {'message': '广州旅游'})
        self.assertEqual(status, 400)
        self.assertIn('未配置', data['error'])

    def test_unknown_session_is_rejected(self):
        self.configure()
        status, _ = simulate_http_request('POST', '/api/chat', {
            'message': 'hello', 'session_id': 'missing', 'stream': False})
        self.assertEqual(status, 404)
        self.assertEqual(AgentServiceHolder.contexts, {})

    def test_sessions_are_isolated_and_get_is_read_only(self):
        self.configure()
        a, b = [SessionManager.create_new_session()['session_id'] for _ in range(2)]
        def echo(messages, tools=None):
            return {'content': '|'.join(m['content'] for m in messages if m['role'] == 'user')}
        with patch('smart_agent.agent.llm_client.LLMClient.chat_completion', side_effect=echo):
            for sid, message in [(a, 'PRIVATE_A'), (b, 'PRIVATE_B')]:
                status, result = simulate_http_request('POST', '/api/chat', {
                    'session_id': sid, 'message': message, 'stream': False})
                self.assertEqual(status, 200)
                self.assertEqual(result['answer'], message)
            original = AgentServiceHolder.context(a).memory.get_messages()
            self.assertEqual(simulate_http_request('GET', '/api/session?id=' + b)[0], 200)
            self.assertEqual(AgentServiceHolder.context(a).memory.get_messages(), original)

    def test_same_session_busy_returns_conflict(self):
        self.configure()
        sid = SessionManager.create_new_session()['session_id']
        context = AgentServiceHolder.context(sid)
        context.lock.acquire()
        try:
            self.assertEqual(simulate_http_request('POST', '/api/chat', {
                'session_id': sid, 'message': 'hello', 'stream': False})[0], 409)
            self.assertEqual(simulate_http_request('POST', '/api/session/delete', {'id': sid})[0], 409)
        finally:
            context.lock.release()

    def test_clear_is_scoped_and_persisted(self):
        a, b = [SessionManager.create_new_session()['session_id'] for _ in range(2)]
        for sid in [a, b]:
            SessionManager.append_turn(sid, 'hi', 'reply', [], [])
        self.assertEqual(simulate_http_request('POST', '/api/clear', {'session_id': a})[0], 200)
        self.assertEqual(SessionManager.get_session(a)['turns'], [])
        self.assertEqual(len(SessionManager.get_session(b)['turns']), 1)

    def test_mcp_notification_and_parameters(self):
        self.assertEqual(simulate_http_request('POST', '/api/mcp', {
            'jsonrpc': '2.0', 'method': 'notifications/initialized'})[0], 202)
        status, data = simulate_http_request('POST', '/api/mcp', {
            'jsonrpc': '2.0', 'method': 'tools/list', 'id': 1})
        self.assertEqual(status, 200)
        self.assertEqual(len(data['result']['tools']), 5)

    def test_download_scope_and_symlink(self):
        (self.root / 'safe.md').write_text('# safe')
        status, headers, body = request('GET', '/api/itinerary/download?filename=safe.md')
        self.assertEqual(status, 200)
        self.assertIn('attachment', headers)
        self.assertEqual(body, b'# safe')
        self.assertEqual(request('GET', '/api/itinerary/download?filename=../README.md')[0], 400)
        (self.root / 'link.md').symlink_to(self.root / 'safe.md')
        self.assertEqual(request('GET', '/api/itinerary/download?filename=link.md')[0], 404)


if __name__ == '__main__':
    unittest.main()
