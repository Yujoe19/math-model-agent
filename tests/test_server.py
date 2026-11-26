import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from unittest import mock

import server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        server.PORT = 0
        cls.httpd = ThreadingHTTPServer((server.HOST, 0), server.Handler)
        server.PORT = cls.httpd.server_port
        cls.base = f'http://{server.HOST}:{server.PORT}'
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def post(self, origin, data):
        return urllib.request.urlopen(urllib.request.Request(self.base+'/api/run',data=json.dumps(data).encode(),headers={'Origin':origin,'Content-Type':'application/json'}),timeout=10)

    def test_cross_origin_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post('http://attacker.invalid', {'apiKey':'secret','question':'x','model':'deepseek-chat'})
        self.assertEqual(e.exception.code,403)
        e.exception.close()

    def test_key_is_passed_per_request_without_echo(self):
        def fake(question, key, model, enabled, emit):
            self.assertEqual(key,'test-secret')
            self.assertEqual(enabled,['search_papers'])
            emit({'type':'answer','content':'ok'})
            emit({'type':'done'})
        with mock.patch.object(server,'run_agent',fake):
            with self.post(self.base, {'apiKey':'test-secret','question':'hello','model':'deepseek-chat','search':True}) as response:
                raw=response.read().decode()
        self.assertNotIn('test-secret',raw)
        self.assertEqual([json.loads(x)['type'] for x in raw.splitlines()],['answer','done'])

if __name__=='__main__': unittest.main()
