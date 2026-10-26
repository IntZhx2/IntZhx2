import io
import unittest
import urllib.error
from unittest.mock import patch, MagicMock
from smart_agent.agent.llm_client import LLMClient, validate_api_base, _NoRedirect


class TestLLMConfiguration(unittest.TestCase):
    def test_supported_paths_are_not_rewritten(self):
        for base in ['https://example.invalid/api/paas/v4',
                     'https://example.invalid/compatible-mode/v1']:
            self.assertEqual(validate_api_base(base), base)
        self.assertEqual(validate_api_base('https://example.invalid/chat/completions'),
                         'https://example.invalid/v1')

    def test_unsafe_urls_are_rejected(self):
        for base in ['http://remote.invalid/v1', 'https://user:password@example.invalid/v1',
                     'file:///etc/passwd', 'https://example.invalid/v1?key=secret']:
            with self.assertRaises(ValueError):
                validate_api_base(base)

    def test_redirect_does_not_forward_auth(self):
        self.assertIsNone(_NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.invalid'))

    def test_authorization_and_provider_path(self):
        client = LLMClient('https://example.invalid/api/paas/v4', 'dummy-key', 'exact-model-id')
        opener = MagicMock()
        opener.open.return_value = io.BytesIO(b'{"choices":[{"message":{"content":"OK"}}]}')
        with patch('urllib.request.build_opener', return_value=opener):
            self.assertEqual(client.chat_completion([{'role':'user','content':'hi'}])['content'], 'OK')
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://example.invalid/api/paas/v4/chat/completions')
        self.assertEqual(request.get_header('Authorization'), 'Bearer dummy-key')

    def test_provider_errors_do_not_echo_secrets(self):
        opener = MagicMock()
        opener.open.side_effect = urllib.error.HTTPError('https://example.invalid', 401, '', {},
                                                       io.BytesIO(b'REAL_SECRET_MARKER'))
        with patch('urllib.request.build_opener', return_value=opener):
            with self.assertRaises(RuntimeError) as result:
                LLMClient('https://example.invalid', 'dummy-key', 'model').chat_completion([])
        self.assertNotIn('REAL_SECRET_MARKER', str(result.exception))

