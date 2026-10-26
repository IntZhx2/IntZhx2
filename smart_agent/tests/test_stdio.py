import json
import subprocess
import sys
import unittest
from pathlib import Path


class TestStdioTransport(unittest.TestCase):
    def test_independent_process_handshake_list_call_and_parse_error(self):
        root = Path(__file__).resolve().parents[2]
        frames = [
            {'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2024-11-05'}},
            {'jsonrpc':'2.0','method':'notifications/initialized'},
            {'jsonrpc':'2.0','id':2,'method':'tools/list'},
            {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{
                'name':'attraction_info','arguments':{'city':'广州','attraction_name':'广州塔'}}},
        ]
        data = '\n'.join(json.dumps(frame) for frame in frames) + '\ninvalid JSON\n'
        result = subprocess.run([sys.executable, str(root/'smart_agent/main.py'), '--mcp-stdio'],
                                input=data, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        replies = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(replies), 4)
        self.assertEqual(replies[0]['result']['protocolVersion'], '2024-11-05')
        self.assertEqual(len(replies[1]['result']['tools']), 5)
        self.assertIn('广州塔', replies[2]['result']['content'][0]['text'])
        self.assertEqual(replies[3]['error']['code'], -32700)
