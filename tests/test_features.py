import base64
import io
import json
import unittest
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from openpyxl import Workbook
from pypdf import PdfWriter

import agent
from files import decode_files


def attach(name, data):
    return {'name':name,'data':base64.b64encode(data).decode('ascii')}


class AttachmentTests(unittest.TestCase):
    def test_csv_and_spreadsheet_reading(self):
        wb=Workbook();ws=wb.active;ws.append(['x','y']);ws.append([1,4]);buf=io.BytesIO();wb.save(buf)
        texts,images,files=decode_files([attach('values.csv',b'x,y\n1,4\n'),attach('table.xlsx',buf.getvalue())])
        self.assertEqual(len(texts),2);self.assertIn('1\t4',texts[1][1]);self.assertEqual(len(files),2);self.assertEqual(images,[])

    def test_image_signature_and_scanned_pdf(self):
        with self.assertRaises(ValueError):decode_files([attach('fake.png',b'not an image')])
        writer=PdfWriter();writer.add_blank_page(width=100,height=100);buf=io.BytesIO();writer.write(buf)
        with self.assertRaisesRegex(ValueError,'没有可提取'):decode_files([attach('blank.pdf',buf.getvalue())])

    def test_duplicate_data_files_rejected(self):
        with self.assertRaisesRegex(ValueError,'重名'):decode_files([attach('x.csv',b'a'),attach('x.csv',b'b')])


class WorkflowTests(unittest.TestCase):
    def test_sandbox_artifact_validation(self):
        png = base64.b64encode(b'\x89PNG\r\n\x1a\nexample').decode('ascii')
        self.assertEqual(agent.valid_artifacts([{'name':'chart.png','data':png}]), [{'name':'chart.png','data':png}])
        for item in (None, {'name':'../chart.png','data':png}, {'name':'chart.png','data':'invalid!'},
                     {'name':'chart.png','data':base64.b64encode(b'not png').decode('ascii')}):
            self.assertEqual(agent.valid_artifacts([item]), [])

    def test_openai_compatible_provider_http(self):
        captured={}
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                captured['path']=self.path
                captured['auth']=self.headers.get('Authorization')
                captured['body']=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                content=json.dumps({'choices':[{'finish_reason':'stop','message':{'role':'assistant','content':'ok'}}]}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        httpd=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=httpd.serve_forever,daemon=True).start()
        try:
            result=agent.post_model('provider-secret','vision-model',[{'role':'user','content':[{'type':'text','text':'hello'},{'type':'image_url','image_url':{'url':'data:image/png;base64,AA=='}}]}],[],f'http://127.0.0.1:{httpd.server_port}/v1')
        finally:
            httpd.shutdown();httpd.server_close()
        self.assertEqual(captured['path'],'/v1/chat/completions')
        self.assertEqual(captured['auth'],'Bearer provider-secret')
        self.assertEqual(captured['body']['messages'][0]['content'][1]['type'],'image_url')
        self.assertEqual(result['content'],'ok')

    def test_history_and_images_passed_to_model(self):
        calls=[];events=[]
        def model(key,name,messages,tools):
            calls.append(messages);return {'role':'assistant','content':'ok'}
        agent.run_agent('新问题','secret','any',['search_web'],events.append,model_call=model,
                        history=[{'role':'user','content':'旧问题'},{'role':'assistant','content':'旧答案'}],
                        images=[{'name':'x.png','url':'data:image/png;base64,aGVsbG8='}],search_key='web-secret')
        self.assertEqual(calls[0][1]['content'],'旧问题')
        self.assertEqual(calls[0][-1]['content'][1]['type'],'image_url')
        self.assertNotIn('secret',json.dumps(events))

    def test_web_search_uses_separate_key(self):
        calls=[];events=[]
        def model(key,name,messages,tools):
            calls.append(1)
            if len(calls)==1:return {'role':'assistant','content':None,'tool_calls':[{'id':'1','type':'function','function':{'name':'search_web','arguments':'{"query":"test"}'}}]}
            return {'role':'assistant','content':'finished'}
        def search(query,key):
            self.assertEqual(key,'search-key');return {'results':[{'title':'source','url':'https://example.com'}]}
        agent.run_agent('search','model-key','model',['search_web'],events.append,model_call=model,web_search=search,search_key='search-key')
        self.assertTrue(any(e['type']=='tool_result' and e['result']['results'] for e in events))
        self.assertNotIn('search-key',json.dumps(events))

    def test_real_chart_and_uploaded_data_in_sandbox(self):
        data=attach('table.csv',b'x,y\n1,2\n2,5\n')
        code='import pandas as pd\nimport matplotlib.pyplot as p\nd=pd.read_csv("/tmp/data/table.csv")\nprint(int(d.y.sum()))\np.plot(d.x,d.y)\np.savefig("/tmp/output/chart.png")'
        result=agent.run_python(code,[data])
        self.assertEqual(result['status'],'ok',result)
        self.assertIn('7',result['stdout'])
        self.assertEqual(result['artifacts'][0]['name'],'chart.png')
        self.assertTrue(base64.b64decode(result['artifacts'][0]['data']).startswith(b'\x89PNG'))

if __name__=='__main__': unittest.main()
