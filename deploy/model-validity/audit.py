"""隔离容器验证，不挂生产配置、不改生产容器，配置仅通过标准输入。"""
import json
import sys
from pathlib import Path
import subprocess
from inventory import models
stage=Path(__file__).resolve().parent
rows=models()
base=["docker","run","--rm","-i","--cpus=1","--memory=3g","--pids-limit=256","--cap-drop=ALL","--security-opt=no-new-privileges","--network=xiaozhi-server_default","-v",str(stage/"model_validation.py")+":/opt/xiaozhi-esp32-server/core/model_validation.py:ro","-v","/opt/xiaozhi-server/models/SenseVoiceSmall/model.pt:/opt/xiaozhi-esp32-server/models/SenseVoiceSmall/model.pt:ro","-v",str(stage/"sample")+":/validation-sample","xiaozhi-aipet-server:v0.9.6-b14-companion"]
(stage/'sample').mkdir(exist_ok=True)
voice=next(x['config'] for x in rows if x['id']=='TTS_HuoshanDoubleStreamTTS')
source="""import sys,json,asyncio,wave,os
from core.model_validation import huoshan_audio
c=json.load(sys.stdin)
with open(os.devnull,'w') as sink:
 sys.stdout=sys.stderr=sink
 a=asyncio.run(asyncio.wait_for(huoshan_audio(c),20))
 with wave.open('/validation-sample/model_validation_sample.wav','wb') as f:
  f.setnchannels(1); f.setsampwidth(2); f.setframerate(16000); f.writeframes(a)
"""
try:
 r = subprocess.CompletedProcess([], 0) if (stage/'sample/model_validation_sample.wav').exists() else subprocess.run(base+['python','-c',source],input=json.dumps(voice),text=True,capture_output=True,timeout=30)
 print('合成样本：'+('成功' if r.returncode==0 else '失败'),flush=True)
except subprocess.TimeoutExpired:
 print('合成样本超时',flush=True)
previous = json.loads((stage/'audit-results.json').read_text()) if (stage/'audit-results.json').exists() else []
retry_ids = {x['id'] for x in previous if x['status']=='unknown'}
results = [x for x in previous if x['id'] not in retry_ids] if '--retry' in sys.argv else []
for row in rows:
 if '--retry' in sys.argv and row['id'] not in retry_ids: continue
 c=row.pop('config') or {}
 if isinstance(c,str): c=json.loads(c)
 if c.get('llm'):
  dependency=next((x for x in results+previous if x['id']==c['llm']),{})
  c['_validation_dependency']={'status':dependency.get('status','unknown')}
 try:
  r=subprocess.run(base+['python','-m','core.model_validation'],input=json.dumps({'modelType':row['modelType'],'config':c}),text=True,capture_output=True,timeout=29)
  status=json.loads(r.stdout.strip().splitlines()[-1])
 except Exception:
  status={'status':'unknown','reason':'隔离探测超时或未返回结果'}
 row.update(status); results.append(row)
 print(json.dumps(row,ensure_ascii=False),flush=True)
 (stage/'audit-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
