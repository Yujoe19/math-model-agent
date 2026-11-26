"""Loopback-only HTTP interface; API keys are held in memory per request."""
import json
import sys
import threading
import urllib.error
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from agent import run_agent
from files import decode_files

ROOT = Path(__file__).resolve().parent
HOST, PORT = '127.0.0.1', 8789
MAX_BODY = 12_000_000


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, status, data, content_type='application/json; charset=utf-8'):
        if isinstance(data, dict):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        paths = {'/': ('index.html', 'text/html; charset=utf-8'), '/app.js': ('app.js', 'text/javascript; charset=utf-8'), '/style.css': ('style.css', 'text/css; charset=utf-8')}
        item = paths.get(self.path)
        if not item:
            return self.respond(404, {'error': '页面不存在'})
        self.respond(200, (ROOT / 'static' / item[0]).read_bytes(), item[1])

    def do_POST(self):
        if self.path != '/api/run':
            return self.respond(404, {'error': '接口不存在'})
        if self.headers.get('Origin') != f'http://{HOST}:{PORT}' or self.headers.get('Host') != f'{HOST}:{PORT}':
            return self.respond(403, {'error': '请求来源不匹配。'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > MAX_BODY:
                raise ValueError('请求过大或为空。')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('请求格式不正确。')
            key, question, model = (body.get(k, '') for k in ('apiKey', 'question', 'model'))
            if not all(isinstance(x, str) for x in (key, question, model)):
                raise ValueError('请求字段格式不正确。')
            key, question, model = key.strip(), question.strip(), model.strip()
            if not key or len(key) > 300 or '\n' in key or '\r' in key:
                raise ValueError('请输入有效的 DeepSeek API Key。')
            if not 1 <= len(question) <= 40000:
                raise ValueError('请输入不超过 40000 字的题目。')
            if not re_model(model):
                raise ValueError('模型名称格式不正确。')
            base_url=body.get('baseUrl','https://api.deepseek.com')
            if not isinstance(base_url,str) or len(base_url)>500:
                raise ValueError('模型 API 地址不正确。')
            base_url=base_url.strip().rstrip('/')
            try: url=urllib.parse.urlsplit(base_url); port=url.port
            except ValueError: raise ValueError('模型 API 地址不正确。')
            if not url.hostname or url.username or url.password or url.query or url.fragment or (url.scheme!='https' and not (url.scheme=='http' and url.hostname in ('localhost','127.0.0.1','::1'))):
                raise ValueError('请输入 HTTPS 模型 API 地址；本机接口可使用 HTTP。')
            search_key=body.get('searchApiKey','')
            if not isinstance(search_key,str) or len(search_key)>300 or '\n' in search_key or '\r' in search_key:
                raise ValueError('搜索 API Key 格式不正确。')
            search_key=search_key.strip() or (key if url.hostname=='api.deepseek.com' else '')
            history = body.get('history', [])
            if not isinstance(history,list) or len(history)>12:
                raise ValueError('对话历史过长，请新建对话。')
            for message in history:
                if not isinstance(message,dict) or message.get('role') not in ('user','assistant') or not isinstance(message.get('content'),str) or len(message['content'])>50000:
                    raise ValueError('对话历史格式不正确或过长。')
            history = [{'role':m['role'],'content':m['content']} for m in history]
            texts, images, sandbox_files = decode_files(body.get('files', []))
            if images and body.get('vision') is not True:
                raise ValueError('请确认模型支持图片，并勾选“模型支持图片”。')
            for filename, content in texts:
                question += '\n\n【上传文件：'+filename+'】\n'+content
            if sandbox_files:
                question += '\n\n【沙盒可用数据文件】'+', '.join('/tmp/data/'+f['name'] for f in sandbox_files)
            if images:
                question += '\n\n【随本轮附带的图片】'+', '.join(x['name'] for x in images)
            enabled = []
            if body.get('search') is True: enabled.append('search_papers')
            if body.get('webSearch') is True:
                if not search_key: raise ValueError('使用其他模型平台时，请另填 DeepSeek 搜索 API Key 或关闭网页搜索。')
                enabled.append('search_web')
            if body.get('execute') is True: enabled.append('run_python')
        except (ValueError, TypeError, json.JSONDecodeError, ImportError) as e:
            return self.respond(400, {'error': str(e)})
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-ndjson; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        def emit(obj):
            self.wfile.write((json.dumps(obj, ensure_ascii=False) + '\n').encode('utf-8'))
            self.wfile.flush()
        try:
            run_agent(question, key, model, enabled, emit, history=history, images=images, files=sandbox_files, base_url=base_url, search_key=search_key)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except urllib.error.HTTPError as e:
            message = {401: 'API Key 无效或无权限。', 402: '模型账户余额不足。', 403: '模型平台拒绝请求。', 429: '请求过于频繁，请稍后再试。'}.get(e.code, f'模型请求失败（HTTP {e.code}）。')
            emit({'type': 'error', 'message': message})
        except (OSError, ValueError, KeyError):
            emit({'type': 'error', 'message': '请求失败或模型输出不完整，请检查网络及模型配置后重试。'})


def re_model(value):
    return 1 <= len(value) <= 80 and all(c.isascii() and (c.isalnum() or c in '-_.') for c in value)


if __name__ == '__main__':
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f'建模 Agent 已启动：http://{HOST}:{PORT}', flush=True)
    if '--no-browser' not in sys.argv:
        threading.Timer(.8, lambda: webbrowser.open(f'http://{HOST}:{PORT}')).start()
    server.serve_forever()
