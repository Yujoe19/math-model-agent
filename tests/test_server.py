import json
import base64
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
        def fake(question, key, model, enabled, emit, **kwargs):
            self.assertEqual(key,'test-secret')
            self.assertEqual(enabled,['search_papers'])
            emit({'type':'answer','content':'ok'})
            emit({'type':'done'})
        with mock.patch.object(server,'run_agent',fake):
            with self.post(self.base, {'apiKey':'test-secret','question':'hello','model':'deepseek-chat','search':True}) as response:
                raw=response.read().decode()
        self.assertNotIn('test-secret',raw)
        self.assertEqual([json.loads(x)['type'] for x in raw.splitlines()],['answer','done'])

    def test_custom_provider_history_and_image(self):
        image=base64.b64encode(b'\x89PNG\r\n\x1a\nplaceholder').decode()
        def fake(question,key,model,enabled,emit,**kwargs):
            self.assertEqual(kwargs['base_url'],'https://provider.example/v1')
            self.assertEqual(kwargs['history'][0]['content'],'上一问')
            self.assertTrue(kwargs['images'][0]['url'].startswith('data:image/png;base64,'))
            self.assertEqual(kwargs['search_key'],'different-search-key')
            self.assertEqual(enabled,['search_web'])
            emit({'type':'answer','content':'ok'});emit({'type':'done'})
        data={'apiKey':'model-key','question':'下一问','model':'vision-model','baseUrl':'https://provider.example/v1',
              'searchApiKey':'different-search-key','vision':True,'webSearch':True,
              'history':[{'role':'user','content':'上一问'}],'files':[{'name':'x.png','data':image}]}
        with mock.patch.object(server,'run_agent',fake):
            with self.post(self.base,data) as response: raw=response.read().decode()
        self.assertNotIn('model-key',raw);self.assertNotIn('different-search-key',raw)

    def test_non_local_http_provider_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post(self.base,{'apiKey':'key','question':'x','model':'m','baseUrl':'http://provider.example/v1'})
        self.assertEqual(e.exception.code,400);e.exception.close()

    def test_image_requires_vision_switch(self):
        image=base64.b64encode(b'\x89PNG\r\n\x1a\nplaceholder').decode()
        with self.assertRaises(urllib.error.HTTPError) as e:
            self.post(self.base,{'apiKey':'key','question':'x','model':'m','vision':False,'files':[{'name':'x.png','data':image}]})
        self.assertEqual(e.exception.code,400);e.exception.close()

if __name__=='__main__': unittest.main()
