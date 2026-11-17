"""在语音容器内运行，密钥从私有挂载配置读取，不打印。"""
import json,sys,urllib.request,yaml
from pathlib import Path
cfg=yaml.safe_load(Path('data/.config.yaml').read_text())
secret=cfg.get('server',{}).get('auth_key') or cfg.get('manager-api',{}).get('secret')
path=sys.argv[1]
body=json.loads(sys.argv[2]) if len(sys.argv)>2 else ({'device_uid':'d8:85:ac:bb:b0:80','consented':True} if path=='start' else None)
if path == 'start-dual':
 body={'device_uid':'d8:85:ac:bb:b0:80','peer_device_uid':'d8:85:ac:ba:85:d0','consented':True}
 path='start'
req=urllib.request.Request('http://127.0.0.1:8003/internal/social/test/'+path,
 data=json.dumps(body).encode() if body is not None else None,
 headers={'X-Server-Secret':secret,'Content-Type':'application/json'})
try:
 with urllib.request.urlopen(req,timeout=12) as r: print(r.read().decode())
except urllib.error.HTTPError as e:
 print('HTTP',e.code,e.reason)
 raise SystemExit(1)
