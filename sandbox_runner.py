"""Runs inside the disposable container, not on the host."""
import base64
import json
import os
import pathlib
import sys

payload=json.loads(sys.stdin.read())
data_dir=pathlib.Path('/tmp/data'); data_dir.mkdir(exist_ok=True)
out_dir=pathlib.Path('/tmp/output'); out_dir.mkdir(exist_ok=True)
for item in payload.get('files',[]):
    name=pathlib.PurePath(item['name']).name
    if name in ('','.','..') or name!=item['name']: raise ValueError('invalid file name')
    (data_dir/name).write_bytes(base64.b64decode(item['data'],validate=True))
os.chdir('/tmp')
try:
    exec(compile(payload['code'],'<agent-code>','exec'),{'__name__':'__main__'})
finally:
    artifacts=[]
    for path in sorted(out_dir.glob('*.png'))[:2]:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size>450_000: continue
            data=path.read_bytes()
            if not data.startswith(b'\x89PNG\r\n\x1a\n'): continue
            artifacts.append({'name':path.name,'data':base64.b64encode(data).decode('ascii')})
        except OSError: pass
    print('\n__MODELING_AGENT_ARTIFACTS__'+json.dumps(artifacts,separators=(',',':')))
