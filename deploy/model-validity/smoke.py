"""发布后 OTA、WebSocket hello 及静态资源校验；不打印设备和凭据。"""
import json,subprocess,urllib.request,hashlib,re
from pathlib import Path
from production_validate import sql
stage=Path('/opt/aipet-model-validation-20260909')
html=urllib.request.urlopen('http://127.0.0.1:8002/',timeout=10).read()
assert hashlib.sha256(html).digest()==hashlib.sha256((stage/'dist/index.html').read_bytes()).digest()
assets=set(re.findall(r'(?:src|href)=["\'](/(?:js|css)/[^"\']+)["\']',html.decode()))
for asset in assets:
 data=urllib.request.urlopen('http://127.0.0.1:8002'+asset,timeout=15).read()
 assert data==(stage/'dist'/asset.lstrip('/')).read_bytes()
print('PASS frontend index and %d asset hashes'%len(assets))
device=json.loads(sql("SELECT JSON_OBJECT('mac',mac_address,'board',board,'version',app_version) FROM ai_device WHERE agent_id IS NOT NULL ORDER BY last_connected_at DESC LIMIT 1"))
code=r"""
import sys,json,asyncio,urllib.request
import websockets
c=json.load(sys.stdin);mac=c['mac']
body={'mac_address':mac,'application':{'name':'xiaozhi','version':c['version']},'board':{'type':c['board']}}
req=urllib.request.Request('http://127.0.0.1:8002/xiaozhi/ota/',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','Device-Id':mac,'Client-Id':mac})
r=json.loads(urllib.request.urlopen(req,timeout=15).read());assert r.get('websocket',{}).get('url');print('PASS OTA websocket credentials')
async def test():
 headers={'Device-Id':mac,'Client-Id':mac,'Authorization':'Bearer '+r['websocket'].get('token','')}
 async with websockets.connect('ws://127.0.0.1:8000/xiaozhi/v1/',additional_headers=headers,open_timeout=15) as ws:
  await ws.send(json.dumps({'type':'hello','version':1,'transport':'websocket','audio_params':{'format':'opus','sample_rate':16000,'channels':1,'frame_duration':60}}))
  for _ in range(6):
   reply=json.loads(await asyncio.wait_for(ws.recv(),20))
   if reply.get('type')=='hello': print('PASS registered device websocket hello');return
  raise RuntimeError('hello response missing')
asyncio.run(test())
"""
r=subprocess.run(['docker','run','--rm','-i','--network=host','--memory=512m','xiaozhi-aipet-server:v0.9.6-b15-validity','python','-c',code],input=json.dumps(device),text=True,capture_output=True,timeout=60)
if r.returncode: print('FAIL OTA/websocket smoke; inspect private log');(stage/'smoke-private.log').write_text(r.stderr);raise SystemExit(1)
print(r.stdout)
